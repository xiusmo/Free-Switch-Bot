from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from genesis import Outbound, Consumer, Inbound
import asyncio
import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, List
import aiofiles
from pathlib import Path
import wave
import numpy as np
from pydub import AudioSegment
import io
import websockets
import threading
import time
from .config import config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FreeSWITCH AI Service")

# 全局变量存储通话状态
active_calls: Dict[str, Dict] = {}
call_recordings: Dict[str, List[bytes]] = {}
audio_streams: Dict[str, asyncio.Queue] = {}

class CallRequest(BaseModel):
    phone_number: str
    caller_id: Optional[str] = None

class AnswerRequest(BaseModel):
    call_uuid: str

class HangupRequest(BaseModel):
    call_uuid: str

class CallStatus(BaseModel):
    call_uuid: str
    status: str
    phone_number: str
    start_time: Optional[str] = None
    duration: Optional[int] = None

# Genesis 连接配置 - 使用配置类
FS_HOST = config.FS_HOST
FS_PORT = config.FS_PORT
FS_PASSWORD = config.FS_PASSWORD

# 音频配置 - 使用配置类
AUDIO_SAMPLE_RATE = config.AUDIO_SAMPLE_RATE
AUDIO_CHANNELS = config.AUDIO_CHANNELS
RECORDING_DIR = config.RECORDING_DIR

# 确保录音目录存在
os.makedirs(RECORDING_DIR, exist_ok=True)

class AudioStreamManager:
    """音频流管理器 - 使用 mod_audio_stream 插件"""
    
    def __init__(self):
        self.websocket_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.audio_buffers: Dict[str, List[bytes]] = {}
        self.server = None
        self.port = 8081  # WebSocket 端口
        self._server_started = False
        
    async def start_server(self):
        """启动 WebSocket 服务器接收音频流（防重复）"""
        if self._server_started:
            return
        try:
            self.server = await websockets.serve(
                self.handle_websocket_connection,
                "0.0.0.0",
                self.port
            )
            self._server_started = True
            logger.info(f"音频流 WebSocket 服务器启动在端口 {self.port}")
            print(f"🔌 音频流 WebSocket 服务器启动在端口 {self.port}")
        except Exception as e:
            logger.error(f"启动 WebSocket 服务器失败: {e}")
    
    async def handle_websocket_connection(self, websocket, path):
        """处理 WebSocket 连接"""
        try:
            # 从路径中提取通话UUID
            # 路径格式: /audio/{call_uuid}
            if path.startswith("/audio/"):
                call_uuid = path.split("/")[2]
                logger.info(f"音频流连接建立: {call_uuid}")
                print(f"🎵 音频流连接建立: {call_uuid}")
                
                # 存储连接和初始化音频缓冲区
                self.websocket_connections[call_uuid] = websocket
                self.audio_buffers[call_uuid] = []
                
                # 通知 FreeSWITCH 开始发送音频流
                await self.start_audio_stream(call_uuid)
                
                try:
                    async for message in websocket:
                        await self.handle_audio_message(call_uuid, message)
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"音频流连接关闭: {call_uuid}")
                    print(f"🔌 音频流连接关闭: {call_uuid}")
                finally:
                    # 清理连接
                    if call_uuid in self.websocket_connections:
                        del self.websocket_connections[call_uuid]
                    if call_uuid in self.audio_buffers:
                        del self.audio_buffers[call_uuid]
            else:
                await websocket.close(1008, "Invalid path")
                
        except Exception as e:
            logger.error(f"处理 WebSocket 连接失败: {e}")
            await websocket.close(1011, "Internal error")
    
    async def handle_audio_message(self, call_uuid: str, message):
        """处理音频消息"""
        try:
            if isinstance(message, bytes):
                # 二进制音频数据
                if call_uuid in call_recordings:
                    call_recordings[call_uuid].append(message)
                
                # 存储到音频缓冲区
                if call_uuid in self.audio_buffers:
                    self.audio_buffers[call_uuid].append(message)
                
                logger.debug(f"收到音频数据: {call_uuid}, 大小: {len(message)} bytes")
            else:
                # 文本消息（可能是控制信息）
                logger.info(f"收到文本消息: {call_uuid}, 内容: {message}")
                
        except Exception as e:
            logger.error(f"处理音频消息失败: {e}")
    
    async def start_audio_stream(self, call_uuid: str):
        """通知 FreeSWITCH 开始发送音频流"""
        try:
            # 使用 mod_audio_stream 插件开始音频流
            # 格式: uuid_audio_stream {call_uuid} start ws://localhost:8081/audio/{call_uuid}
            stream_url = f"ws://localhost:{self.port}/audio/{call_uuid}"
            command = f"uuid_audio_stream {call_uuid} start {stream_url}"
            
            # 这里需要通过 Genesis 执行命令
            # 暂时记录日志，实际执行需要 FreeSwitchManager 配合
            logger.info(f"音频流命令: {command}")
            print(f"📡 音频流命令: {command}")
            
        except Exception as e:
            logger.error(f"启动音频流失败: {e}")
    
    async def stop_audio_stream(self, call_uuid: str):
        """停止音频流"""
        try:
            command = f"uuid_audio_stream {call_uuid} stop"
            logger.info(f"停止音频流命令: {command}")
            print(f"⏹️  停止音频流命令: {command}")
            
            # 关闭 WebSocket 连接
            if call_uuid in self.websocket_connections:
                await self.websocket_connections[call_uuid].close()
                
        except Exception as e:
            logger.error(f"停止音频流失败: {e}")
    
    def get_audio_buffer(self, call_uuid: str) -> List[bytes]:
        """获取音频缓冲区数据"""
        return self.audio_buffers.get(call_uuid, [])
    
    def clear_audio_buffer(self, call_uuid: str):
        """清空音频缓冲区"""
        if call_uuid in self.audio_buffers:
            self.audio_buffers[call_uuid].clear()

class FreeSwitchManager:
    def __init__(self):
        self.consumer = None
        self.inbound = None
        self.connected = False
        self.audio_manager = AudioStreamManager()
        self._connect_lock = asyncio.Lock()
        
    async def connect(self):
        """连接到 FreeSWITCH（带重试）"""
        async with self._connect_lock:
            # 启动音频流 WebSocket 服务器
            await self.audio_manager.start_server()
            
            backoff_seconds = 1
            max_backoff = 30
            while not self.connected:
                try:
                    logger.info(f"尝试连接到 FreeSWITCH: {FS_HOST}:{FS_PORT}")
                    print(f"🔌 尝试连接到 FreeSWITCH: {FS_HOST}:{FS_PORT}")
                    
                    # 创建消费者连接 (用于监听事件)
                    self.consumer = Consumer(
                        host=FS_HOST,
                        port=FS_PORT,
                        password=FS_PASSWORD
                    )
                    
                    # 创建入站连接 (用于发送命令)
                    self.inbound = Inbound(
                        host=FS_HOST,
                        port=FS_PORT,
                        password=FS_PASSWORD
                    )
                    
                    # 连接到 FreeSWITCH（入站）
                    await self.inbound.start()
                    logger.info("入站连接已建立")
                    print("✅ 入站连接已建立")

                    # 连接到 FreeSWITCH（消费者）
                    await self.consumer.start()
                    logger.info("消费者连接已建立")
                    print("✅ 消费者连接已建立")
                    
                    self.connected = True
                    logger.info("成功连接到 FreeSWITCH")
                    print("✅ 成功连接到 FreeSWITCH")
                    
                    # 启动事件监听
                    asyncio.create_task(self.listen_for_events())
                    break
                except Exception as e:
                    logger.error(f"连接 FreeSWITCH 失败: {e}")
                    print(f"❌ 连接 FreeSWITCH 失败: {e}")
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, max_backoff)
    
    async def listen_for_events(self):
        """监听 FreeSWITCH 事件"""
        try:
            async for event in self.consumer.events():
                await self.handle_event(event)
        except Exception as e:
            logger.error(f"事件监听错误: {e}")
            self.connected = False
            # 断线重连
            asyncio.create_task(self.connect())
    
    async def handle_event(self, event):
        """处理 FreeSWITCH 事件"""
        try:
            event_data = json.loads(event)
            event_name = event_data.get("Event-Name")
            
            if event_name == "CHANNEL_CREATE":
                await self.handle_channel_create(event_data)
            elif event_name == "CHANNEL_ANSWER":
                await self.handle_channel_answer(event_data)
            elif event_name == "CHANNEL_HANGUP":
                await self.handle_channel_hangup(event_data)
                
        except Exception as e:
            logger.error(f"处理事件错误: {e}")
    
    async def handle_channel_create(self, event_data):
        """处理通道创建事件"""
        call_uuid = event_data.get("Unique-ID")
        caller_id = event_data.get("Caller-Caller-ID-Number")
        callee_id = event_data.get("Caller-Destination-Number")
        
        if call_uuid:
            active_calls[call_uuid] = {
                "status": "ringing",
                "caller_id": caller_id,
                "callee_id": callee_id,
                "start_time": datetime.now().isoformat(),
                "call_uuid": call_uuid
            }
            
            call_recordings[call_uuid] = []
            
            logger.info(f"来电: {caller_id} -> {callee_id} (UUID: {call_uuid})")
            print(f"📞 来电: {caller_id} -> {callee_id} (UUID: {call_uuid})")
    
    async def handle_channel_answer(self, event_data):
        """处理通道应答事件"""
        call_uuid = event_data.get("Unique-ID")
        
        if call_uuid in active_calls:
            active_calls[call_uuid]["status"] = "answered"
            active_calls[call_uuid]["answer_time"] = datetime.now().isoformat()
            
            logger.info(f"通话已接听: {call_uuid}")
            print(f"✅ 通话已接听: {call_uuid}")
            
            # 开始音频流和播放
            await self.start_audio_stream_and_playback(call_uuid)
    
    async def handle_channel_hangup(self, event_data):
        """处理通道挂断事件"""
        call_uuid = event_data.get("Unique-ID")
        
        if call_uuid in active_calls:
            call_info = active_calls[call_uuid]
            end_time = datetime.now()
            start_time = datetime.fromisoformat(call_info["start_time"])
            duration = int((end_time - start_time).total_seconds())
            
            call_info["status"] = "completed"
            call_info["end_time"] = end_time.isoformat()
            call_info["duration"] = duration
            
            # 停止音频流
            await self.audio_manager.stop_audio_stream(call_uuid)
            
            # 保存录音
            if call_uuid in call_recordings and call_recordings[call_uuid]:
                await self.save_recording(call_uuid, call_recordings[call_uuid])
            
            logger.info(f"通话结束: {call_uuid}, 时长: {duration}秒")
            print(f"📴 通话结束: {call_uuid}, 时长: {duration}秒")
    
    async def start_audio_stream_and_playback(self, call_uuid: str):
        """开始音频流和播放"""
        try:
            # 1. 启动音频流到 WebSocket
            await self.audio_manager.start_audio_stream(call_uuid)
            
            # 2. 开始播放示例音频文件
            await self.start_audio_playback(call_uuid)
            
            logger.info(f"音频流和播放已启动: {call_uuid}")
            print(f"🎵 音频流和播放已启动: {call_uuid}")
            
        except Exception as e:
            logger.error(f"启动音频流和播放失败: {e}")
    
    async def start_audio_playback(self, call_uuid: str):
        """开始播放音频"""
        try:
            # 读取示例音频文件
            audio_file_path = "/app/wav-example.wav"
            if os.path.exists(audio_file_path):
                # 使用 FreeSWITCH 的 audio 插件播放音频
                play_command = f"uuid_audio {call_uuid} start /app/wav-example.wav"
                await self.inbound.api(play_command)
                
                logger.info(f"开始播放音频: {call_uuid}")
                print(f"🎵 开始播放音频: {call_uuid}")
            else:
                logger.warning(f"音频文件不存在: {audio_file_path}")
                
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
    
    async def save_recording(self, call_uuid, audio_chunks):
        """保存录音"""
        try:
            if not audio_chunks:
                return
                
            # 合并音频数据
            combined_audio = b''.join(audio_chunks)
            
            # 保存为 WAV 文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"call_{call_uuid}_{timestamp}.wav"
            filepath = os.path.join(RECORDING_DIR, filename)
            
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(AUDIO_CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(AUDIO_SAMPLE_RATE)
                wav_file.writeframes(combined_audio)
            
            logger.info(f"录音已保存: {filepath}")
            print(f"💾 录音已保存: {filepath}")
            
        except Exception as e:
            logger.error(f"保存录音失败: {e}")
    
    async def make_outbound_call(self, phone_number: str, caller_id: str = None):
        """发起外呼"""
        try:
            if not self.connected:
                raise Exception("未连接到 FreeSWITCH")
            
            # 构建外呼命令
            call_command = f"originate {{origination_caller_id_number={caller_id or '1000'}}}sofia/external/{phone_number}@localhost &echo"
            
            # 执行外呼
            result = await self.inbound.api(call_command)
            
            logger.info(f"外呼命令已发送: {phone_number}")
            print(f"📤 外呼命令已发送: {phone_number}")
            
            return {"status": "success", "message": f"外呼 {phone_number} 已发起", "result": result}
            
        except Exception as e:
            logger.error(f"外呼失败: {e}")
            raise HTTPException(status_code=500, detail=f"外呼失败: {str(e)}")
    
    async def answer_call(self, call_uuid: str):
        """接听来电"""
        try:
            if not self.connected:
                raise Exception("未连接到 FreeSWITCH")
            
            if call_uuid not in active_calls:
                raise Exception("通话不存在")
            
            # 接听通话
            answer_command = f"uuid_answer {call_uuid}"
            result = await self.inbound.api(answer_command)
            
            logger.info(f"通话已接听: {call_uuid}")
            print(f"✅ 通话已接听: {call_uuid}")
            
            return {"status": "success", "message": f"通话 {call_uuid} 已接听", "result": result}
            
        except Exception as e:
            logger.error(f"接听失败: {e}")
            raise HTTPException(status_code=500, detail=f"接听失败: {str(e)}")
    
    async def hangup_call(self, call_uuid: str):
        """挂断通话"""
        try:
            if not self.connected:
                raise Exception("未连接到 FreeSWITCH")
            
            if call_uuid not in active_calls:
                raise Exception("通话不存在")
            
            # 挂断通话
            hangup_command = f"uuid_kill {call_uuid}"
            result = await self.inbound.api(hangup_command)
            
            logger.info(f"通话已挂断: {call_uuid}")
            print(f"📴 通话已挂断: {call_uuid}")
            
            return {"status": "success", "message": f"通话 {call_uuid} 已挂断", "result": result}
            
        except Exception as e:
            logger.error(f"挂断失败: {e}")
            raise HTTPException(status_code=500, detail=f"挂断失败: {str(e)}")

# 创建 FreeSWITCH 管理器实例
fs_manager = FreeSwitchManager()

@app.on_event("startup")
async def startup_event():
    """应用启动时连接 FreeSWITCH"""
    asyncio.create_task(fs_manager.connect())

@app.get("/health")
async def health():
    """健康检查"""
    connection_info = {
        "status": "ok",
        "freeswitch_connected": fs_manager.connected,
        "fs_host": FS_HOST,
        "fs_port": FS_PORT,
        "fs_password_set": bool(FS_PASSWORD),
        "active_calls": len(active_calls),
        "audio_streams": len(fs_manager.audio_manager.websocket_connections),
        "consumer_connected": fs_manager.consumer is not None,
        "inbound_connected": fs_manager.inbound is not None
    }
    
    # 如果连接失败，尝试重新连接
    if not fs_manager.connected:
        asyncio.create_task(fs_manager.connect())
    
    return connection_info

@app.get("/test-connection")
async def test_connection():
    """测试 FreeSWITCH 连接"""
    try:
        if fs_manager.connected:
            # 尝试执行一个简单的 API 命令来测试连接
            result = await fs_manager.inbound.api("version")
            return {
                "status": "success",
                "connected": True,
                "version": result,
                "message": "连接正常，可以执行命令"
            }
        else:
            # 尝试连接
            await fs_manager.connect()
            if fs_manager.connected:
                return {
                    "status": "success",
                    "connected": True,
                    "message": "连接已建立"
                }
            else:
                return {
                    "status": "error",
                    "connected": False,
                    "message": "无法建立连接"
                }
    except Exception as e:
        logger.error(f"连接测试失败: {e}")
        return {
            "status": "error",
            "connected": False,
            "error": str(e),
            "message": "连接测试失败"
        }

@app.get("/calls", response_model=List[CallStatus])
async def get_active_calls():
    """获取所有活跃通话"""
    calls = []
    for call_uuid, call_info in active_calls.items():
        calls.append(CallStatus(
            call_uuid=call_uuid,
            status=call_info["status"],
            phone_number=call_info.get("caller_id", "unknown"),
            start_time=call_info.get("start_time"),
            duration=call_info.get("duration")
        ))
    return calls

@app.post("/call/outbound")
async def make_call(call_request: CallRequest):
    """发起外呼"""
    return await fs_manager.make_outbound_call(
        phone_number=call_request.phone_number,
        caller_id=call_request.caller_id
    )

@app.post("/call/answer")
async def answer_call(answer_request: AnswerRequest):
    """接听来电"""
    return await fs_manager.answer_call(answer_request.call_uuid)

@app.post("/call/hangup")
async def hangup_call(hangup_request: HangupRequest):
    """挂断通话"""
    return await fs_manager.hangup_call(hangup_request.call_uuid)

@app.get("/call/{call_uuid}/recording")
async def get_call_recording(call_uuid: str):
    """获取通话录音"""
    if call_uuid not in call_recordings:
        raise HTTPException(status_code=404, detail="录音不存在")
    
    # 返回录音文件列表
    recording_files = []
    for filename in os.listdir(RECORDING_DIR):
        if filename.startswith(f"call_{call_uuid}_"):
            recording_files.append(filename)
    
    return {"call_uuid": call_uuid, "recordings": recording_files}

@app.get("/recordings")
async def list_recordings():
    """列出所有录音文件"""
    recordings = []
    for filename in os.listdir(RECORDING_DIR):
        if filename.endswith(".wav"):
            filepath = os.path.join(RECORDING_DIR, filename)
            stat = os.stat(filepath)
            recordings.append({
                "filename": filename,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
    
    return {"recordings": recordings}

@app.get("/audio/stream/{call_uuid}")
async def get_audio_stream(call_uuid: str):
    """获取实时音频流（WebSocket 升级）"""
    # 这个端点用于 WebSocket 升级
    # 实际的音频流处理在 AudioStreamManager 中
    return {"message": "音频流端点", "call_uuid": call_uuid}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False) 
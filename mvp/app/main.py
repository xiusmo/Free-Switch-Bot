from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from genesis import Consumer, Inbound
import asyncio
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List
import wave
from pydub import AudioSegment
import websockets
import uuid
import aiofiles
from . import config
from .qwen_omni_client import QwenOmniAudioProcessor

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FreeSWITCH Call Service")

# 全局变量存储通话状态
active_calls: Dict[str, Dict] = {}
call_recordings: Dict[str, List[bytes]] = {}
# 通话对应的待播放音频文件映射
call_audio_files: Dict[str, str] = {}

class CallRequest(BaseModel):
    phone_number: str
    caller_id: Optional[str] = None
    dial_prefix: Optional[str] = None

# Genesis 连接配置 - 使用配置类
FS_HOST = config.config.FS_HOST
FS_PORT = config.config.FS_PORT
FS_PASSWORD = config.config.FS_PASSWORD

# 音频配置 - 使用配置类
AUDIO_SAMPLE_RATE = config.config.AUDIO_SAMPLE_RATE
AUDIO_CHANNELS = config.config.AUDIO_CHANNELS
RECORDING_DIR = config.config.RECORDING_DIR

# 确保录音目录与上传目录存在
os.makedirs(RECORDING_DIR, exist_ok=True)
os.makedirs(config.config.UPLOAD_DIR, exist_ok=True)

class AudioStreamManager:
    """音频流管理器 - 使用 mod_audio_stream 插件"""
    
    def __init__(self):
        self.websocket_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.audio_buffers: Dict[str, List[bytes]] = {}
        self.server = None
        self.port = config.config.AUDIO_WS_PORT  # WebSocket 端口
        self._server_started = False
        self._sender_tasks: Dict[str, asyncio.Task] = {}
        
        # AI音频处理器
        self.ai_processors: Dict[str, QwenOmniAudioProcessor] = {}
        self._ai_enabled = config.config.QWEN_OMNI_ENABLED
        
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
                
                # 启动AI音频处理器（如果启用）
                if self._ai_enabled:
                    try:
                        await self.start_ai_processor(call_uuid, websocket)
                    except Exception as e:
                        logger.error(f"启动AI音频处理器失败: {e}")
                        # 回退到传统音频播放
                        await self.start_traditional_audio_playback(call_uuid, websocket)
                else:
                    # 使用传统音频播放
                    await self.start_traditional_audio_playback(call_uuid, websocket)
                
                try:
                    async for message in websocket:
                        await self.handle_audio_message(call_uuid, message)
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"音频流连接关闭: {call_uuid}")
                    print(f"🔌 音频流连接关闭: {call_uuid}")
                finally:
                    # 清理连接
                    if call_uuid in self._sender_tasks:
                        try:
                            self._sender_tasks[call_uuid].cancel()
                        except Exception:
                            pass
                        del self._sender_tasks[call_uuid]
                    
                    # 清理AI处理器
                    if call_uuid in self.ai_processors:
                        try:
                            await self.ai_processors[call_uuid].stop()
                        except Exception:
                            pass
                        del self.ai_processors[call_uuid]
                    
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
                
                # 如果启用AI处理，发送到AI处理器
                if call_uuid in self.ai_processors:
                    await self.ai_processors[call_uuid].process_incoming_audio(message)
                
                logger.debug(f"收到音频数据: {call_uuid}, 大小: {len(message)} bytes")
            else:
                # 文本消息（可能是控制信息）
                logger.info(f"收到文本消息: {call_uuid}, 内容: {message}")
                
        except Exception as e:
            logger.error(f"处理音频消息失败: {e}")
    

    async def push_audio_file_to_freeswitch(self, websocket, file_path: str, call_uuid: str):
        """将本地 WAV 文件内容通过 WebSocket 推送到 FreeSWITCH（16-bit PCM, 8kHz, mono, 20ms 帧）"""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"推流文件不存在: {file_path}")
                return

            # 加载并转换音频到期望格式
            audio: AudioSegment = AudioSegment.from_file(file_path)
            audio = audio.set_frame_rate(AUDIO_SAMPLE_RATE).set_channels(AUDIO_CHANNELS).set_sample_width(2)
            raw_bytes: bytes = audio.raw_data

            frame_duration_sec = 0.02  # 20ms
            bytes_per_second = AUDIO_SAMPLE_RATE * AUDIO_CHANNELS * 2
            chunk_size = int(bytes_per_second * frame_duration_sec)

            # 按实时节奏推送
            offset = 0
            while offset < len(raw_bytes):
                if websocket.closed:
                    break
                chunk = raw_bytes[offset: offset + chunk_size]
                if not chunk:
                    break
                await websocket.send(chunk)
                offset += len(chunk)
                await asyncio.sleep(frame_duration_sec)

            logger.info(f"推流完成: {call_uuid}, 文件: {file_path}")
            print(f"📤 推流完成: {call_uuid}, 文件: {file_path}")
        except Exception as e:
            logger.error(f"推流失败: {e}")
    
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
    
    async def start_ai_processor(self, call_uuid: str, websocket):
        """启动AI音频处理器"""
        try:
            # 创建AI音频处理器
            ai_processor = QwenOmniAudioProcessor(call_uuid)
            
            # 设置AI音频响应回调
            ai_processor.on_ai_audio = lambda audio_data: asyncio.create_task(
                self.send_ai_audio_to_freeswitch(websocket, audio_data, call_uuid)
            )
            
            # 启动AI处理器
            success = await ai_processor.start()
            if success:
                self.ai_processors[call_uuid] = ai_processor
                logger.info(f"AI音频处理器启动成功: {call_uuid}")
                print(f"🤖 AI音频处理器启动成功: {call_uuid}")
            else:
                logger.warning(f"AI音频处理器启动失败，回退到传统模式: {call_uuid}")
                raise Exception("AI处理器启动失败")
                
        except Exception as e:
            logger.error(f"启动AI音频处理器异常: {e}")
            raise
    
    async def start_traditional_audio_playback(self, call_uuid: str, websocket):
        """启动传统音频播放（固定文件推流）"""
        try:
            if call_uuid in self._sender_tasks:
                # 旧任务清理
                try:
                    self._sender_tasks[call_uuid].cancel()
                except Exception:
                    pass
            
            audio_file_path = call_audio_files.get(call_uuid, config.config.EXAMPLE_AUDIO_FILE)
            self._sender_tasks[call_uuid] = asyncio.create_task(
                self.push_audio_file_to_freeswitch(websocket, audio_file_path, call_uuid)
            )
            logger.info(f"传统音频播放已启动: {call_uuid}")
            print(f"🎵 传统音频播放已启动: {call_uuid}")
            
        except Exception as e:
            logger.error(f"启动传统音频播放失败: {e}")
    
    async def send_ai_audio_to_freeswitch(self, websocket, audio_data: bytes, call_uuid: str):
        """将AI生成的音频发送到FreeSWITCH"""
        try:
            if websocket.closed:
                return
                
            # 确保音频格式符合FreeSWITCH要求
            # Qwen-Omni输出的音频格式需要转换为8kHz, 16-bit, mono
            # 这里假设Qwen-Omni输出的格式与FreeSWITCH兼容
            # 如果不兼容，需要添加音频格式转换逻辑
            
            await websocket.send(audio_data)
            logger.debug(f"AI音频发送到FreeSWITCH: {call_uuid}, 大小: {len(audio_data)} bytes")
            
        except Exception as e:
            logger.error(f"发送AI音频失败: {e}")
    
class FreeSwitchManager:
    def __init__(self):
        self.consumer = None
        self.inbound = None
        self.connected = False
        self.audio_manager = AudioStreamManager()
        self._connect_lock = asyncio.Lock()
        
    async def connect(self):
        """连接到 FreeSWITCH"""
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

                    # 注册事件处理器
                    self.consumer.handle("CHANNEL_CREATE")(self.handle_channel_create)
                    self.consumer.handle("CHANNEL_ANSWER")(self.handle_channel_answer)
                    self.consumer.handle("CHANNEL_HANGUP")(self.handle_channel_hangup)

                    # 创建入站连接 (用于发送命令)
                    self.inbound = Inbound(
                        host=FS_HOST,
                        port=FS_PORT,
                        password=FS_PASSWORD
                    )
                    
                    # 连接到 FreeSWITCH（入站）
                    await self.inbound.start()
                    # 标记总体连接成功（入站可用即可认为已连通）
                    self.connected = True
                    logger.info("入站连接已建立")
                    print("✅ 入站连接已建立")
                    logger.info("成功连接到 FreeSWITCH")
                    print("✅ 成功连接到 FreeSWITCH")

                    # 连接到 FreeSWITCH（消费者）后台运行（失败不影响总体连通状态）
                    try:
                        asyncio.create_task(self.consumer.start())
                        logger.info("消费者连接任务已启动")
                        print("✅ 消费者连接任务已启动")
                    except Exception as _e:
                        logger.error(f"消费者连接任务启动失败: {_e}")
                    
                    break
                except Exception as e:
                    logger.error(f"连接 FreeSWITCH 失败: {e}")
                    print(f"❌ 连接 FreeSWITCH 失败: {e}")
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, max_backoff)

    async def api(self, command: str, timeout_seconds: float = 1.0) -> str:
        """通过 ESL 执行 API 命令，并返回文本响应（带超时，防阻塞）"""
        if not self.inbound:
            raise Exception("Inbound 未初始化")
        response = await asyncio.wait_for(self.inbound.send(f"api {command}"), timeout=timeout_seconds)
        body = getattr(response, 'body', None)
        if body is not None:
            return body
        # 某些响应可能在 Reply-Text
        return response.get("Reply-Text", "")

    async def gateway_is_up(self, gateway_name: str = "ucm_trunk") -> bool:
        """检查 Sofia 网关是否可用（非 DOWN）。"""
        try:
            status = await self.api(f"sofia status gateway {gateway_name}")
            logger.debug(f"网关状态[{gateway_name}]:\n{status}")
            # 更稳健：排除包含 DOWN/INVALID/NOT FOUND 等文本
            upper = status.upper() if isinstance(status, str) else ""
            if any(x in upper for x in ["DOWN", "INVALID", "NOT FOUND", "NO SUCH GATEWAY", "UNDEFINED"]):
                return False
            return True
        except Exception as e:
            logger.warning(f"查询网关状态失败[{gateway_name}]: {e}")
            return False
    
    
    async def handle_channel_create(self, event_data):
        """处理通道创建事件"""
        call_uuid = event_data.get("Unique-ID")
        caller_id = event_data.get("Caller-Caller-ID-Number")
        callee_id = event_data.get("Caller-Destination-Number")
        direction = (
            event_data.get("Call-Direction")
            or event_data.get("variable_direction")
            or event_data.get("Caller-Direction")
            or "unknown"
        )
        
        if call_uuid:
            active_calls[call_uuid] = {
                "status": "ringing",
                "caller_id": caller_id,
                "callee_id": callee_id,
                "start_time": datetime.now().isoformat(),
                "call_uuid": call_uuid
            }
            
            call_recordings[call_uuid] = []
            
            if str(direction).lower() == "outbound":
                logger.info(f"外呼通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
                print(f"📤 外呼通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
            else:
                logger.info(f"来电通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
                print(f"📞 来电通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
            
            # 也可能是我们发起的外呼，origination_uuid == call_uuid
            # 不做特别处理，这里只记录状态
    
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
            
            # 开始音频播放（如果有上传的音频则优先播放上传的音频）
            await self.start_audio_playback(call_uuid)
    
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
            
            # 停止 FreeSWITCH 端的音频流
            try:
                await self.stop_call_audio_stream(call_uuid)
            except Exception as _e:
                logger.warning(f"停止 FreeSWITCH 音频流失败（可忽略）: {_e}")

            # 停止音频流
            await self.audio_manager.stop_audio_stream(call_uuid)
            
            # 保存录音
            if call_uuid in call_recordings and call_recordings[call_uuid]:
                await self.save_recording(call_uuid, call_recordings[call_uuid])
            
            logger.info(f"通话结束: {call_uuid}, 时长: {duration}秒")
            print(f"📴 通话结束: {call_uuid}, 时长: {duration}秒")
            
            # 清理上载音频文件映射（保留文件本体以便复查；如需自动删除，可在此删除）
            call_audio_files.pop(call_uuid, None)
    
    async def start_audio_stream_and_playback(self, call_uuid: str):
        """开始音频流和播放"""
        try:
            # 1. 启动音频流到 WebSocket（FreeSWITCH -> MVP）
            await self.start_call_audio_stream(call_uuid)
            
            logger.info(f"音频流已启动（WebSocket 推流）: {call_uuid}")
            print(f"🎵 音频流已启动（WebSocket 推流）: {call_uuid}")
            
        except Exception as e:
            logger.error(f"启动音频流和播放失败: {e}")
    
    async def start_call_audio_stream(self, call_uuid: str):
        """通过 ESL 命令启动 FreeSWITCH 到本服务的音频流"""
        stream_url = f"ws://{config.config.AUDIO_WS_HOST}:{config.config.AUDIO_WS_PORT}/audio/{call_uuid}"
        command = f"uuid_audio_stream {call_uuid} start {stream_url}"
        logger.info(f"启动 FreeSWITCH 音频流: {command}")
        print(f"📡 启动 FreeSWITCH 音频流: {command}")
        await self.api(command)
    
    async def uuid_exists(self, call_uuid: str) -> bool:
        """检查通话 UUID 是否仍然存在（避免对已销毁会话下发命令）"""
        try:
            res = await self.api(f"uuid_exists {call_uuid}")
            if isinstance(res, str) and res.strip().lower().startswith("true"):
                return True
            return False
        except Exception:
            return False

    async def stop_call_audio_stream(self, call_uuid: str):
        """停止 FreeSWITCH 到本服务的音频流"""
        # 若会话已不存在则跳过
        if not await self.uuid_exists(call_uuid):
            logger.info(f"通道已不存在，跳过停止音频流: {call_uuid}")
            return
        command = f"uuid_audio_stream {call_uuid} stop"
        logger.info(f"停止 FreeSWITCH 音频流: {command}")
        print(f"⏹️  停止 FreeSWITCH 音频流: {command}")
        try:
            await self.api(command)
        except Exception:
            # 通道可能已销毁，忽略错误
            pass
    
    async def start_audio_playback(self, call_uuid: str):
        """开始播放音频"""
        try:
            # 优先播放上传的文件
            upload_path = call_audio_files.get(call_uuid)
            if upload_path and os.path.exists(upload_path):
                # 将 MVP 容器路径映射到 FreeSWITCH 容器可见路径
                # 这里假定两容器共享卷 /shared 映射到 FreeSWITCH 的 /var/lib/freeswitch 之下
                # 示例：/shared/recordings/xxx.wav -> /var/lib/freeswitch/recordings/xxx.wav
                try:
                    rel_path = os.path.relpath(upload_path, "/shared")
                except Exception:
                    rel_path = os.path.basename(upload_path)
                fs_audio_file = f"/var/lib/freeswitch/{rel_path}".replace("\\", "/")
            else:
                # 回退到示例文件
                mvp_audio_file = "/app/wav-example.wav"
                fs_audio_file = "/var/lib/freeswitch/recordings/wav-example.wav"
                if not os.path.exists(mvp_audio_file):
                    logger.warning(f"音频文件不存在: {mvp_audio_file}")
                    return

            # 使用 FreeSWITCH 播放音频到当前通道
            play_command = f"uuid_broadcast {call_uuid} {fs_audio_file} aleg"
            await self.api(play_command)
            logger.info(f"开始播放音频: {call_uuid} -> {fs_audio_file}")
            print(f"🎵 开始播放音频: {call_uuid} -> {fs_audio_file}")
                
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
    
    async def make_outbound_call(self, phone_number: str, caller_id: str = None, origination_uuid: Optional[str] = None, dial_prefix: Optional[str] = None):
        """发起外呼"""
        try:
            if not self.connected:
                raise Exception("未连接到 FreeSWITCH")
            
            # 构建外呼命令
            uuid_kv = f",origination_uuid={origination_uuid}" if origination_uuid else ""
            number_to_dial = f"{(dial_prefix or '')}{phone_number}"
            
            # 特殊测试号码处理
            if number_to_dial == "9999":
                call_route = "loopback/9999/default"
            elif number_to_dial in ["1000", "1002", "1003", "6001"]:
                call_route = f"loopback/{number_to_dial}/default"
            else:
                # 通过已配置的网关 ucm_trunk 外呼；若网关不可用，则回退直拨 UCM IP
                if await self.gateway_is_up("ucm_trunk"):
                    call_route = f"sofia/gateway/ucm_trunk/{number_to_dial}"
                else:
                    call_route = f"sofia/internal/{number_to_dial}@{config.config.UCM_IP}:5060"

            
            call_command = f"originate {{origination_caller_id_number={caller_id or '1000'}{uuid_kv}}}{call_route} &park"

            logger.info(f"外呼路由: {call_route}")
            logger.debug(f"外呼命令: {call_command}")
            
            # 执行外呼
            result = await self.api(call_command)
            
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
            result = await self.api(answer_command)
            
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
            result = await self.api(hangup_command)
            
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
    inbound_is_connected = False
    if fs_manager.inbound:
        inbound_is_connected = bool(
            getattr(fs_manager.inbound, "is_connected", None)
            or getattr(fs_manager.inbound, "connected", None)
            or getattr(fs_manager.inbound, "ready", None)
            or getattr(fs_manager.inbound, "_connected", None)
        )

    overall_connected = bool(fs_manager.connected or inbound_is_connected)

    connection_info = {
        "status": "ok",
        "freeswitch_connected": overall_connected,
        "fs_host": FS_HOST,
        "fs_port": FS_PORT,
        "fs_password_set": bool(FS_PASSWORD),
        "active_calls": len(active_calls),
        "audio_streams": len(fs_manager.audio_manager.websocket_connections),
        "consumer_connected": fs_manager.consumer is not None,
        "inbound_connected": inbound_is_connected
    }
    
    # 如果连接失败，尝试重新连接
    if not overall_connected:
        asyncio.create_task(fs_manager.connect())
    
    return connection_info

@app.get("/test-connection")
async def test_connection():
    """测试 FreeSWITCH 连接"""
    try:
        if fs_manager.connected:
            # 尝试执行一个简单的 API 命令来测试连接
            result = await fs_manager.api("version")
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

@app.post("/call/outbound")
async def make_call(
    phone_number: Optional[str] = Form(None),
    caller_id: Optional[str] = Form(None),
    dial_prefix: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None)
):
    """发起外呼（表单+文件）
    - Content-Type: multipart/form-data
    - 表单字段：`phone_number`、`caller_id`、`dial_prefix`
    - 可选文件字段：`audio_file`（wav/mp3）。若提供则通话接通后优先播放该音频
    """

    if not phone_number:
        raise HTTPException(status_code=422, detail="phone_number 必填")

    saved_audio_path: Optional[str] = None
    if audio_file is not None:
        content_type = (audio_file.content_type or "").lower()
        allowed_mp3 = {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mpeg-3"}
        allowed_wav = {"audio/wav", "audio/x-wav", "audio/wave"}

        file_ext: Optional[str] = None
        if content_type in allowed_wav:
            file_ext = "wav"
        elif content_type in allowed_mp3:
            file_ext = "mp3"
        else:
            # 回退使用文件名判定
            lower_name = (audio_file.filename or "").lower()
            if lower_name.endswith(".wav"):
                file_ext = "wav"
            elif lower_name.endswith(".mp3"):
                file_ext = "mp3"

        if file_ext not in {"wav", "mp3"}:
            raise HTTPException(status_code=400, detail="仅支持 wav 或 mp3 音频文件")

        # 保存到共享目录（FreeSWITCH 可见）
        os.makedirs(config.config.UPLOAD_DIR, exist_ok=True)
        unique_id = str(uuid.uuid4())
        filename = f"outbound_{unique_id}.{file_ext}"
        saved_audio_path = os.path.join(config.config.UPLOAD_DIR, filename)

        try:
            async with aiofiles.open(saved_audio_path, "wb") as f:
                while True:
                    chunk = await audio_file.read(1024 * 1024)
                    if not chunk:
                        break
                    await f.write(chunk)
        finally:
            try:
                await audio_file.close()
            except Exception:
                pass

    # 总是指定 origination_uuid，便于事件中直接按 UUID 取回上传音频
    origination_uuid = str(uuid.uuid4())
    if saved_audio_path:
        call_audio_files[origination_uuid] = saved_audio_path

    return await fs_manager.make_outbound_call(
        phone_number=phone_number,
        caller_id=caller_id,
        origination_uuid=origination_uuid,
        dial_prefix=dial_prefix
    )

@app.post("/call/outbound-json")
async def make_call_json(call_request: CallRequest):
    """发起外呼（JSON）
    - Content-Type: application/json
    - Body: CallRequest
    - 不支持上传音频文件，按系统默认音频播放
    """
    return await fs_manager.make_outbound_call(
        phone_number=call_request.phone_number,
        caller_id=call_request.caller_id,
        origination_uuid=None,
        dial_prefix=call_request.dial_prefix
    )

@app.get("/call/status")
async def get_call_status():
    """获取所有通话状态"""
    return {
        "active_calls": len(active_calls),
        "calls": [
            {
                "call_uuid": call_uuid,
                "status": call_info.get("status"),
                "caller_id": call_info.get("caller_id"),
                "callee_id": call_info.get("callee_id"),
                "start_time": call_info.get("start_time"),
                "answer_time": call_info.get("answer_time"),
                "duration": call_info.get("duration")
            }
            for call_uuid, call_info in active_calls.items()
        ]
    }

@app.get("/call/{call_uuid}/status")
async def get_call_status_by_uuid(call_uuid: str):
    """获取指定通话状态"""
    if call_uuid not in active_calls:
        raise HTTPException(status_code=404, detail="通话不存在")
    
    call_info = active_calls[call_uuid]
    return {
        "call_uuid": call_uuid,
        "status": call_info.get("status"),
        "caller_id": call_info.get("caller_id"),
        "callee_id": call_info.get("callee_id"),
        "start_time": call_info.get("start_time"),
        "answer_time": call_info.get("answer_time"),
        "duration": call_info.get("duration")
    }

@app.post("/call/{call_uuid}/answer")
async def answer_call(call_uuid: str):
    """接听来电"""
    return await fs_manager.answer_call(call_uuid)

@app.post("/call/{call_uuid}/hangup")
async def hangup_call(call_uuid: str):
    """挂断通话"""
    return await fs_manager.hangup_call(call_uuid)



if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False) 
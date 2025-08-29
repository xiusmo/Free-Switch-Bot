import asyncio
import base64
import json
import logging
import time
import uuid
from typing import Optional, Dict, Callable, List
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
from . import config

logger = logging.getLogger(__name__)

class QwenOmniClient:
    """Qwen-Omni实时API客户端"""
    
    def __init__(self, call_uuid: str):
        self.call_uuid = call_uuid
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.session_id: str = str(uuid.uuid4())
        self.is_connected = False
        self.audio_queue = asyncio.Queue()
        self.response_queue = asyncio.Queue()
        
        # 回调函数
        self.on_audio_response: Optional[Callable[[bytes], None]] = None
        self.on_text_response: Optional[Callable[[str], None]] = None
        self.on_speech_started: Optional[Callable[[], None]] = None
        self.on_speech_stopped: Optional[Callable[[], None]] = None
        
        # 任务管理
        self.tasks: List[asyncio.Task] = []
        self._closing = False
        
    async def connect(self) -> bool:
        """连接到Qwen-Omni WebSocket API"""
        try:
            if not config.config.QWEN_OMNI_API_KEY:
                logger.error("Qwen-Omni API Key未配置")
                return False
                
            # 根据DashScope标准格式构建WebSocket URL
            websocket_url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen-omni-turbo-realtime"
            
            headers = {
                "Authorization": f"Bearer {config.config.QWEN_OMNI_API_KEY}",
                "X-DashScope-WorkSpace": "default"
            }
            
            logger.info(f"连接到Qwen-Omni API: {websocket_url}")
            logger.debug(f"API Key前缀: {config.config.QWEN_OMNI_API_KEY[:10]}...")
            
            self.websocket = await websockets.connect(
                websocket_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            logger.info(f"Qwen-Omni WebSocket连接成功: {self.call_uuid}")
            
            # 启动处理任务
            self.tasks = [
                asyncio.create_task(self._send_loop()),
                asyncio.create_task(self._receive_loop())
            ]
            
            # 初始化会话
            await self._initialize_session()
            
            return True
            
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"Qwen-Omni API认证失败 (状态码: {e.status_code}): 请检查API Key是否有效")
            self.is_connected = False
            return False
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"Qwen-Omni WebSocket连接错误: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"连接Qwen-Omni失败: {type(e).__name__}: {e}")
            self.is_connected = False
            return False
    
    async def _initialize_session(self):
        """初始化Qwen-Omni会话"""
        session_config = {
            "type": "session.update",
            "session": {
                "model": config.config.QWEN_OMNI_MODEL,
                "voice": config.config.QWEN_OMNI_VOICE,
                "language": config.config.QWEN_OMNI_LANGUAGE,
                "turn_detection": {
                    "type": "server_vad" if config.config.QWEN_OMNI_VAD_MODE else "none",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "instructions": "你是一个智能语音助手，请用简洁友好的语调回答用户问题。",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        
        await self.websocket.send(json.dumps(session_config))
        logger.info(f"Qwen-Omni会话初始化完成: {self.call_uuid}")
    
    async def _send_loop(self):
        """发送循环 - 处理音频队列中的数据"""
        try:
            while not self._closing and self.is_connected:
                try:
                    # 等待音频数据
                    audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
                    
                    if audio_data is None:  # 停止信号
                        break
                        
                    # 发送音频数据到Qwen-Omni
                    audio_event = {
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(audio_data).decode('utf-8')
                    }
                    
                    await self.websocket.send(json.dumps(audio_event))
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"发送音频数据失败: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"发送循环异常: {e}")
        finally:
            logger.info(f"发送循环结束: {self.call_uuid}")
    
    async def _receive_loop(self):
        """接收循环 - 处理来自Qwen-Omni的响应"""
        try:
            while not self._closing and self.is_connected:
                try:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    await self._handle_response(data)
                    
                except ConnectionClosed:
                    logger.info(f"Qwen-Omni连接已关闭: {self.call_uuid}")
                    break
                except Exception as e:
                    logger.error(f"接收消息失败: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"接收循环异常: {e}")
        finally:
            self.is_connected = False
            logger.info(f"接收循环结束: {self.call_uuid}")
    
    async def _handle_response(self, data: dict):
        """处理Qwen-Omni响应"""
        event_type = data.get("type", "")
        
        try:
            if event_type == "session.created":
                logger.info(f"Qwen-Omni会话已创建: {self.call_uuid}")
                
            elif event_type == "session.updated":
                logger.info(f"Qwen-Omni会话已更新: {self.call_uuid}")
                
            elif event_type == "input_audio_buffer.speech_started":
                logger.debug(f"检测到语音开始: {self.call_uuid}")
                if self.on_speech_started:
                    self.on_speech_started()
                    
            elif event_type == "input_audio_buffer.speech_stopped":
                logger.debug(f"检测到语音结束: {self.call_uuid}")
                if self.on_speech_stopped:
                    self.on_speech_stopped()
                    
            elif event_type == "response.audio.delta":
                # 接收到音频响应数据
                audio_data = data.get("delta", "")
                if audio_data and self.on_audio_response:
                    audio_bytes = base64.b64decode(audio_data)
                    self.on_audio_response(audio_bytes)
                    
            elif event_type == "response.audio_transcript.delta":
                # 接收到文本转录
                text = data.get("delta", "")
                if text and self.on_text_response:
                    self.on_text_response(text)
                    
            elif event_type == "response.audio_transcript.done":
                logger.debug(f"音频转录完成: {self.call_uuid}")
                
            elif event_type == "response.audio.done":
                logger.debug(f"音频响应完成: {self.call_uuid}")
                
            elif event_type == "response.done":
                logger.debug(f"响应完成: {self.call_uuid}")
                
            elif event_type == "error":
                error_msg = data.get("error", {}).get("message", "未知错误")
                logger.error(f"Qwen-Omni错误: {error_msg}")
                
            else:
                logger.debug(f"未处理的事件类型: {event_type}")
                
        except Exception as e:
            logger.error(f"处理响应事件失败: {e}")
    
    async def send_audio(self, audio_data: bytes):
        """发送音频数据到Qwen-Omni"""
        if not self.is_connected:
            logger.warning(f"未连接到Qwen-Omni: {self.call_uuid}")
            return
            
        try:
            await self.audio_queue.put(audio_data)
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}")
    
    async def commit_audio_buffer(self):
        """提交音频缓冲区（Manual模式使用）"""
        if not self.is_connected:
            return
            
        try:
            commit_event = {
                "type": "input_audio_buffer.commit"
            }
            await self.websocket.send(json.dumps(commit_event))
            logger.debug(f"音频缓冲区已提交: {self.call_uuid}")
            
        except Exception as e:
            logger.error(f"提交音频缓冲区失败: {e}")
    
    async def send_text(self, text: str):
        """发送文本消息到Qwen-Omni"""
        if not self.is_connected:
            return
            
        try:
            text_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": text
                        }
                    ]
                }
            }
            await self.websocket.send(json.dumps(text_event))
            
            # 创建响应
            response_event = {
                "type": "response.create"
            }
            await self.websocket.send(json.dumps(response_event))
            
        except Exception as e:
            logger.error(f"发送文本消息失败: {e}")
    
    async def close(self):
        """关闭连接"""
        self._closing = True
        
        # 发送停止信号
        if self.audio_queue:
            try:
                await self.audio_queue.put(None)
            except:
                pass
        
        # 取消所有任务
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # 等待任务完成
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # 关闭WebSocket连接
        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.close()
            except:
                pass
        
        self.is_connected = False
        logger.info(f"Qwen-Omni连接已关闭: {self.call_uuid}")


class QwenOmniAudioProcessor:
    """Qwen-Omni音频处理器 - 整合音频流处理逻辑"""
    
    def __init__(self, call_uuid: str):
        self.call_uuid = call_uuid
        self.qwen_client: Optional[QwenOmniClient] = None
        self.audio_buffer: List[bytes] = []
        self.is_active = False
        
        # 音频格式转换参数
        self.sample_rate = config.config.AUDIO_SAMPLE_RATE  # 8000Hz
        self.channels = config.config.AUDIO_CHANNELS       # 1 (mono)
        self.sample_width = 2                              # 16-bit
        
        # 回调函数
        self.on_ai_audio: Optional[Callable[[bytes], None]] = None
        
    async def start(self) -> bool:
        """启动AI音频处理"""
        if not config.config.QWEN_OMNI_ENABLED or not config.config.QWEN_OMNI_API_KEY:
            logger.info(f"Qwen-Omni未启用或API Key未配置: {self.call_uuid}")
            return False
            
        try:
            self.qwen_client = QwenOmniClient(self.call_uuid)
            
            # 设置回调函数
            self.qwen_client.on_audio_response = self._on_ai_audio_response
            self.qwen_client.on_text_response = self._on_ai_text_response
            self.qwen_client.on_speech_started = self._on_speech_started
            self.qwen_client.on_speech_stopped = self._on_speech_stopped
            
            # 连接到Qwen-Omni
            success = await self.qwen_client.connect()
            if success:
                self.is_active = True
                logger.info(f"AI音频处理已启动: {self.call_uuid}")
                return True
            else:
                logger.error(f"AI音频处理启动失败: {self.call_uuid}")
                return False
                
        except Exception as e:
            logger.error(f"启动AI音频处理异常: {e}")
            return False
    
    async def process_incoming_audio(self, audio_data: bytes):
        """处理来自FreeSWITCH的音频数据"""
        if not self.is_active or not self.qwen_client:
            return
            
        try:
            # 发送音频到Qwen-Omni进行处理
            await self.qwen_client.send_audio(audio_data)
            
        except Exception as e:
            logger.error(f"处理输入音频失败: {e}")
    
    def _on_ai_audio_response(self, audio_data: bytes):
        """处理AI音频响应"""
        try:
            if self.on_ai_audio and audio_data:
                self.on_ai_audio(audio_data)
                
        except Exception as e:
            logger.error(f"处理AI音频响应失败: {e}")
    
    def _on_ai_text_response(self, text: str):
        """处理AI文本响应"""
        logger.info(f"AI响应文本[{self.call_uuid}]: {text}")
    
    def _on_speech_started(self):
        """语音开始检测"""
        logger.debug(f"用户开始说话: {self.call_uuid}")
    
    def _on_speech_stopped(self):
        """语音结束检测"""
        logger.debug(f"用户停止说话: {self.call_uuid}")
    
    async def stop(self):
        """停止AI音频处理"""
        self.is_active = False
        
        if self.qwen_client:
            await self.qwen_client.close()
            self.qwen_client = None
            
        logger.info(f"AI音频处理已停止: {self.call_uuid}")

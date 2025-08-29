"""
WebSocket Proxy
WebSocket代理 - 处理MVP和RealtimeVoiceChat之间的WebSocket连接和消息转发
"""
import asyncio
import json
import logging
import websockets
from typing import Optional
from websockets.exceptions import ConnectionClosed, WebSocketException

from .config import config
from .session_manager import session_manager, SessionState
from .audio_converter import AudioConverter

logger = logging.getLogger(__name__)

class WebSocketProxy:
    """WebSocket代理类"""
    
    def __init__(self):
        """初始化WebSocket代理"""
        self.audio_converter = AudioConverter()
        logger.info("🌐 WebSocket代理初始化完成")
    
    async def start_bridge_session(self, call_uuid: str, phone_number: Optional[str] = None):
        """启动音频桥接会话
        
        Args:
            call_uuid: FreeSWITCH通话UUID
            phone_number: 电话号码
            
        Returns:
            会话对象
        """
        try:
            # 创建会话
            session = session_manager.create_session(call_uuid, phone_number)
            
            # 更新状态为连接中
            session_manager.update_session_state(session.session_id, SessionState.CONNECTING)
            
            logger.info(f"🚀 启动桥接会话: {session.session_id} (Call: {call_uuid})")
            
            # 启动连接任务
            mvp_task = asyncio.create_task(
                self._connect_to_mvp(session.session_id, call_uuid)
            )
            rtvc_task = asyncio.create_task(
                self._connect_to_rtvc(session.session_id)
            )
            
            # 等待连接建立
            await asyncio.gather(mvp_task, rtvc_task, return_exceptions=True)
            
            # 检查连接状态
            if session.mvp_ws and session.rtvc_ws:
                session_manager.update_session_state(session.session_id, SessionState.ACTIVE)
                logger.info(f"✅ 桥接会话连接成功: {session.session_id}")
                
                # 启动音频转发任务
                asyncio.create_task(self._handle_session(session.session_id))
                
            else:
                session_manager.update_session_state(session.session_id, SessionState.ERROR)
                logger.error(f"❌ 桥接会话连接失败: {session.session_id}")
                
            return session
            
        except Exception as e:
            logger.error(f"启动桥接会话失败: {e}")
            if 'session' in locals():
                session_manager.close_session(session.session_id, f"启动失败: {e}")
            raise
    
    async def _connect_to_mvp(self, session_id: str, call_uuid: str):
        """连接到MVP WebSocket"""
        try:
            mvp_url = f"ws://{config.MVP_WS_HOST}:{config.MVP_WS_PORT}/audio/{call_uuid}"
            logger.info(f"🔗 连接MVP: {mvp_url}")
            
            mvp_ws = await websockets.connect(
                mvp_url,
                ping_interval=config.WS_PING_INTERVAL,
                ping_timeout=config.WS_PING_TIMEOUT,
                max_size=config.WS_MAX_SIZE
            )
            
            session_manager.set_mvp_connection(session_id, mvp_ws)
            logger.info(f"✅ MVP连接成功: {session_id}")
            
        except Exception as e:
            logger.error(f"MVP连接失败: {e}")
            session = session_manager.get_session(session_id)
            if session:
                session.add_error(f"MVP连接失败: {e}")
            raise
    
    async def _connect_to_rtvc(self, session_id: str):
        """连接到RealtimeVoiceChat WebSocket"""
        try:
            rtvc_url = f"ws://{config.RTVC_WS_HOST}:{config.RTVC_WS_PORT}/ws"
            logger.info(f"🔗 连接RTVC: {rtvc_url}")
            
            rtvc_ws = await websockets.connect(
                rtvc_url,
                ping_interval=config.WS_PING_INTERVAL,
                ping_timeout=config.WS_PING_TIMEOUT,
                max_size=config.WS_MAX_SIZE
            )
            
            session_manager.set_rtvc_connection(session_id, rtvc_ws)
            logger.info(f"✅ RTVC连接成功: {session_id}")
            
        except Exception as e:
            logger.error(f"RTVC连接失败: {e}")
            session = session_manager.get_session(session_id)
            if session:
                session.add_error(f"RTVC连接失败: {e}")
            raise
    
    async def _handle_session(self, session_id: str):
        """处理会话的双向音频转发"""
        session = session_manager.get_session(session_id)
        if not session or not session.mvp_ws or not session.rtvc_ws:
            logger.error(f"会话或连接无效: {session_id}")
            return
        
        logger.info(f"🔄 开始音频转发: {session_id}")
        
        try:
            # 创建双向转发任务
            mvp_to_rtvc_task = asyncio.create_task(
                self._forward_mvp_to_rtvc(session_id)
            )
            rtvc_to_mvp_task = asyncio.create_task(
                self._forward_rtvc_to_mvp(session_id)
            )
            
            # 等待任务完成或异常
            done, pending = await asyncio.wait(
                [mvp_to_rtvc_task, rtvc_to_mvp_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消待完成的任务
            for task in pending:
                task.cancel()
                
            # 检查异常
            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(f"音频转发任务异常: {e}")
                    
        except Exception as e:
            logger.error(f"处理会话异常: {e}")
        finally:
            session_manager.close_session(session_id, "音频转发结束")
    
    async def _forward_mvp_to_rtvc(self, session_id: str):
        """转发MVP音频到RTVC (8kHz -> 48kHz)"""
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        logger.info(f"📤 MVP->RTVC 音频转发开始: {session_id}")
        
        try:
            async for message in session.mvp_ws:
                if isinstance(message, bytes):
                    # 处理音频数据
                    await self._process_mvp_audio(session_id, message)
                elif isinstance(message, str):
                    # 处理控制消息
                    await self._process_mvp_control(session_id, message)
                    
        except ConnectionClosed:
            logger.info(f"MVP连接关闭: {session_id}")
        except Exception as e:
            logger.error(f"MVP音频转发异常: {e}")
            session.add_error(f"MVP转发异常: {e}")
    
    async def _forward_rtvc_to_mvp(self, session_id: str):
        """转发RTVC音频到MVP (48kHz -> 8kHz)"""
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        logger.info(f"📤 RTVC->MVP 音频转发开始: {session_id}")
        
        try:
            async for message in session.rtvc_ws:
                if isinstance(message, bytes):
                    # 处理音频数据
                    await self._process_rtvc_audio(session_id, message)
                elif isinstance(message, str):
                    # 处理控制消息
                    await self._process_rtvc_control(session_id, message)
                    
        except ConnectionClosed:
            logger.info(f"RTVC连接关闭: {session_id}")
        except Exception as e:
            logger.error(f"RTVC音频转发异常: {e}")
            session.add_error(f"RTVC转发异常: {e}")
    
    async def _process_mvp_audio(self, session_id: str, audio_data: bytes):
        """处理MVP音频数据 (8kHz PCM -> RTVC格式)"""
        session = session_manager.get_session(session_id)
        if not session or not session.rtvc_ws:
            return
            
        try:
            # 上采样到16kHz
            upsampled_pcm = self.audio_converter.upsample_8k_to_16k(audio_data)
            if not upsampled_pcm:
                return
                
            # 创建RTVC格式消息
            rtvc_message = self.audio_converter.create_rtvc_audio_message(upsampled_pcm)
            
            # 发送到RTVC
            await session.rtvc_ws.send(rtvc_message)
            
            # 记录统计
            session_manager.record_traffic(session_id, 'to_rtvc', len(rtvc_message))
            
            logger.debug(f"MVP音频转发: {len(audio_data)} -> {len(rtvc_message)} bytes")
            
        except Exception as e:
            logger.error(f"处理MVP音频失败: {e}")
            session.add_error(f"MVP音频处理失败: {e}")
    
    async def _process_rtvc_audio(self, session_id: str, audio_data: bytes):
        """处理RTVC音频数据 (RTVC格式 -> 8kHz PCM)"""
        session = session_manager.get_session(session_id)
        if not session or not session.mvp_ws:
            return
            
        try:
            # 解析RTVC消息
            pcm_16k, timestamp_ms, flags = self.audio_converter.parse_rtvc_audio_message(audio_data)
            if pcm_16k is None:
                return
                
            # 下采样到8kHz
            downsampled_pcm = self.audio_converter.downsample_16k_to_8k(pcm_16k)
            if not downsampled_pcm:
                return
                
            # 发送到MVP
            await session.mvp_ws.send(downsampled_pcm)
            
            # 记录统计
            session_manager.record_traffic(session_id, 'to_mvp', len(downsampled_pcm))
            
            logger.debug(f"RTVC音频转发: {len(audio_data)} -> {len(downsampled_pcm)} bytes")
            
        except Exception as e:
            logger.error(f"处理RTVC音频失败: {e}")
            session.add_error(f"RTVC音频处理失败: {e}")
    
    async def _process_mvp_control(self, session_id: str, message: str):
        """处理MVP控制消息"""
        try:
            logger.debug(f"MVP控制消息: {message}")
            # MVP通常发送二进制音频，控制消息较少
            # 如果需要处理特定控制消息，在此添加逻辑
            
        except Exception as e:
            logger.error(f"处理MVP控制消息失败: {e}")
    
    async def _process_rtvc_control(self, session_id: str, message: str):
        """处理RTVC控制消息"""
        session = session_manager.get_session(session_id)
        if not session:
            return
            
        try:
            # 解析JSON消息
            data = json.loads(message)
            msg_type = data.get("type")
            
            logger.debug(f"RTVC控制消息: {msg_type}")
            
            # 处理不同类型的控制消息
            if msg_type == "tts_chunk":
                # TTS音频块 - 已在二进制处理中处理
                pass
            elif msg_type == "partial_user_request":
                # 部分用户请求
                logger.info(f"用户部分输入: {data.get('content', '')}")
            elif msg_type == "final_user_request":
                # 最终用户请求
                logger.info(f"用户最终输入: {data.get('content', '')}")
            elif msg_type == "partial_assistant_answer":
                # 部分AI回复
                logger.info(f"AI部分回复: {data.get('content', '')}")
            elif msg_type == "final_assistant_answer":
                # 最终AI回复
                logger.info(f"AI最终回复: {data.get('content', '')}")
            elif msg_type in ["tts_start", "tts_stop", "stop_tts", "tts_interruption"]:
                # TTS控制消息
                logger.debug(f"TTS控制: {msg_type}")
            else:
                logger.debug(f"未处理的控制消息类型: {msg_type}")
                
        except json.JSONDecodeError:
            logger.warning(f"无效JSON控制消息: {message}")
        except Exception as e:
            logger.error(f"处理RTVC控制消息失败: {e}")

# 全局WebSocket代理实例
websocket_proxy = WebSocketProxy()

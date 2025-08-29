"""
Session Manager
会话管理器 - 管理音频桥接会话的生命周期
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from .config import config

logger = logging.getLogger(__name__)

class SessionState(Enum):
    """会话状态枚举"""
    IDLE = "idle"
    CONNECTING = "connecting" 
    ACTIVE = "active"
    DISCONNECTING = "disconnecting"
    CLOSED = "closed"
    ERROR = "error"

@dataclass
class BridgeSession:
    """音频桥接会话"""
    # 基础信息
    session_id: str
    call_uuid: str
    phone_number: Optional[str] = None
    
    # 状态信息
    state: SessionState = SessionState.IDLE
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    # 连接信息
    mvp_ws = None  # MVP WebSocket连接
    rtvc_ws = None  # RealtimeVoiceChat WebSocket连接
    
    # 统计信息
    bytes_sent_to_rtvc: int = 0
    bytes_sent_to_mvp: int = 0
    packets_sent_to_rtvc: int = 0  
    packets_sent_to_mvp: int = 0
    
    # 错误信息
    last_error: Optional[str] = None
    error_count: int = 0
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = time.time()
    
    def is_expired(self, timeout_seconds: int) -> bool:
        """检查会话是否过期"""
        return (time.time() - self.last_activity) > timeout_seconds
    
    def add_error(self, error: str):
        """添加错误记录"""
        self.last_error = error
        self.error_count += 1
        logger.warning(f"会话 {self.session_id} 错误: {error} (总计 {self.error_count})")

class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        """初始化会话管理器"""
        self.sessions: Dict[str, BridgeSession] = {}  # session_id -> BridgeSession
        self.call_uuid_to_session: Dict[str, str] = {}  # call_uuid -> session_id
        self.active_sessions: Set[str] = set()
        self._cleanup_task_started = False
        
        logger.info("📋 会话管理器已初始化")
    
    def _ensure_cleanup_task(self):
        """确保清理任务已启动"""
        if not self._cleanup_task_started:
            try:
                asyncio.create_task(self._cleanup_task())
                self._cleanup_task_started = True
                logger.info("🧹 会话清理任务已启动")
            except RuntimeError:
                # 如果没有运行的事件循环，稍后再启动
                pass
    
    def create_session(self, call_uuid: str, phone_number: Optional[str] = None) -> BridgeSession:
        """创建新会话
        
        Args:
            call_uuid: FreeSWITCH通话UUID
            phone_number: 电话号码
            
        Returns:
            创建的会话对象
            
        Raises:
            ValueError: 如果会话已存在或超出最大并发数
        """
        # 确保清理任务已启动
        self._ensure_cleanup_task()
        
        if call_uuid in self.call_uuid_to_session:
            raise ValueError(f"Call UUID {call_uuid} 已存在会话")
            
        if len(self.sessions) >= config.MAX_CONCURRENT_SESSIONS:
            raise ValueError(f"超出最大并发会话数: {config.MAX_CONCURRENT_SESSIONS}")
        
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())
        
        # 创建会话对象
        session = BridgeSession(
            session_id=session_id,
            call_uuid=call_uuid,
            phone_number=phone_number
        )
        
        # 存储会话
        self.sessions[session_id] = session
        self.call_uuid_to_session[call_uuid] = session_id
        
        logger.info(f"📝 创建会话: {session_id} (Call UUID: {call_uuid})")
        return session
    
    def get_session(self, session_id: str) -> Optional[BridgeSession]:
        """根据会话ID获取会话"""
        return self.sessions.get(session_id)
    
    def get_session_by_call_uuid(self, call_uuid: str) -> Optional[BridgeSession]:
        """根据通话UUID获取会话"""
        session_id = self.call_uuid_to_session.get(call_uuid)
        if session_id:
            return self.sessions.get(session_id)
        return None
    
    def update_session_state(self, session_id: str, new_state: SessionState):
        """更新会话状态"""
        session = self.get_session(session_id)
        if session:
            old_state = session.state
            session.state = new_state
            session.update_activity()
            
            # 维护活跃会话集合
            if new_state == SessionState.ACTIVE:
                self.active_sessions.add(session_id)
            elif new_state in (SessionState.CLOSED, SessionState.ERROR):
                self.active_sessions.discard(session_id)
                
            logger.info(f"🔄 会话状态变更: {session_id} {old_state.value} -> {new_state.value}")
    
    def set_mvp_connection(self, session_id: str, websocket):
        """设置MVP WebSocket连接"""
        session = self.get_session(session_id)
        if session:
            session.mvp_ws = websocket
            session.update_activity()
            logger.info(f"🔗 MVP连接已设置: {session_id}")
    
    def set_rtvc_connection(self, session_id: str, websocket):
        """设置RTVC WebSocket连接"""
        session = self.get_session(session_id)
        if session:
            session.rtvc_ws = websocket
            session.update_activity()
            logger.info(f"🔗 RTVC连接已设置: {session_id}")
    
    def record_traffic(self, session_id: str, direction: str, bytes_count: int):
        """记录流量统计
        
        Args:
            session_id: 会话ID
            direction: 'to_rtvc' 或 'to_mvp'
            bytes_count: 字节数
        """
        session = self.get_session(session_id)
        if session:
            session.update_activity()
            if direction == 'to_rtvc':
                session.bytes_sent_to_rtvc += bytes_count
                session.packets_sent_to_rtvc += 1
            elif direction == 'to_mvp':
                session.bytes_sent_to_mvp += bytes_count
                session.packets_sent_to_mvp += 1
    
    def close_session(self, session_id: str, reason: str = "正常关闭"):
        """关闭会话
        
        Args:
            session_id: 会话ID
            reason: 关闭原因
        """
        session = self.get_session(session_id)
        if not session:
            return
            
        logger.info(f"🚪 关闭会话: {session_id}, 原因: {reason}")
        
        # 关闭WebSocket连接
        async def close_connections():
            try:
                if session.mvp_ws:
                    await session.mvp_ws.close()
                if session.rtvc_ws:
                    await session.rtvc_ws.close()
            except Exception as e:
                logger.error(f"关闭连接失败: {e}")
        
        # 创建异步任务关闭连接
        asyncio.create_task(close_connections())
        
        # 更新状态
        session.state = SessionState.CLOSED
        self.active_sessions.discard(session_id)
        
        # 记录统计信息
        duration = time.time() - session.created_at
        logger.info(f"📊 会话统计 {session_id}: "
                   f"持续时间={duration:.1f}s, "
                   f"发送到RTVC={session.bytes_sent_to_rtvc}字节/{session.packets_sent_to_rtvc}包, "
                   f"发送到MVP={session.bytes_sent_to_mvp}字节/{session.packets_sent_to_mvp}包")
    
    def cleanup_session(self, session_id: str):
        """清理会话（从内存中移除）"""
        session = self.sessions.pop(session_id, None)
        if session:
            self.call_uuid_to_session.pop(session.call_uuid, None)
            self.active_sessions.discard(session_id)
            logger.info(f"🗑️  清理会话: {session_id}")
    
    def get_session_stats(self) -> Dict:
        """获取会话统计信息"""
        active_count = len(self.active_sessions)
        total_count = len(self.sessions)
        
        stats = {
            "active_sessions": active_count,
            "total_sessions": total_count,
            "max_sessions": config.MAX_CONCURRENT_SESSIONS,
            "sessions": []
        }
        
        # 添加每个会话的详细信息
        for session_id, session in self.sessions.items():
            session_info = {
                "session_id": session_id,
                "call_uuid": session.call_uuid,
                "phone_number": session.phone_number,
                "state": session.state.value,
                "duration": time.time() - session.created_at,
                "last_activity": time.time() - session.last_activity,
                "bytes_to_rtvc": session.bytes_sent_to_rtvc,
                "bytes_to_mvp": session.bytes_sent_to_mvp,
                "error_count": session.error_count,
                "last_error": session.last_error
            }
            stats["sessions"].append(session_info)
        
        return stats
    
    async def _cleanup_task(self):
        """后台清理任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"清理任务异常: {e}")
    
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired(config.SESSION_TIMEOUT):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.close_session(session_id, "会话超时")
            # 延迟清理，给关闭操作一些时间
            await asyncio.sleep(1)
            self.cleanup_session(session_id)
        
        if expired_sessions:
            logger.info(f"🧹 清理了 {len(expired_sessions)} 个过期会话")

# 全局会话管理器实例
session_manager = SessionManager()

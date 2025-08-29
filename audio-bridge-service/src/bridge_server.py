"""
Audio Bridge Server
音频桥接服务器 - 主服务入口点
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn

from .config import config
from .session_manager import session_manager, SessionState
from .websocket_proxy import websocket_proxy

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件
    logger.info("🚀 音频桥接服务启动")
    logger.info(f"📊 最大并发会话数: {config.MAX_CONCURRENT_SESSIONS}")
    logger.info(f"⏱️  会话超时: {config.SESSION_TIMEOUT}秒")
    
    # 确保会话清理任务启动
    session_manager._ensure_cleanup_task()
    
    # 安装信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    yield
    
    # 关闭事件
    logger.info("🛑 音频桥接服务关闭")
    
    # 关闭所有活跃会话
    active_sessions = list(session_manager.active_sessions)
    for session_id in active_sessions:
        session_manager.close_session(session_id, "服务关闭")
    
    logger.info(f"🧹 已关闭 {len(active_sessions)} 个活跃会话")

def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"接收到信号 {signum}，准备关闭服务...")
    sys.exit(0)

# FastAPI应用
app = FastAPI(
    title="Audio Bridge Service",
    description="连接MVP FreeSWITCH系统和RealtimeVoiceChat AI系统的音频桥接服务",
    version="1.0.0",
    lifespan=lifespan
)

# API数据模型
class BridgeRequest(BaseModel):
    """桥接请求模型"""
    call_uuid: str
    phone_number: Optional[str] = None

class BridgeResponse(BaseModel):
    """桥接响应模型"""
    success: bool
    session_id: Optional[str] = None
    message: str

class SessionInfo(BaseModel):
    """会话信息模型"""
    session_id: str
    call_uuid: str
    phone_number: Optional[str]
    state: str
    duration: float
    bytes_to_rtvc: int
    bytes_to_mvp: int
    error_count: int

@app.get("/")
async def root():
    """根路径 - 服务基本信息"""
    return {
        "service": "Audio Bridge Service",
        "version": "1.0.0",
        "status": "running",
        "config": {
            "mvp_host": config.MVP_WS_HOST,
            "mvp_port": config.MVP_WS_PORT,
            "rtvc_host": config.RTVC_WS_HOST,
            "rtvc_port": config.RTVC_WS_PORT,
            "max_sessions": config.MAX_CONCURRENT_SESSIONS
        }
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    stats = session_manager.get_session_stats()
    
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "sessions": {
            "active": stats["active_sessions"],
            "total": stats["total_sessions"],
            "max": stats["max_sessions"]
        },
        "audio_conversion": {
            "freeswitch_sample_rate": config.FREESWITCH_SAMPLE_RATE,
            "rtvc_sample_rate": config.RTVC_SAMPLE_RATE,
            "channels": config.AUDIO_CHANNELS
        }
    }

@app.post("/bridge/start", response_model=BridgeResponse)
async def start_bridge(request: BridgeRequest):
    """启动音频桥接会话
    
    Args:
        request: 桥接请求，包含call_uuid和可选的phone_number
        
    Returns:
        桥接响应，包含会话ID和状态
    """
    try:
        logger.info(f"📞 收到桥接请求: {request.call_uuid}")
        
        # 检查会话是否已存在
        existing_session = session_manager.get_session_by_call_uuid(request.call_uuid)
        if existing_session:
            if existing_session.state in (SessionState.ACTIVE, SessionState.CONNECTING):
                return BridgeResponse(
                    success=True,
                    session_id=existing_session.session_id,
                    message="会话已存在"
                )
            else:
                # 清理旧会话
                session_manager.cleanup_session(existing_session.session_id)
        
        # 启动新的桥接会话
        session = await websocket_proxy.start_bridge_session(
            call_uuid=request.call_uuid,
            phone_number=request.phone_number
        )
        
        return BridgeResponse(
            success=True,
            session_id=session.session_id,
            message="桥接会话启动成功"
        )
        
    except ValueError as e:
        logger.warning(f"启动桥接失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"启动桥接异常: {e}")
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {e}")

@app.post("/bridge/stop")
async def stop_bridge(call_uuid: str):
    """停止音频桥接会话
    
    Args:
        call_uuid: FreeSWITCH通话UUID
        
    Returns:
        操作结果
    """
    try:
        session = session_manager.get_session_by_call_uuid(call_uuid)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        session_manager.close_session(session.session_id, "手动停止")
        
        return {
            "success": True,
            "message": f"会话 {session.session_id} 已停止"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止桥接异常: {e}")
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {e}")

@app.get("/sessions")
async def list_sessions():
    """获取所有会话列表"""
    stats = session_manager.get_session_stats()
    return stats

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取特定会话的详细信息
    
    Args:
        session_id: 会话ID
        
    Returns:
        会话详细信息
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    import time
    return {
        "session_id": session.session_id,
        "call_uuid": session.call_uuid,
        "phone_number": session.phone_number,
        "state": session.state.value,
        "created_at": session.created_at,
        "last_activity": session.last_activity,
        "duration": time.time() - session.created_at,
        "idle_time": time.time() - session.last_activity,
        "traffic": {
            "bytes_to_rtvc": session.bytes_sent_to_rtvc,
            "bytes_to_mvp": session.bytes_sent_to_mvp,
            "packets_to_rtvc": session.packets_sent_to_rtvc,
            "packets_to_mvp": session.packets_sent_to_mvp
        },
        "errors": {
            "count": session.error_count,
            "last_error": session.last_error
        },
        "connections": {
            "mvp_connected": session.mvp_ws is not None,
            "rtvc_connected": session.rtvc_ws is not None
        }
    }

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除特定会话
    
    Args:
        session_id: 会话ID
        
    Returns:
        操作结果
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    session_manager.close_session(session_id, "手动删除")
    session_manager.cleanup_session(session_id)
    
    return {
        "success": True,
        "message": f"会话 {session_id} 已删除"
    }

@app.get("/stats")
async def get_stats():
    """获取服务统计信息"""
    stats = session_manager.get_session_stats()
    
    # 计算流量统计
    total_bytes_to_rtvc = sum(s.get("bytes_to_rtvc", 0) for s in stats["sessions"])
    total_bytes_to_mvp = sum(s.get("bytes_to_mvp", 0) for s in stats["sessions"])
    
    return {
        "service": {
            "uptime": asyncio.get_event_loop().time(),
            "status": "running"
        },
        "sessions": {
            "active": stats["active_sessions"],
            "total": stats["total_sessions"],
            "max": stats["max_sessions"]
        },
        "traffic": {
            "total_bytes_to_rtvc": total_bytes_to_rtvc,
            "total_bytes_to_mvp": total_bytes_to_mvp,
            "total_bytes": total_bytes_to_rtvc + total_bytes_to_mvp
        },
        "audio_config": {
            "freeswitch_sample_rate": config.FREESWITCH_SAMPLE_RATE,
            "rtvc_sample_rate": config.RTVC_SAMPLE_RATE,
            "channels": config.AUDIO_CHANNELS,
            "buffer_size": config.AUDIO_BUFFER_SIZE
        }
    }

def main():
    """主函数 - 启动服务"""
    logger.info("🎵 启动音频桥接服务...")
    logger.info(f"🌐 服务地址: {config.BRIDGE_HOST}:{config.BRIDGE_PORT}")
    logger.info(f"🔗 MVP连接: {config.MVP_WS_HOST}:{config.MVP_WS_PORT}")
    logger.info(f"🤖 RTVC连接: {config.RTVC_WS_HOST}:{config.RTVC_WS_PORT}")
    
    uvicorn.run(
        app,
        host=config.BRIDGE_HOST,
        port=config.BRIDGE_PORT,
        log_level=config.LOG_LEVEL.lower(),
        access_log=True
    )

if __name__ == "__main__":
    main()

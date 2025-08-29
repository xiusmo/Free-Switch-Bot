# Audio Bridge Service

这是连接MVP FreeSWITCH系统和RealtimeVoiceChat AI系统的音频桥接服务。

## 功能
- 音频格式转换 (8kHz ↔ 16kHz)
- WebSocket协议适配
- 会话状态管理
- 实时音频流转发

## 架构
```
FreeSWITCH → MVP → Audio Bridge → RealtimeVoiceChat
    ↑                                       ↓
    ←─────── 音频响应流 ←──────────────────────
```

## 端口配置
- 8082: 桥接服务管理端口
- WebSocket客户端连接:
  - MVP: ws://mvp:8081/audio/{call_uuid}
  - RTVC: ws://realtimevoicechat:8000/ws

## 启动方式
```bash
docker-compose up audio-bridge
```

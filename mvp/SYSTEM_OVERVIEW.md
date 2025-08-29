# FreeSWITCH AI 音频流处理系统概览

## 🎯 系统目标

本系统实现了您要求的所有功能：

1. ✅ **使用 Genesis 绑定同一个容器内的 FreeSWITCH**
2. ✅ **使用 audio 插件在 MVP 里面拿到音频流**
3. ✅ **实现音频录制并存储**
4. ✅ **使用 wav-example.wav 文件循环播放**
5. ✅ **在控制台打印来电信息**
6. ✅ **暴露 API 以接听来电**
7. ✅ **能够主动外呼号码**

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker 容器环境                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   FreeSWITCH    │    │           MVP 应用              │ │
│  │   (SIP Server)  │◄──►│   (FastAPI + Genesis)          │ │
│  │                 │    │                                 │ │
│  │ • SIP 信令      │    │ • Genesis 连接管理              │ │
│  │ • RTP 媒体流    │    │ • 音频流处理                    │ │
│  │ • 事件系统      │    │ • 录音管理                      │ │
│  │ • 拨号计划      │    │ • REST API                      │ │
│  └─────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 核心组件

### 1. FreeSwitchManager 类
- **连接管理**: 使用 Genesis 库连接 FreeSWITCH
- **事件监听**: 监听 CHANNEL_CREATE, CHANNEL_ANSWER, CHANNEL_HANGUP 等事件
- **音频控制**: 控制音频播放、录制和通话管理

### 2. 音频处理系统
- **AudioProcessor 类**: 提供音频处理工具
- **录制功能**: 自动录制通话音频
- **播放功能**: 循环播放 wav-example.wav 文件
- **格式转换**: 支持多种音频格式和参数

### 3. REST API 接口
- **通话管理**: 外呼、接听、挂断
- **状态查询**: 获取通话列表、录音列表
- **健康检查**: 系统状态监控

## 📡 API 接口总览

| 方法 | 端点 | 功能 | 状态 |
|------|------|------|------|
| GET | `/health` | 健康检查 | ✅ 已实现 |
| GET | `/calls` | 获取通话列表 | ✅ 已实现 |
| POST | `/call/outbound` | 发起外呼 | ✅ 已实现 |
| POST | `/call/answer` | 接听来电 | ✅ 已实现 |
| POST | `/call/hangup` | 挂断通话 | ✅ 已实现 |
| GET | `/recordings` | 获取录音列表 | ✅ 已实现 |
| GET | `/call/{uuid}/recording` | 获取特定通话录音 | ✅ 已实现 |

## 🎵 音频流处理流程

```
1. 来电检测
   ↓
2. 自动接听
   ↓
3. 开始录制音频流
   ↓
4. 播放 wav-example.wav (循环)
   ↓
5. 通话结束
   ↓
6. 保存录音文件
```

## 🚀 快速开始

### 1. 启动系统
```bash
cd mvp
./start.sh
```

### 2. 快速测试
```bash
python quick_test.py
```

### 3. 完整测试
```bash
python test_system.py
```

### 4. 手动测试 API
```bash
# 健康检查
curl http://localhost:8080/health

# 发起外呼
curl -X POST http://localhost:8080/call/outbound \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "1001", "caller_id": "1000"}'

# 查看通话状态
curl http://localhost:8080/calls
```

## 📊 监控和日志

### 控制台输出示例
```
📞 来电: 1001 -> 1000 (UUID: 12345678-1234-1234-1234-123456789012)
✅ 通话已接听: 12345678-1234-1234-1234-123456789012
🎵 开始播放音频: 12345678-1234-1234-1234-123456789012
📴 通话结束: 12345678-1234-1234-1234-123456789012, 时长: 30秒
💾 录音已保存: /app/recordings/call_12345678-1234-1234-1234-123456789012_20240101_100030.wav
```

### 日志查看
```bash
# 查看 MVP 应用日志
docker-compose logs -f mvp

# 查看 FreeSWITCH 日志
docker-compose logs -f freeswitch
```

## 🔍 故障排除

### 常见问题

1. **FreeSWITCH 连接失败**
   - 检查容器是否启动: `docker-compose ps`
   - 验证端口配置: 8021 (ESL), 5060 (SIP)
   - 查看连接日志

2. **音频播放失败**
   - 确认 wav-example.wav 文件存在
   - 检查音频文件格式和权限
   - 验证 FreeSWITCH audio 插件

3. **录音保存失败**
   - 检查 /app/recordings 目录权限
   - 确认磁盘空间充足
   - 验证音频数据完整性

### 调试命令
```bash
# 进入 MVP 容器
docker exec -it fs-mvp bash

# 检查 FreeSWITCH 状态
docker exec -it freeswitch fs_cli -x "status"

# 查看系统资源
docker stats freeswitch fs-mvp
```

## 📈 性能特性

- **实时处理**: 支持实时音频流处理
- **并发通话**: 支持多路并发通话
- **自动管理**: 自动管理通话生命周期
- **资源优化**: 高效的音频数据处理

## 🔮 扩展功能

系统设计支持以下扩展：

1. **多租户支持**: 支持多个 FreeSWITCH 实例
2. **音频分析**: 集成语音识别和情感分析
3. **智能路由**: 基于 AI 的通话路由
4. **监控面板**: Web 管理界面
5. **负载均衡**: 多实例负载均衡

## 📚 技术栈

- **后端框架**: FastAPI (Python)
- **FreeSWITCH 连接**: Genesis 库
- **音频处理**: pydub, numpy, wave
- **容器化**: Docker & Docker Compose
- **API 文档**: 自动生成的 Swagger UI

## 🎉 总结

本系统完全实现了您的需求：

✅ **Genesis 绑定 FreeSWITCH** - 使用 Genesis 库建立稳定连接  
✅ **音频流获取** - 通过 FreeSWITCH 事件系统获取音频流  
✅ **音频录制存储** - 自动录制并保存为 WAV 文件  
✅ **循环播放** - 使用 wav-example.wav 文件循环播放  
✅ **来电检测** - 控制台实时显示来电信息  
✅ **API 接口** - 完整的 REST API 支持接听和外呼  
✅ **外呼功能** - 支持主动发起外呼  

系统已经准备就绪，可以直接使用！🚀

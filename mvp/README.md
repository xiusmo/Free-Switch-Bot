# FreeSWITCH AI 音频流处理系统

这是一个基于 FreeSWITCH 的完整音频流处理系统，使用 Genesis 库进行连接，支持音频录制、播放、来电检测和外呼功能。

## 功能特性

- 🔗 **FreeSWITCH 集成**: 使用 Genesis 库连接 FreeSWITCH
- 📞 **来电检测**: 自动检测并记录来电信息
- 🎵 **音频播放**: 支持 WAV 文件循环播放
- 💾 **音频录制**: 自动录制通话音频并保存
- 📤 **外呼功能**: 支持主动发起外呼
- 📱 **REST API**: 提供完整的 HTTP API 接口
- 🔍 **实时监控**: 控制台实时显示通话状态

## 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FreeSWITCH    │    │   Genesis       │    │   FastAPI       │
│   (SIP Server)  │◄──►│   (Connection)  │◄──►│   (Web App)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Audio Stream  │    │   Event Bus     │    │   Recording     │
│   (RTP/Media)   │    │   (ESL Events)  │    │   (WAV Files)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 安装和配置

### 1. 环境要求

- Python 3.11+
- FreeSWITCH 1.10+
- Docker & Docker Compose

### 2. 环境变量配置

创建 `.env` 文件并配置以下变量：

```bash
# FreeSWITCH 连接配置
FS_HOST=localhost
FS_PORT=8021
FS_PASSWORD=ClueCon

# 应用配置
PORT=8080
HOST=0.0.0.0
DEBUG=false

# 音频配置
AUDIO_SAMPLE_RATE=8000
AUDIO_CHANNELS=1
AUDIO_BIT_DEPTH=16

# 录音配置
RECORDING_DIR=/app/recordings
MAX_RECORDING_SIZE=100
RECORDING_RETENTION_DAYS=30
```

### 3. 启动系统

```bash
# 启动 FreeSWITCH 和 MVP 服务
docker-compose up -d

# 查看日志
docker-compose logs -f mvp
```

## API 接口

### 健康检查

```http
GET /health
```

响应示例：
```json
{
  "status": "ok",
  "freeswitch_connected": true,
  "active_calls": 2
}
```

### 获取活跃通话

```http
GET /calls
```

响应示例：
```json
[
  {
    "call_uuid": "12345678-1234-1234-1234-123456789012",
    "status": "answered",
    "phone_number": "1001",
    "start_time": "2024-01-01T10:00:00",
    "duration": 30
  }
]
```

### 发起外呼

```http
POST /call/outbound
Content-Type: application/json

{
  "phone_number": "1001",
  "caller_id": "1000"
}
```

### 接听来电

```http
POST /call/answer
Content-Type: application/json

{
  "call_uuid": "12345678-1234-1234-1234-123456789012"
}
```

### 挂断通话

```http
POST /call/hangup
Content-Type: application/json

{
  "call_uuid": "12345678-1234-1234-1234-123456789012"
}
```

### 获取录音列表

```http
GET /recordings
```

### 获取特定通话录音

```http
GET /call/{call_uuid}/recording
```

## 使用示例

### 1. 测试系统功能

```bash
# 运行系统测试
python test_system.py

# 测试特定服务地址
python test_system.py http://localhost:8080
```

### 2. 使用 curl 测试 API

```bash
# 健康检查
curl http://localhost:8080/health

# 发起外呼
curl -X POST http://localhost:8080/call/outbound \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "1001", "caller_id": "1000"}'

# 获取通话列表
curl http://localhost:8080/calls
```

### 3. 监控通话状态

系统会在控制台实时显示通话状态：

```
📞 来电: 1001 -> 1000 (UUID: 12345678-1234-1234-1234-123456789012)
✅ 通话已接听: 12345678-1234-1234-1234-123456789012
🎵 开始播放音频: 12345678-1234-1234-1234-123456789012
📴 通话结束: 12345678-1234-1234-1234-123456789012, 时长: 30秒
💾 录音已保存: /app/recordings/call_12345678-1234-1234-1234-123456789012_20240101_100030.wav
```

## 音频处理

### 音频格式

- **采样率**: 8000 Hz (可配置)
- **声道**: 单声道 (可配置)
- **位深**: 16-bit (可配置)
- **格式**: WAV

### 音频文件

系统使用 `wav-example.wav` 文件作为示例音频，支持：

- 循环播放
- 音量标准化
- 格式转换
- DTMF 音调生成

## 故障排除

### 常见问题

1. **连接 FreeSWITCH 失败**
   - 检查 FreeSWITCH 是否运行
   - 验证端口和密码配置
   - 确认网络连接

2. **音频播放失败**
   - 检查音频文件是否存在
   - 验证文件格式和权限
   - 查看 FreeSWITCH 日志

3. **录音保存失败**
   - 检查录音目录权限
   - 确认磁盘空间
   - 验证音频数据完整性

### 日志查看

```bash
# 查看应用日志
docker-compose logs mvp

# 查看 FreeSWITCH 日志
docker-compose logs freeswitch

# 实时监控日志
docker-compose logs -f mvp
```

## 开发指南

### 项目结构

```
mvp/
├── app/
│   ├── __init__.py
│   ├── main.py          # 主应用文件
│   ├── config.py        # 配置管理
│   └── audio_utils.py   # 音频处理工具
├── Dockerfile           # Docker 镜像配置
├── requirements.txt     # Python 依赖
├── test_system.py      # 系统测试脚本
└── README.md           # 项目文档
```

### 添加新功能

1. 在 `main.py` 中添加新的 API 端点
2. 在 `FreeSwitchManager` 类中实现相关功能
3. 更新测试脚本验证功能
4. 更新文档说明

### 自定义音频处理

使用 `AudioProcessor` 类进行音频处理：

```python
from app.audio_utils import audio_processor

# 创建静音
silence = audio_processor.create_silence(1000)  # 1秒静音

# 标准化音量
normalized = audio_processor.normalize_audio(audio_data, target_db=-20.0)

# 添加 DTMF 音调
with_dtmf = audio_processor.add_dtmf_tones(audio_data, "1234")
```

## 许可证

本项目采用 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过以下方式联系：

- 提交 GitHub Issue
- 发送邮件至项目维护者

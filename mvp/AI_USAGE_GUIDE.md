# AI语音助手外呼系统使用指南

## 🎯 功能概述

本系统将VideoSDK Agents框架的核心代码集成到FreeSWITCH外呼系统中，支持：

- **OpenAI GPT-4o Realtime API** - 实时语音对话
- **Google Gemini Live API** - 多模态语音交互  
- **实时音频流处理** - 双向音频传输
- **智能外呼** - AI驱动的自动外呼系统

## 🚀 快速开始

### 1. 环境准备

```bash
cd mvp

# 复制环境配置文件
cp env.ai.example .env

# 编辑配置文件，设置API密钥
vim .env
```

### 2. 配置API密钥

在`.env`文件中设置：

```bash
# OpenAI API密钥 (用于GPT-4o实时API)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Google API密钥 (用于Gemini Live API)  
GOOGLE_API_KEY=your-google-api-key-here
```

### 3. 启动系统

```bash
# 启动FreeSWITCH和MVP服务
docker-compose up -d

# 查看日志
docker-compose logs -f mvp
```

### 4. 验证运行状态

```bash
# 健康检查
curl http://localhost:8080/health

# 预期返回：
{
  "status": "ok",
  "freeswitch_connected": true,
  "active_calls": 0,
  "audio_streams": 0
}
```

## 📞 AI外呼使用方法

### 方法1: OpenAI语音助手外呼

```bash
curl -X POST http://localhost:8080/call/ai-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "1001",
    "caller_id": "1000",
    "ai_provider": "openai",
    "ai_model": "gpt-4o-realtime-preview",
    "ai_voice": "alloy",
    "ai_instructions": "你是一个友好的AI助手，可以进行自然对话。请保持简洁和礼貌。"
  }'
```

**OpenAI语音选项：**
- `alloy` - 平衡的中性声音
- `echo` - 男性化声音  
- `fable` - 英式口音
- `onyx` - 深沉男声
- `nova` - 年轻女声
- `shimmer` - 温和女声

### 方法2: Gemini语音助手外呼

```bash
curl -X POST http://localhost:8080/call/ai-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "1002", 
    "caller_id": "1000",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.0-flash-live-001",
    "ai_voice": "Puck",
    "ai_instructions": "你是一个有用的AI语音助手，可以回答问题并协助完成任务。"
  }'
```

**Gemini语音选项：**
- `Puck` - 活泼年轻声音
- `Charon` - 深沉稳重声音
- `Kore` - 温和女声
- `Fenrir` - 强劲男声
- `Aoede` - 优雅女声
- `Leda` - 专业女声
- `Orus` - 权威男声
- `Zephyr` - 轻快男声

### 方法3: 使用测试脚本

```bash
# 运行自动化测试
python test_ai_outbound.py

# 或指定服务地址
python test_ai_outbound.py http://localhost:8080
```

## 📊 监控和管理

### 获取AI助手状态

```bash
curl http://localhost:8080/call/ai-status
```

**返回示例：**
```json
{
  "active_ai_sessions": 2,
  "sessions": [
    {
      "call_uuid": "12345678-1234-1234-1234-123456789012",
      "status": "answered",
      "phone_number": "1001",
      "start_time": "2024-01-01T10:00:00",
      "ai_provider": "openai"
    }
  ]
}
```

### 获取活跃通话

```bash
curl http://localhost:8080/calls
```

### 挂断AI通话

```bash
curl -X POST http://localhost:8080/call/hangup \
  -H "Content-Type: application/json" \
  -d '{"call_uuid": "12345678-1234-1234-1234-123456789012"}'
```

## 🔧 高级配置

### 自定义AI指令

可以为不同场景设置专门的AI指令：

```json
{
  "phone_number": "1001",
  "ai_provider": "openai", 
  "ai_instructions": "你是一家餐厅的订餐助手。你需要：1. 友好地问候客户 2. 询问他们想要什么菜品 3. 确认订单详情 4. 告知预计送达时间。请保持专业和礼貌。"
}
```

### 指定API密钥

如果不想在环境变量中设置密钥，可以在请求中直接传递：

```json
{
  "phone_number": "1001",
  "ai_provider": "openai",
  "api_key": "sk-your-specific-api-key"
}
```

## 🎛️ API参数详解

### AICallRequest参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `phone_number` | string | ✅ | - | 目标电话号码 |
| `caller_id` | string | ❌ | null | 主叫号码 |
| `dial_prefix` | string | ❌ | null | 拨号前缀 |
| `ai_provider` | string | ❌ | "openai" | AI提供商 (openai/gemini) |
| `ai_model` | string | ❌ | 自动选择 | AI模型名称 |
| `ai_voice` | string | ❌ | 默认声音 | 语音选项 |
| `ai_instructions` | string | ❌ | 默认指令 | 自定义AI指令 |
| `api_key` | string | ❌ | 环境变量 | API密钥 |

## 🔍 故障排除

### 常见问题

1. **API密钥错误**
   ```
   错误: OpenAI API key must be provided
   解决: 在.env文件中设置OPENAI_API_KEY
   ```

2. **FreeSWITCH连接失败**
   ```
   错误: freeswitch_connected: false
   解决: 检查FreeSWITCH容器是否运行
   ```

3. **音频质量问题**
   ```
   问题: 音频断断续续
   解决: 检查网络延迟和系统负载
   ```

### 调试命令

```bash
# 查看容器状态
docker-compose ps

# 查看MVP日志
docker-compose logs mvp

# 查看FreeSWITCH日志  
docker-compose logs freeswitch

# 进入MVP容器调试
docker exec -it fs-mvp bash

# 检查FreeSWITCH状态
docker exec -it freeswitch fs_cli -x "status"
```

## 📈 性能优化

### 音频配置优化

在`.env`文件中调整音频参数：

```bash
# 降低延迟
AUDIO_SAMPLE_RATE=16000  # 提高采样率
AUDIO_WS_PORT=8081      # 确保端口可用

# 提高质量
AUDIO_CHANNELS=1        # 单声道足够
AUDIO_BIT_DEPTH=16      # 16位深度
```

### 系统资源监控

```bash
# 监控容器资源使用
docker stats freeswitch fs-mvp

# 监控音频流连接
curl http://localhost:8080/health | jq '.audio_streams'
```

## 🌟 使用场景示例

### 1. 客服机器人

```json
{
  "phone_number": "客户电话",
  "ai_provider": "openai",
  "ai_voice": "nova",
  "ai_instructions": "你是客服代表。请礼貌地询问客户需要什么帮助，记录问题并提供解决方案。如果无法解决，请告知客户将转接人工客服。"
}
```

### 2. 预约提醒

```json
{
  "phone_number": "患者电话", 
  "ai_provider": "gemini",
  "ai_voice": "Leda",
  "ai_instructions": "你是医院的预约提醒助手。请确认患者明天的预约时间，询问是否需要改期，并提醒带身份证和病历本。"
}
```

### 3. 市场调研

```json
{
  "phone_number": "调研对象电话",
  "ai_provider": "openai", 
  "ai_voice": "alloy",
  "ai_instructions": "你是市场调研员。请简要介绍调研目的，询问3-5个关于产品使用习惯的问题，记录答案并感谢配合。"
}
```

## 🔐 安全注意事项

1. **API密钥安全**
   - 不要在代码中硬编码API密钥
   - 使用环境变量或密钥管理服务
   - 定期轮换API密钥

2. **通话录音合规**
   - 确保遵守当地法律法规
   - 在录音前告知对方
   - 妥善保存和处理录音数据

3. **网络安全**
   - 使用HTTPS进行API调用
   - 限制API访问权限
   - 监控异常调用行为

## 📞 技术支持

如果遇到问题，请：

1. 查看日志文件排查错误
2. 检查API密钥和网络连接
3. 确认FreeSWITCH配置正确
4. 提交Issue时包含详细错误信息

---

🎉 **恭喜！您现在已经成功集成了AI语音助手到FreeSWITCH外呼系统！**

复用agents框架的核心代码让您拥有了企业级的实时AI语音能力，可以构建各种智能电话应用场景。

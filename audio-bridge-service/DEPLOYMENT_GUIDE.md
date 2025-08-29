# 音频桥接服务部署指南

## 📋 **项目概述**

音频桥接服务是连接MVP FreeSWITCH系统和RealtimeVoiceChat AI系统的核心组件，实现电话AI机器人功能。

### **架构图**
```
电话用户 ↔ FreeSWITCH ↔ MVP ↔ 音频桥接服务 ↔ RealtimeVoiceChat ↔ AI服务
    ↑                                ↓
    ←────────────── AI语音响应 ←──────────
```

## 🚀 **快速启动**

### **1. 使用自动脚本（推荐）**

```bash
cd audio-bridge-service
./start.sh
```

脚本会自动：
- 检查Docker环境
- 启动依赖服务
- 构建和启动桥接服务  
- 运行基本测试

### **2. 手动启动**

```bash
# 启动所有服务
docker-compose up -d

# 仅启动桥接服务
docker-compose up -d audio-bridge
```

## 🔧 **详细部署步骤**

### **第一步：环境检查**

确保以下环境已就绪：

```bash
# 检查Docker
docker --version
docker-compose --version

# 检查端口占用（这些端口需要空闲）
# 8082 - 音频桥接服务
# 8080 - MVP服务  
# 8000 - RealtimeVoiceChat服务
netstat -an | grep -E "(8082|8080|8000)"
```

### **第二步：服务配置**

创建环境配置文件 `.env`（可选）：

```bash
# 音频桥接服务配置
BRIDGE_HOST=0.0.0.0
BRIDGE_PORT=8082
LOG_LEVEL=INFO
DEBUG=false

# 会话管理配置
SESSION_TIMEOUT=300
MAX_SESSIONS=10

# WebSocket连接配置
MVP_WS_HOST=fs-mvp
MVP_WS_PORT=8081
RTVC_WS_HOST=realtimevoicechat  
RTVC_WS_PORT=8000

# 音频处理配置
FREESWITCH_SAMPLE_RATE=8000
RTVC_SAMPLE_RATE=48000
AUDIO_CHANNELS=1
```

### **第三步：构建服务**

```bash
# 构建桥接服务镜像
docker-compose build audio-bridge

# 查看构建结果
docker images | grep audio-bridge
```

### **第四步：启动服务**

```bash
# 启动所有相关服务
docker-compose up -d freeswitch mvp realtimevoicechat audio-bridge

# 查看服务状态
docker-compose ps
```

### **第五步：验证部署**

```bash
# 健康检查
curl http://localhost:8082/health

# 服务信息
curl http://localhost:8082/

# 会话列表
curl http://localhost:8082/sessions
```

## 🧪 **测试验证**

### **1. 自动化测试**

```bash
# 安装测试依赖
pip install httpx

# 运行测试脚本
python test_bridge.py

# 指定服务地址测试
python test_bridge.py --host localhost --port 8082
```

### **2. 手动API测试**

```bash
# 启动桥接会话
curl -X POST http://localhost:8082/bridge/start \
  -H "Content-Type: application/json" \
  -d '{"call_uuid": "test-123", "phone_number": "1001"}'

# 查看会话状态  
curl http://localhost:8082/sessions/SESSION_ID

# 停止桥接会话
curl -X POST "http://localhost:8082/bridge/stop?call_uuid=test-123"
```

### **3. 端到端测试**

1. **发起AI外呼**：
   ```bash
   curl -X POST http://localhost:8080/call/ai-outbound \
     -H "Content-Type: application/json" \
     -d '{
       "phone_number": "1001",
       "caller_id": "1000", 
       "ai_provider": "openai",
       "ai_instructions": "你是一个友好的AI助手"
     }'
   ```

2. **检查桥接会话**：
   ```bash
   # 查看桥接服务状态
   curl http://localhost:8082/sessions
   
   # 查看MVP通话状态
   curl http://localhost:8080/calls
   ```

## 📊 **监控和日志**

### **查看实时日志**

```bash
# 桥接服务日志
docker-compose logs -f audio-bridge

# 所有相关服务日志
docker-compose logs -f audio-bridge mvp realtimevoicechat

# 过滤错误日志
docker-compose logs audio-bridge | grep ERROR
```

### **监控指标**

访问以下端点获取监控数据：

- **健康状态**: `GET /health`
- **服务统计**: `GET /stats`  
- **会话列表**: `GET /sessions`
- **特定会话**: `GET /sessions/{session_id}`

### **关键监控指标**

- **连接状态**: MVP和RTVC连接是否正常
- **会话数量**: 活跃会话数是否超限
- **音频延迟**: 端到端音频处理延迟
- **错误率**: 会话建立和音频转发错误率
- **资源使用**: CPU和内存使用情况

## 🔍 **故障排查**

### **常见问题**

#### **1. 服务启动失败**

```bash
# 检查端口占用
netstat -tulpn | grep :8082

# 检查Docker资源
docker system df
docker system events

# 查看详细错误
docker-compose logs audio-bridge
```

#### **2. 连接失败**

```bash
# 检查网络连通性
docker exec audio-bridge ping fs-mvp
docker exec audio-bridge ping realtimevoicechat  

# 检查服务端口
docker exec audio-bridge telnet fs-mvp 8081
docker exec audio-bridge telnet realtimevoicechat 8000
```

#### **3. 音频质量问题**

```bash
# 启用调试模式
docker-compose down
export DEBUG=true
export SAVE_AUDIO_DEBUG=true
docker-compose up -d audio-bridge

# 检查音频调试文件
docker exec audio-bridge ls /tmp/audio_debug/
```

#### **4. 会话管理问题**

```bash
# 查看会话详情
curl http://localhost:8082/sessions

# 手动清理会话
curl -X DELETE http://localhost:8082/sessions/SESSION_ID

# 重启服务清理所有会话
docker-compose restart audio-bridge
```

### **日志分析**

**正常启动日志**：
```
🚀 音频桥接服务启动
🔄 音频转换器初始化: 8000Hz ↔ 48000Hz
📋 会话管理器已初始化
🌐 WebSocket代理初始化完成
```

**连接成功日志**：
```
🔗 连接MVP: ws://fs-mvp:8081/audio/xxx
✅ MVP连接成功: session_id
🔗 连接RTVC: ws://realtimevoicechat:8000/ws
✅ RTVC连接成功: session_id
🔄 开始音频转发: session_id
```

**错误日志关键词**：
- `ConnectionClosed`: WebSocket连接断开
- `Connection refused`: 目标服务不可达
- `resample failed`: 音频重采样失败
- `Session timeout`: 会话超时

## 🔧 **配置调优**

### **性能优化**

```yaml
# docker-compose.yml 资源限制
audio-bridge:
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 512M
      reservations:
        cpus: '0.5'  
        memory: 256M
```

### **音频质量优化**

```bash
# 环境变量配置
AUDIO_BUFFER_SIZE=2048      # 增大缓冲区
WS_PING_INTERVAL=20         # 降低心跳频率
SESSION_TIMEOUT=600         # 延长会话超时
```

### **并发优化**

```bash
# 增加最大会话数
MAX_SESSIONS=20

# 启用调试模式分析性能
DEBUG=true
LOG_LEVEL=DEBUG
```

## 📈 **生产环境部署**

### **安全配置**

1. **网络隔离**：
   ```yaml
   networks:
     audio-bridge-net:
       driver: bridge
       internal: true
   ```

2. **资源限制**：
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 1G
   ```

3. **健康检查**：
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8082/health"]
     interval: 30s
     timeout: 10s
     retries: 3
   ```

### **高可用性配置**

1. **自动重启**：
   ```yaml
   restart: unless-stopped
   ```

2. **数据持久化**：
   ```yaml
   volumes:
     - ./logs:/app/logs
     - ./audio_debug:/tmp/audio_debug
   ```

3. **负载均衡**：
   ```bash
   # 启动多个实例
   docker-compose up -d --scale audio-bridge=2
   ```

## 🎯 **成功标准**

部署成功的标志：

- ✅ 所有容器正常运行
- ✅ 健康检查通过
- ✅ 能够建立WebSocket连接
- ✅ 音频格式转换正常
- ✅ 端到端延迟 < 300ms
- ✅ 会话管理功能正常
- ✅ 错误恢复机制有效

## 📞 **支持**

如果遇到问题：

1. 查看本文档的故障排查部分
2. 运行自动测试脚本诊断问题
3. 检查详细日志输出
4. 提交Issue时包含完整的错误日志和环境信息

---

🎉 **部署完成！现在你可以使用电话AI机器人功能了！**

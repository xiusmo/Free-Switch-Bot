## 🔌 Event Socket Library (ESL) 使用机制

### 1. **ESL 连接架构设计**

项目采用 **Genesis 库**作为 ESL 客户端，使用**双连接模式**实现职责分离：

```python
class FreeSwitchManager:
    def __init__(self):
        self.consumer = None    # 事件消费者连接（监听事件）
        self.inbound = None     # 入站连接（发送命令）
        self.connected = False
        self._connect_lock = asyncio.Lock()
```

#### **双连接模式优势**
- **Consumer 连接**: 专门监听 FreeSWITCH 事件，异步处理
- **Inbound 连接**: 专门发送 API 命令，同步执行
- **职责分离**: 避免事件监听阻塞命令执行
- **高可用性**: 单个连接失败不影响另一个连接

### 2. **ESL 连接建立流程**

#### **完整连接代码**
```python
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
                
                # 步骤1: 创建消费者连接（事件监听）
                self.consumer = Consumer(
                    host=FS_HOST,          # FreeSWITCH 地址
                    port=FS_PORT,          # 8021 ESL 端口
                    password=FS_PASSWORD   # ESL 密码认证
                )
                
                # 步骤2: 注册事件处理器
                self.consumer.handle("CHANNEL_CREATE")(self.handle_channel_create)
                self.consumer.handle("CHANNEL_ANSWER")(self.handle_channel_answer)
                self.consumer.handle("CHANNEL_HANGUP")(self.handle_channel_hangup)
                
                # 步骤3: 创建入站连接（命令发送）
                self.inbound = Inbound(
                    host=FS_HOST,
                    port=FS_PORT,
                    password=FS_PASSWORD
                )
                
                # 步骤4: 启动入站连接
                await self.inbound.start()
                self.connected = True
                logger.info("入站连接已建立")
                
                # 步骤5: 启动消费者连接（后台任务）
                asyncio.create_task(self.consumer.start())
                logger.info("消费者连接任务已启动")
                break
                
            except Exception as e:
                logger.error(f"连接 FreeSWITCH 失败: {e}")
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, max_backoff)
```

#### **连接配置参数**
```python
# ESL 连接配置（来自 vars.xml）
FS_HOST = "freeswitch"                              # FreeSWITCH 容器名
FS_PORT = 8021                                      # ESL 端口
FS_PASSWORD = "FSB0t_3SL_pw_20250812_abcDEF1234"  # ESL 密码
```

### 3. **ESL API 命令执行机制**

#### **API 命令执行函数**
```python
async def api(self, command: str, timeout_seconds: float = 1.0) -> str:
    """通过 ESL 执行 API 命令，并返回文本响应（带超时，防阻塞）"""
    if not self.inbound:
        raise Exception("Inbound 未初始化")
    
    # 发送 API 命令到 FreeSWITCH
    response = await asyncio.wait_for(
        self.inbound.send(f"api {command}"), 
        timeout=timeout_seconds
    )
    
    # 解析响应数据
    body = getattr(response, 'body', None)
    if body is not None:
        return body
    # 某些响应可能在 Reply-Text 字段
    return response.get("Reply-Text", "")
```

#### **常用 ESL API 命令清单**

| 命令分类 | API 命令 | 功能说明 | 示例 |
|----------|----------|----------|------|
| **通道管理** | `uuid_exists {uuid}` | 检查通道是否存在 | `uuid_exists 12345678-1234-1234-1234-123456789012` |
| | `uuid_answer {uuid}` | 接听通话 | `uuid_answer 12345678-1234-1234-1234-123456789012` |
| | `uuid_kill {uuid}` | 挂断通话 | `uuid_kill 12345678-1234-1234-1234-123456789012` |
| **音频流控制** | `uuid_audio_stream {uuid} start {url}` | 启动音频流 | `uuid_audio_stream 123... start ws://localhost:8081/audio/123...` |
| | `uuid_audio_stream {uuid} stop` | 停止音频流 | `uuid_audio_stream 12345678-1234-1234-1234-123456789012 stop` |
| **音频播放** | `uuid_broadcast {uuid} {file} aleg` | 播放音频文件 | `uuid_broadcast 123... /var/lib/freeswitch/recordings/test.wav aleg` |
| **外呼控制** | `originate {params}{dest} &park` | 发起外呼 | `originate {origination_caller_id_number=1000}sofia/gateway/ucm_trunk/1001 &park` |
| **系统状态** | `status` | 查看系统状态 | `status` |
| | `sofia status` | 查看 SIP 状态 | `sofia status` |
| | `sofia status gateway {name}` | 查看网关状态 | `sofia status gateway ucm_trunk` |

#### **ESL 命令使用示例**
```python
# 检查通道是否存在
exists = await self.api(f"uuid_exists {call_uuid}")
if exists.strip().lower().startswith("true"):
    print(f"通道 {call_uuid} 存在")

# 启动音频流到 WebSocket
stream_url = f"ws://fs-mvp:8081/audio/{call_uuid}"
await self.api(f"uuid_audio_stream {call_uuid} start {stream_url}")

# 播放音频文件
await self.api(f"uuid_broadcast {call_uuid} /var/lib/freeswitch/recordings/welcome.wav aleg")

# 挂断通话
await self.api(f"uuid_kill {call_uuid}")
```

---

## 🎵 mod_audio_stream WebSocket 音频流获取机制

### 1. **mod_audio_stream 插件配置**

#### **插件配置文件**: `conf/autoload_configs/mod_audio_stream.conf.xml`
```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration name="mod_audio_stream.conf" description="Audio Stream to WebSocket">
  <load module="mod_audio_stream"/>
  <settings>
    <!-- WebSocket 基础配置 -->
    <param name="websocket-enabled" value="true"/>
    <param name="websocket-port" value="8081"/>        <!-- WebSocket 端口 -->
    
    <!-- 音频格式配置 -->
    <param name="sample-rate" value="8000"/>           <!-- 8kHz 采样率 -->
    <param name="channels" value="1"/>                 <!-- 单声道 -->
    <param name="bit-depth" value="16"/>               <!-- 16位深度 -->
    
    <!-- 性能配置 -->
    <param name="buffer-size" value="1024"/>           <!-- 缓冲区大小 -->
    <param name="max-connections" value="100"/>        <!-- 最大连接数 -->
  </settings>
</configuration>
```

#### **模块加载配置**: `conf/autoload_configs/modules.conf.xml`
```xml
<modules>
  <!-- 其他模块... -->
  
  <!-- 音频流模块 - 关键组件 -->
  <load module="mod_audio_stream"/>
</modules>
```

### 2. **WebSocket 音频流服务器架构**

#### **AudioStreamManager 类设计**
```python
class AudioStreamManager:
    """音频流管理器 - 使用 mod_audio_stream 插件"""
    
    def __init__(self):
        # WebSocket 连接管理
        self.websocket_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.audio_buffers: Dict[str, List[bytes]] = {}
        
        # 服务器配置
        self.server = None
        self.port = config.config.AUDIO_WS_PORT  # 8081 端口
        self._server_started = False
        
        # 任务管理
        self._sender_tasks: Dict[str, asyncio.Task] = {}
        
        # AI 音频处理器
        self.ai_processors: Dict[str, QwenOmniAudioProcessor] = {}
        self._ai_enabled = config.config.QWEN_OMNI_ENABLED
```

#### **WebSocket 服务器启动**
```python
async def start_server(self):
    """启动 WebSocket 服务器接收音频流（防重复）"""
    if self._server_started:
        return
    try:
        self.server = await websockets.serve(
            self.handle_websocket_connection,
            "0.0.0.0",                    # 监听所有网络接口
            self.port                     # 8081 端口
        )
        self._server_started = True
        logger.info(f"音频流 WebSocket 服务器启动在端口 {self.port}")
        print(f"🔌 音频流 WebSocket 服务器启动在端口 {self.port}")
    except Exception as e:
        logger.error(f"启动 WebSocket 服务器失败: {e}")
```

### 3. **WebSocket 连接处理机制**

#### **连接建立和路径解析**
```python
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
            
            # 启动音频处理（AI 或传统模式）
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
            
            # 处理音频消息循环
            try:
                async for message in websocket:
                    await self.handle_audio_message(call_uuid, message)
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"音频流连接关闭: {call_uuid}")
            finally:
                # 清理连接和资源
                await self._cleanup_connection(call_uuid)
```

#### **音频消息处理**
```python
async def handle_audio_message(self, call_uuid: str, message):
    """处理音频消息"""
    try:
        if isinstance(message, bytes):
            # 二进制音频数据处理
            
            # 1. 录制功能 - 存储音频数据
            if call_uuid in call_recordings:
                call_recordings[call_uuid].append(message)
            
            # 2. 音频缓冲区 - 实时处理
            if call_uuid in self.audio_buffers:
                self.audio_buffers[call_uuid].append(message)
            
            # 3. AI 处理 - 发送到 AI 处理器
            if call_uuid in self.ai_processors:
                await self.ai_processors[call_uuid].process_incoming_audio(message)
            
            logger.debug(f"收到音频数据: {call_uuid}, 大小: {len(message)} bytes")
            
        else:
            # 文本消息（控制信息）
            logger.info(f"收到文本消息: {call_uuid}, 内容: {message}")
            
    except Exception as e:
        logger.error(f"处理音频消息失败: {e}")
```

### 4. **音频流启动命令机制**

#### **通过 ESL 启动音频流**
```python
async def start_call_audio_stream(self, call_uuid: str):
    """通过 ESL 命令启动 FreeSWITCH 到本服务的音频流"""
    # 构建 WebSocket URL
    stream_url = f"ws://{config.config.AUDIO_WS_HOST}:{config.config.AUDIO_WS_PORT}/audio/{call_uuid}"
    
    # 发送音频流启动命令
    command = f"uuid_audio_stream {call_uuid} start {stream_url}"
    logger.info(f"启动 FreeSWITCH 音频流: {command}")
    print(f"📡 启动 FreeSWITCH 音频流: {command}")
    
    # 执行 ESL 命令
    await self.api(command)
```

#### **停止音频流**
```python
async def stop_call_audio_stream(self, call_uuid: str):
    """停止 FreeSWITCH 到本服务的音频流"""
    # 检查通道是否还存在
    if not await self.uuid_exists(call_uuid):
        logger.info(f"通道已不存在，跳过停止音频流: {call_uuid}")
        return
    
    # 发送停止命令
    command = f"uuid_audio_stream {call_uuid} stop"
    logger.info(f"停止 FreeSWITCH 音频流: {command}")
    print(f"⏹️  停止 FreeSWITCH 音频流: {command}")
    
    try:
        await self.api(command)
    except Exception:
        # 通道可能已销毁，忽略错误
        pass
```

### 5. **音频数据格式和处理**

#### **音频格式规范**
```
标准音频格式：
- 采样率: 8000 Hz (电话音质标准)
- 声道数: 1 (单声道)
- 位深度: 16-bit
- 编码格式: PCM 原始格式
- 帧大小: 20ms (320 bytes)
- 数据传输率: 128 kbps
- 字节序: Little Endian
```

#### **音频数据流向**
```
FreeSWITCH RTP 包 → mod_audio_stream → WebSocket → AudioStreamManager
     ↓                      ↓                ↓              ↓
   SIP 媒体流          音频流插件        实时传输        音频处理
     ↓                      ↓                ↓              ↓
   编解码处理          二进制数据        WebSocket       录制/AI处理
```

---

## 📡 FreeSWITCH 事件信令接收和处理机制

### 1. **事件系统架构**

#### **事件注册机制**
```python
# 在连接建立时注册事件处理器
def setup_event_handlers(self):
    """设置事件处理器"""
    # 通道生命周期事件
    self.consumer.handle("CHANNEL_CREATE")(self.handle_channel_create)
    self.consumer.handle("CHANNEL_ANSWER")(self.handle_channel_answer)
    self.consumer.handle("CHANNEL_HANGUP")(self.handle_channel_hangup)
    
    # 可扩展的其他事件
    # self.consumer.handle("CHANNEL_BRIDGE")(self.handle_channel_bridge)
    # self.consumer.handle("DTMF")(self.handle_dtmf)
    # self.consumer.handle("RECORD_START")(self.handle_record_start)
```

#### **事件监听启动**
```python
# 启动事件监听（后台异步任务）
asyncio.create_task(self.consumer.start())
```

### 2. **通话生命周期事件处理**

#### **CHANNEL_CREATE 事件处理**
```python
async def handle_channel_create(self, event_data):
    """处理通道创建事件"""
    # 提取事件数据
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
        # 创建通话记录
        active_calls[call_uuid] = {
            "status": "ringing",           # 通话状态
            "caller_id": caller_id,        # 主叫号码
            "callee_id": callee_id,        # 被叫号码
            "start_time": datetime.now().isoformat(),  # 开始时间
            "call_uuid": call_uuid         # 通话UUID
        }
        
        # 初始化录音缓冲区
        call_recordings[call_uuid] = []
        
        # 控制台输出
        if str(direction).lower() == "outbound":
            logger.info(f"外呼通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
            print(f"📤 外呼通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
        else:
            logger.info(f"来电通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
            print(f"📞 来电通道创建: {caller_id} -> {callee_id} (UUID: {call_uuid})")
```

#### **CHANNEL_ANSWER 事件处理**
```python
async def handle_channel_answer(self, event_data):
    """处理通道应答事件"""
    call_uuid = event_data.get("Unique-ID")
    
    if call_uuid in active_calls:
        # 更新通话状态
        active_calls[call_uuid]["status"] = "answered"
        active_calls[call_uuid]["answer_time"] = datetime.now().isoformat()
        
        logger.info(f"通话已接听: {call_uuid}")
        print(f"✅ 通话已接听: {call_uuid}")
        
        # 启动音频流和播放
        await self.start_audio_stream_and_playback(call_uuid)
        
        # 开始播放音频（如果有上传的音频则优先播放）
        await self.start_audio_playback(call_uuid)
```

#### **CHANNEL_HANGUP 事件处理**
```python
async def handle_channel_hangup(self, event_data):
    """处理通道挂断事件"""
    call_uuid = event_data.get("Unique-ID")
    
    if call_uuid in active_calls:
        call_info = active_calls[call_uuid]
        end_time = datetime.now()
        start_time = datetime.fromisoformat(call_info["start_time"])
        duration = int((end_time - start_time).total_seconds())
        
        # 更新通话状态
        call_info["status"] = "completed"
        call_info["end_time"] = end_time.isoformat()
        call_info["duration"] = duration
        
        # 停止 FreeSWITCH 端的音频流
        try:
            await self.stop_call_audio_stream(call_uuid)
        except Exception as _e:
            logger.warning(f"停止 FreeSWITCH 音频流失败（可忽略）: {_e}")

        # 停止音频流管理器
        await self.audio_manager.stop_audio_stream(call_uuid)
        
        # 保存录音
        if call_uuid in call_recordings and call_recordings[call_uuid]:
            await self.save_recording(call_uuid, call_recordings[call_uuid])
        
        logger.info(f"通话结束: {call_uuid}, 时长: {duration}秒")
        print(f"📴 通话结束: {call_uuid}, 时长: {duration}秒")
        
        # 清理资源
        call_audio_files.pop(call_uuid, None)
```

### 3. **事件数据结构**

#### **典型事件数据字段**
```python
# CHANNEL_CREATE 事件数据示例
event_data = {
    # 核心标识
    "Unique-ID": "12345678-1234-1234-1234-123456789012",
    "Core-UUID": "freeswitch-core-uuid",
    
    # 通话信息
    "Caller-Caller-ID-Number": "1000",
    "Caller-Destination-Number": "1001",
    "Call-Direction": "outbound",
    "Channel-State": "CS_EXECUTE",
    "Channel-Call-State": "ACTIVE",
    
    # 通道信息
    "Channel-Name": "sofia/internal/1001@192.168.1.100",
    "Channel-Created-Time": "1648123456789000",
    "Channel-Answered-Time": "1648123456890000",
    
    # 变量信息
    "variable_direction": "outbound",
    "variable_uuid": "call_uuid",
    "variable_session_id": "session_id",
    
    # 网络信息
    "Channel-Local-IP": "192.168.1.100",
    "Channel-Remote-IP": "192.168.1.101",
    
    # 编解码信息
    "Channel-Read-Codec-Name": "PCMU",
    "Channel-Write-Codec-Name": "PCMU",
    
    # 更多字段...
}
```

#### **事件字段解析表**

| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|---------|
| **核心标识** | | | |
| `Unique-ID` | string | 通话唯一标识 | `12345678-1234-1234-1234-123456789012` |
| `Core-UUID` | string | FreeSWITCH 核心UUID | `freeswitch-core-uuid` |
| **通话信息** | | | |
| `Caller-Caller-ID-Number` | string | 主叫号码 | `1000` |
| `Caller-Destination-Number` | string | 被叫号码 | `1001` |
| `Call-Direction` | string | 呼叫方向 | `outbound`/`inbound` |
| **状态信息** | | | |
| `Channel-State` | string | 通道状态 | `CS_EXECUTE`, `CS_HANGUP` |
| `Channel-Call-State` | string | 通话状态 | `ACTIVE`, `HANGUP` |
| **时间信息** | | | |
| `Channel-Created-Time` | string | 通道创建时间 | `1648123456789000` (微秒) |
| `Channel-Answered-Time` | string | 接听时间 | `1648123456890000` |

---

## 🔄 完整的信令和音频流交互时序

### **从外呼到通话结束的完整流程**

```
时序阶段                     ESL信令                    WebSocket音频流              控制台输出
═══════════════════════════════════════════════════════════════════════════════════════════════

1. 用户发起外呼
   POST /call/outbound       →                           →                          →
   
2. 发送外呼命令
                            originate {params}          →                          →
                            
3. FreeSWITCH发起外呼
                            ↓                           →                          →
                            
4. 通道创建事件
                            CHANNEL_CREATE              →                          📤 外呼通道创建
                            
5. 对方振铃中
                            ↓                           →                          🔔 呼叫振铃中
                            
6. 对方接听电话
                            ↓                           →                          →
                            
7. 通道应答事件
                            CHANNEL_ANSWER              →                          ✅ 通话已接听
                            
8. 启动音频流
                            uuid_audio_stream start     WebSocket连接建立           📡 启动FreeSWITCH音频流
                            
9. 音频流建立
                            ↓                           /audio/{call_uuid}          🎵 音频流连接建立
                            
10. 开始播放音频
                            uuid_broadcast              ↓                          🎵 开始播放音频
                            
11. 实时音频传输
                            ↓                           音频数据流                   🎙️  音频数据传输中
                            
```

---
### 4. **常用调试命令**

#### **FreeSWITCH CLI 调试**
```bash
# 进入 FreeSWITCH CLI
docker exec -it freeswitch fs_cli

# 查看系统状态
fs_cli> status

# 查看活跃通话
fs_cli> show calls

# 查看通道详情
fs_cli> show channels

# 查看音频流状态
fs_cli> uuid_audio_stream <uuid>

# 查看 Sofia SIP 状态
fs_cli> sofia status

# 查看网关状态
fs_cli> sofia status gateway ucm_trunk

# 实时事件监控
fs_cli> /events plain all

# 测试外呼命令
fs_cli> originate sofia/gateway/ucm_trunk/1001 &echo
```

#### **Docker 容器调试**
```bash
# 查看容器状态
docker-compose ps

# 查看 MVP 应用日志
docker-compose logs -f mvp

# 查看 FreeSWITCH 日志
docker-compose logs -f freeswitch

# 进入 MVP 容器
docker exec -it fs-mvp bash

# 进入 FreeSWITCH 容器
docker exec -it freeswitch bash

# 监控网络连接
docker exec -it fs-mvp netstat -tlnp | grep 8081
docker exec -it freeswitch netstat -tlnp | grep 8021
```

### 🎯 核心职责
- **SIP 信令处理**：处理电话呼入/呼出的 SIP 协议
- **RTP 媒体流管理**：处理实时音频数据传输
- **音频流 WebSocket 桥接**：通过 mod_audio_stream 与 AI 应用对接
- **ESL 事件接口**：提供 Genesis 库连接的控制接口

---

## 🏗️ 容器构建架构

### Dockerfile 分析
```dockerfile
# 基础镜像：Debian Bookworm
FROM debian:bookworm

# 构建参数
ARG TOKEN  # SignalWire 官方仓库认证令牌
```

### 🔧 安装流程详解

#### 第一阶段：系统环境准备（第12-31行）
```bash
# 系统包管理配置
- 禁用 HTTPS 校验（开发环境）
- 清理并重新配置 APT 源
- 安装基础工具：ca-certificates, gnupg, wget, curl, git

# 编译环境安装
- build-essential, cmake, pkg-config
- libssl-dev, zlib1g-dev, libevent-dev, libspeexdsp-dev

# 语言环境配置
- 配置 en_US.UTF-8 语言环境
```

#### 第二阶段：FreeSWITCH 官方安装（第34-43行）
```bash
# SignalWire 官方仓库配置
- 下载 GPG 密钥认证
- 配置认证信息到 /etc/apt/auth.conf
- 添加官方 APT 源

# FreeSWITCH 安装
- freeswitch-meta-vanilla（轻量化版本）
- libfreeswitch-dev（开发头文件）
```

#### 第三阶段：mod_audio_stream 模块编译（第46-53行）
```bash
# 源码获取和编译
git clone https://github.com/amigniter/mod_audio_stream.git
cmake -DCMAKE_BUILD_TYPE=Release
make -j$(nproc) && make install
```

#### 第四阶段：配置和启动（第56-69行）
```bash
# 模块自动加载配置
- 注入 mod_audio_stream 到 modules.conf.xml

# 权限配置
- freeswitch:freeswitch 用户权限设置

# 端口暴露
- 8021: ESL 控制接口
- 5060/5061: SIP 信令端口
- 8081: mod_audio_stream WebSocket
- 16384-32768: RTP 媒体流端口范围
```

---

## ⚙️ 配置文件详解

### 🗂️ 配置文件结构
```
conf/
├── freeswitch.xml              # 主配置文件（引入其他配置）
├── vars.xml                    # 系统变量定义
├── autoload_configs/           # 模块配置目录
│   ├── modules.conf.xml        # 模块加载配置
│   ├── sofia.conf.xml          # SIP 协议栈配置
│   ├── event_socket.conf.xml   # ESL 接口配置
│   ├── mod_audio_stream.conf.xml # 音频流模块配置
│   └── switch.conf.xml         # 核心系统配置
├── sip_profiles/               # SIP 配置文件
│   └── internal.xml            # 内部 SIP Profile
└── dialplan/                   # 拨号计划目录
    └── default.xml             # 默认拨号计划
```

### 🔧 关键配置参数

#### vars.xml - 系统核心变量
```xml
<!-- 网络配置 -->
<X-PRE-PROCESS cmd="set" data="external_rtp_ip=172.16.100.105"/>
<X-PRE-PROCESS cmd="set" data="external_sip_ip=172.16.100.105"/>

<!-- 端口配置 -->
<X-PRE-PROCESS cmd="set" data="internal_sip_port=5060"/>
<X-PRE-PROCESS cmd="set" data="rtp_start_port=16384"/>
<X-PRE-PROCESS cmd="set" data="rtp_end_port=16484"/>

<!-- ESL 配置 -->
<X-PRE-PROCESS cmd="set" data="event_socket_listen_ip=0.0.0.0"/>
<X-PRE-PROCESS cmd="set" data="event_socket_listen_port=8021"/>
<X-PRE-PROCESS cmd="set" data="event_socket_password=FSB0t_3SL_pw_20250812_abcDEF1234"/>

<!-- UCM 对接 -->
<X-PRE-PROCESS cmd="set" data="ucm_ip=172.16.100.101"/>
```

#### modules.conf.xml - 加载的核心模块
```xml
<modules>
  <!-- 核心功能 -->
  <load module="mod_logfile"/>        <!-- 日志记录 -->
  <load module="mod_commands"/>       <!-- 命令处理 -->
  <load module="mod_dptools"/>        <!-- 拨号计划工具 -->
  
  <!-- 通信协议 -->
  <load module="mod_event_socket"/>   <!-- ESL 接口 -->
  <load module="mod_sofia"/>          <!-- SIP 协议栈 -->
  
  <!-- 媒体处理 -->
  <load module="mod_sndfile"/>        <!-- 音频文件处理 -->
  <load module="mod_tone_stream"/>    <!-- 音调生成 -->
  
  <!-- AI 集成模块 -->
  <load module="mod_audio_stream"/>   <!-- WebSocket 音频流 -->
  <load module="mod_loopback"/>       <!-- 内部回环测试 -->
</modules>
```

#### mod_audio_stream.conf.xml - 音频流配置
```xml
<configuration name="mod_audio_stream.conf">
  <settings>
    <param name="websocket-enabled" value="true"/>
    <param name="websocket-port" value="8081"/>      <!-- WebSocket 端口 -->
    <param name="sample-rate" value="8000"/>         <!-- 8kHz 采样率 -->
    <param name="channels" value="1"/>               <!-- 单声道 -->
    <param name="bit-depth" value="16"/>             <!-- 16位深度 -->
    <param name="buffer-size" value="1024"/>         <!-- 缓冲区大小 -->
    <param name="max-connections" value="100"/>      <!-- 最大连接数 -->
  </settings>
</configuration>
```

#### sip_profiles/internal.xml - SIP Profile 配置
```xml
<profile name="internal">
  <!-- UCM 网关配置 -->
  <gateways>
    <gateway name="ucm_trunk">
      <param name="proxy" value="172.16.100.101:5060"/>
      <param name="from-user" value="1000"/>
      <param name="register" value="false"/>
    </gateway>
  </gateways>
  
  <settings>
    <!-- 基础 SIP 配置 -->
    <param name="sip-port" value="5060"/>
    <param name="rtp-ip" value="0.0.0.0"/>
    <param name="ext-rtp-ip" value="172.16.100.105"/>
    
    <!-- 音频编解码优先级 -->
    <param name="inbound-codec-prefs" value="OPUS,G722,PCMU,PCMA"/>
    <param name="outbound-codec-prefs" value="OPUS,G722,PCMU,PCMA"/>
  </settings>
</profile>
```

---

## 📞 拨号计划配置

### dialplan/default.xml - 路由规则
```xml
<context name="default">
  <!-- 外呼到 UCM：拨号 9 + 号码 -->
  <extension name="to_ucm">
    <condition field="destination_number" expression="^9(\d+)$">
      <action application="bridge" data="sofia/gateway/ucm_trunk/${1}"/>
    </condition>
  </extension>
  
  <!-- 直拨 UCM 分机 1001 -->
  <extension name="to_ucm_ext_1001">
    <condition field="destination_number" expression="^(1001)$">
      <action application="bridge" data="sofia/gateway/ucm_trunk/${1}"/>
    </condition>
  </extension>
  
  <!-- 测试号码功能 -->
  <!-- 1000: 音频流测试 + 回音 -->
  <extension name="audio_stream_test">
    <condition field="destination_number" expression="^(1000)$">
      <action application="answer"/>
      <action application="record_session" data="/tmp/test_recording.wav"/>
      <action application="echo"/>
    </condition>
  </extension>
  
  <!-- 1002: WAV 文件播放测试 -->
  <extension name="audio_playback_test">
    <condition field="destination_number" expression="^(1002)$">
      <action application="answer"/>
      <action application="playback" data="/var/lib/freeswitch/recordings/wav-example.wav"/>
      <action application="echo"/>
    </condition>
  </extension>
  
  <!-- 1003: 录音功能测试 -->
  <extension name="recording_test">
    <condition field="destination_number" expression="^(1003)$">
      <action application="answer"/>
      <action application="record_session" data="/tmp/recording_test.wav"/>
      <action application="playback" data="silence_stream://5000"/>
      <action application="hangup"/>
    </condition>
  </extension>
  
  <!-- 6001: 纯回音测试 -->
  <extension name="echo_test">
    <condition field="destination_number" expression="^(6001)$">
      <action application="answer"/>
      <action application="echo"/>
    </condition>
  </extension>
  
  <!-- 9999: 简单响应测试 -->
  <extension name="simple_test">
    <condition field="destination_number" expression="^(9999)$">
      <action application="answer"/>
      <action application="playback" data="tone_stream://%(1000,0,1000)"/>
      <action application="hangup"/>
    </condition>
  </extension>
</context>
```

---

## 🐳 Docker 容器配置

### docker-compose.yaml 中的 FreeSWITCH 服务
```yaml
services:
  freeswitch:
    build:
      context: .
      args:
        TOKEN: pat_bujV42y6vPTjaF6SyPXya9GY  # SignalWire 认证令牌
    container_name: freeswitch
    restart: unless-stopped
    
    # 系统权限和资源限制
    cap_add:
      - SYS_NICE                    # 实时音频优先级
    ulimits:
      nofile:
        soft: 65000                 # 高并发文件句柄
        hard: 65000
    
    # 环境变量
    environment:
      - EXT_IP=${EXT_IP:-auto-nat}
      - FS_PASSWORD=${FS_PASSWORD:-FSB0t_3SL_pw_20250812_abcDEF1234}
    
    # 卷挂载
    volumes:
      - ./conf:/etc/freeswitch                              # 配置文件
      - ./data:/var/lib/freeswitch                          # 数据目录
      - ./logs:/var/log/freeswitch                          # 日志目录
      - ./recordings:/recordings                            # 录音目录
      - ./mvp/wav-example.wav:/var/lib/freeswitch/recordings/wav-example.wav:ro
      - ./data:/shared:ro                                   # 共享数据目录
    
    # 端口映射
    ports:
      - "5060:5060/tcp"             # SIP 信令
      - "5060:5060/udp"
      - "5061:5061/tcp"             # SIP over TLS
      - "5061:5061/udp"
      - "5080:5080/tcp"             # 外部 SIP
      - "5080:5080/udp"
      - "5081:5081/tcp"             # 外部 SIP TLS
      - "5081:5081/udp"
      - "8081:8081/tcp"             # mod_audio_stream WebSocket ⭐
      - "16384-16484:16384-16484/udp"  # RTP 媒体流范围（100并发通话）
```

---

## 🔗 与其他服务的接口

### 1. **与 MVP 容器的接口**
- **ESL 连接**：端口 8021，密码认证
- **音频流 WebSocket**：端口 8081，实时音频传输
- **共享数据卷**：`/shared` 目录用于音频文件交换

### 2. **与外部 UCM PBX 的接口**
- **SIP 网关**：`ucm_trunk` 网关，指向 `172.16.100.101:5060`
- **呼叫路由**：通过拨号计划规则路由到 UCM

### 3. **网络拓扑**
```
Internet/SIP Provider
         ↓
        UCM
         ↓
   FreeSWITCH (5060)
         ↓
   ┌─────────────────┐
   │  Docker Network │
   │  freeswitch-net │
   └─────────────────┘
         ↓
   MVP Container (8021 ESL + 8081 WebSocket)
```

---

## 🚀 启动和管理

### 启动命令
```bash
# 构建和启动 FreeSWITCH 容器
docker-compose up -d freeswitch

# 查看启动日志
docker-compose logs -f freeswitch

# 进入容器调试
docker exec -it freeswitch bash
```

### FreeSWITCH CLI 管理
```bash
# 进入 FreeSWITCH 命令行
docker exec -it freeswitch fs_cli

# 常用管理命令
fs_cli> status                          # 查看系统状态
fs_cli> sofia status                    # 查看 SIP 协议栈状态
fs_cli> sofia status gateway ucm_trunk  # 查看网关状态
fs_cli> show calls                      # 查看活跃通话
fs_cli> show channels                   # 查看通道状态
fs_cli> reload mod_audio_stream         # 重载音频流模块
```

---

## 🔍 故障排除

### 常见问题诊断

#### 1. **FreeSWITCH 启动失败**
```bash
# 检查日志
docker-compose logs freeswitch

# 常见原因
- SignalWire TOKEN 无效或过期
- 端口冲突（5060、8021、8081）
- 配置文件语法错误
- 权限问题
```

#### 2. **SIP 注册失败**
```bash
# 检查网关状态
fs_cli> sofia status gateway ucm_trunk

# 排查步骤
- 检查 UCM IP 地址是否正确（172.16.100.101）
- 验证网络连通性
- 检查 SIP 配置参数
```

#### 3. **音频流连接失败**
```bash
# 检查 mod_audio_stream 状态
fs_cli> module_exists mod_audio_stream

# 排查步骤
- 验证端口 8081 是否可访问
- 检查 WebSocket 连接日志
- 确认音频参数配置（8kHz, 16-bit, mono）
```

#### 4. **ESL 连接问题**
```bash
# 检查 ESL 接口
netstat -tlnp | grep 8021

# 排查步骤
- 验证密码配置是否一致
- 检查网络防火墙设置
- 确认 event_socket 模块已加载
```

### 日志文件位置
```bash
# 容器内日志路径
/var/log/freeswitch/freeswitch.log      # 主日志文件
/var/log/freeswitch/sofia.log           # SIP 协议日志

# 宿主机日志路径（通过卷挂载）
./logs/freeswitch.log                   # 主日志文件
./logs/sofia.log                        # SIP 协议日志
```

---

## 🔐 安全考虑

### 生产环境安全配置

#### 1. **ESL 接口安全**
```xml
<!-- 限制 ESL 访问源 IP -->
<param name="apply-inbound-acl" value="trusted_networks"/>

<!-- 使用强密码 -->
<param name="password" value="STRONG_RANDOM_PASSWORD"/>
```

#### 2. **SIP 安全配置**
```xml
<!-- 启用 ACL 访问控制 -->
<param name="apply-inbound-acl" value="internal"/>

<!-- 启用 SIP 认证 -->
<param name="auth-calls" value="true"/>
```

---

## 📊 性能优化

### 系统资源配置
```xml
<!-- switch.conf.xml -->
<param name="max-sessions" value="1000"/>        # 最大并发通话
<param name="sessions-per-second" value="30"/>   # 每秒新建会话限制

<!-- 音频优化 -->
<param name="rtp-timer-name" value="soft"/>      # 软定时器
<param name="rtp-timeout-sec" value="300"/>      # RTP 超时
```

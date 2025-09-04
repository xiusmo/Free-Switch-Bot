# GHCR 镜像部署指南

本项目支持使用GitHub Container Registry (GHCR) 预构建镜像进行快速部署。

## 镜像构建

GitHub Actions 工作流会自动构建两个镜像：
- `ghcr.io/yanxiu/free-switch-bot/freeswitch:latest` - FreeSWITCH 服务镜像
- `ghcr.io/yanxiu/free-switch-bot/mvp:latest` - MVP 应用镜像

镜像支持的标签：
- `latest` - 主分支最新版本
- `v*` - 版本标签（如 v1.0.0）
- 分支名 - 对应分支的最新版本

## 快速启动

### 1. 准备环境变量

创建 `.env` 文件：

```bash
# GitHub 仓库名称
GITHUB_REPOSITORY=yanxiu/free-switch-bot

# FreeSWITCH 配置
FS_PASSWORD=FSB0t_3SL_pw_20250812_abcDEF1234
EXT_IP=auto-nat

# MVP 应用配置
PORT=8080
```

### 2. 登录到 GHCR

```bash
# 使用 GitHub Personal Access Token 登录
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# 或者交互式登录
docker login ghcr.io
```

### 3. 启动服务

```bash
# 使用 GHCR 镜像启动
docker-compose -f docker-compose.ghcr.yml up -d

# 查看服务状态
docker-compose -f docker-compose.ghcr.yml ps

# 查看日志
docker-compose -f docker-compose.ghcr.yml logs -f
```

## 端口说明

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| FreeSWITCH | 5060 | TCP/UDP | SIP 信令 |
| FreeSWITCH | 5061 | TCP/UDP | SIP TLS |
| FreeSWITCH | 5080-5081 | TCP/UDP | SIP 备用端口 |
| FreeSWITCH | 8021 | TCP | Event Socket Library |
| FreeSWITCH | 8081 | TCP | mod_audio_stream WebSocket |
| FreeSWITCH | 16384-16484 | UDP | RTP 媒体流 |
| MVP | 8080 | TCP | HTTP API |

## 配置自定义

### 使用自定义配置

本地配置文件会挂载到容器中：
- `./conf` → `/etc/freeswitch` (只读)
- `./logs` → `/var/log/freeswitch` (读写)
- `./recordings` → `/recordings` (读写)
- `./data` → `/shared` (读写)

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GITHUB_REPOSITORY` | `yanxiu/free-switch-bot` | GitHub 仓库路径 |
| `FS_PASSWORD` | `FSB0t_3SL_pw_20250812_abcDEF1234` | FreeSWITCH ESL 密码 |
| `EXT_IP` | `auto-nat` | 外部IP设置 |

## 镜像架构

所有镜像都基于 `linux/amd64` 架构构建，确保在大多数云平台上的兼容性。

## 故障排除

### 镜像拉取失败

```bash
# 检查网络连接
docker pull ghcr.io/yanxiu/free-switch-bot/freeswitch:latest

# 检查认证状态
docker info | grep -i registry
```

### 服务启动失败

```bash
# 查看详细日志
docker-compose -f docker-compose.ghcr.yml logs freeswitch
docker-compose -f docker-compose.ghcr.yml logs mvp

# 检查端口占用
netstat -tulpn | grep -E "(5060|8021|8080|8081)"
```

### 权限问题

```bash
# 确保目录权限正确
sudo chown -R 999:999 logs data recordings
```

## 更新镜像

```bash
# 拉取最新镜像
docker-compose -f docker-compose.ghcr.yml pull

# 重新启动服务
docker-compose -f docker-compose.ghcr.yml up -d
```

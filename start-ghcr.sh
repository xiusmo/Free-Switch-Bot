#!/bin/bash

# Free Switch Bot - GHCR 镜像快速启动脚本

set -e

echo "🚀 Free Switch Bot - GHCR 镜像启动脚本"
echo "=========================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: Docker 未安装或未在PATH中"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: Docker Compose 未安装或未在PATH中"
    echo "请先安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cat > .env << EOF
# GitHub 仓库名称
GITHUB_REPOSITORY=yanxiu/free-switch-bot

# FreeSWITCH 配置
FS_PASSWORD=FSB0t_3SL_pw_20250812_abcDEF1234
EXT_IP=auto-nat

# MVP 应用配置
PORT=8080
EOF
    echo "✅ 已创建默认 .env 文件"
    echo "💡 您可以编辑 .env 文件来自定义配置"
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p logs recordings data/db data/storage data/images

# 设置目录权限（FreeSWITCH 使用 UID 999）
echo "🔐 设置目录权限..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    sudo chown -R 999:999 logs data recordings 2>/dev/null || {
        echo "⚠️  警告: 无法设置目录权限，可能需要手动设置"
        echo "请运行: sudo chown -R 999:999 logs data recordings"
    }
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    chown -R 999:999 logs data recordings 2>/dev/null || {
        echo "⚠️  警告: 无法设置目录权限（macOS可能不需要）"
    }
fi

# 检查 GHCR 登录状态
echo "🔍 检查 GHCR 登录状态..."
if ! docker info 2>/dev/null | grep -q "ghcr.io"; then
    echo "⚠️  提示: 您可能需要登录到 GHCR"
    echo "如果拉取镜像失败，请运行: docker login ghcr.io"
fi

# 拉取最新镜像
echo "📥 拉取最新镜像..."
docker-compose -f docker-compose.ghcr.yml pull

# 启动服务
echo "🚀 启动服务..."
docker-compose -f docker-compose.ghcr.yml up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo "🔍 检查服务状态..."
docker-compose -f docker-compose.ghcr.yml ps

# 显示访问信息
echo ""
echo "✅ 服务已启动！"
echo "=========================================="
echo "🌐 服务访问地址:"
echo "  - MVP API: http://localhost:8080"
echo "  - FreeSWITCH ESL: localhost:8021"
echo "  - Audio WebSocket: ws://localhost:8081"
echo ""
echo "📋 常用命令:"
echo "  - 查看日志: docker-compose -f docker-compose.ghcr.yml logs -f"
echo "  - 停止服务: docker-compose -f docker-compose.ghcr.yml down"
echo "  - 重启服务: docker-compose -f docker-compose.ghcr.yml restart"
echo ""
echo "📁 数据目录:"
echo "  - 日志: ./logs/"
echo "  - 录音: ./recordings/"
echo "  - 数据: ./data/"
echo ""
echo "🆘 如有问题，请查看 README-GHCR.md 获取详细说明"

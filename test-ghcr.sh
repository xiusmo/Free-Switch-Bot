#!/bin/bash

# GHCR 连接测试脚本

echo "🧪 测试 GHCR 连接和镜像访问"
echo "================================"

# 检查Docker登录状态
echo "1. 检查 Docker 登录状态..."
if docker info 2>/dev/null | grep -q "Username:"; then
    echo "✅ Docker 已登录"
    docker info 2>/dev/null | grep "Username:"
else
    echo "⚠️  Docker 未登录到任何registry"
fi

# 尝试拉取公共镜像（测试网络连接）
echo ""
echo "2. 测试网络连接..."
if docker pull hello-world:latest >/dev/null 2>&1; then
    echo "✅ Docker Hub 连接正常"
    docker rmi hello-world:latest >/dev/null 2>&1 || true
else
    echo "❌ Docker Hub 连接失败"
fi

# 尝试访问 GHCR
echo ""
echo "3. 测试 GHCR 访问..."
REPO=${GITHUB_REPOSITORY:-yanxiu/free-switch-bot}
if docker pull ghcr.io/$REPO/freeswitch:latest >/dev/null 2>&1; then
    echo "✅ GHCR 镜像拉取成功"
    echo "📦 可用镜像："
    docker images | grep "ghcr.io/$REPO" || echo "   (镜像可能已被清理)"
else
    echo "❌ GHCR 镜像拉取失败"
    echo ""
    echo "可能的原因："
    echo "  1. 镜像尚未构建（首次运行 GitHub Actions）"
    echo "  2. 需要登录到 GHCR："
    echo "     docker login ghcr.io"
    echo "  3. 镜像是私有的，需要访问权限"
fi

echo ""
echo "💡 提示："
echo "  - 如果是首次设置，请先推送代码触发 GitHub Actions"
echo "  - 查看构建状态：https://github.com/$REPO/actions"
echo "  - 查看包列表：https://github.com/users/$(echo $REPO | cut -d'/' -f1)/packages"

#!/bin/bash

# Audio Bridge Service Startup Script
# 音频桥接服务启动脚本

set -e

echo "🎵 Audio Bridge Service - 音频桥接服务启动脚本"
echo "================================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 函数：打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查Docker是否运行
check_docker() {
    print_info "检查Docker环境..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装！请先安装Docker。"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker未运行！请启动Docker。"
        exit 1
    fi
    
    print_success "Docker环境正常"
}

# 检查依赖服务
check_dependencies() {
    print_info "检查依赖服务..."
    
    # 检查MVP服务
    if ! docker ps | grep -q "fs-mvp"; then
        print_warning "MVP服务未运行，将尝试启动..."
        cd .. && docker-compose up -d mvp
    else
        print_success "MVP服务已运行"
    fi
    
    # 检查RealtimeVoiceChat服务
    if ! docker ps | grep -q "realtimevoicechat"; then
        print_warning "RealtimeVoiceChat服务未运行，将尝试启动..."
        cd .. && docker-compose up -d realtimevoicechat
    else
        print_success "RealtimeVoiceChat服务已运行"
    fi
}

# 构建服务
build_service() {
    print_info "构建音频桥接服务..."
    
    cd ..
    docker-compose build audio-bridge
    
    print_success "服务构建完成"
}

# 启动服务
start_service() {
    print_info "启动音频桥接服务..."
    
    cd ..
    docker-compose up -d audio-bridge
    
    print_success "服务启动完成"
}

# 等待服务就绪
wait_for_service() {
    print_info "等待服务就绪..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f http://localhost:8082/health > /dev/null 2>&1; then
            print_success "服务已就绪！"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "服务启动超时！"
    return 1
}

# 显示服务状态
show_status() {
    print_info "服务状态："
    
    echo ""
    echo "🐳 Docker容器状态："
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(audio-bridge|fs-mvp|realtimevoicechat|freeswitch)"
    
    echo ""
    echo "🌐 服务端点："
    echo "  • 音频桥接服务: http://localhost:8082"
    echo "  • 健康检查: http://localhost:8082/health"  
    echo "  • API文档: http://localhost:8082/docs"
    echo "  • MVP服务: http://localhost:8080"
    echo "  • RealtimeVoiceChat: http://localhost:8000"
    
    echo ""
    print_info "获取服务状态："
    if curl -s http://localhost:8082/health | python -m json.tool 2>/dev/null; then
        echo ""
    else
        print_warning "无法获取服务状态，服务可能未完全启动"
    fi
}

# 运行测试
run_tests() {
    print_info "运行基本测试..."
    
    if command -v python3 &> /dev/null; then
        # 检查是否有httpx库
        if python3 -c "import httpx" &> /dev/null; then
            python3 test_bridge.py --host localhost --port 8082
        else
            print_warning "缺少httpx库，跳过自动测试"
            print_info "可以手动安装: pip install httpx"
        fi
    else
        print_warning "未找到Python3，跳过自动测试"
    fi
}

# 主流程
main() {
    echo ""
    print_info "开始启动音频桥接服务..."
    
    # 检查环境
    check_docker
    
    # 检查依赖
    check_dependencies
    
    # 构建服务
    build_service
    
    # 启动服务
    start_service
    
    # 等待服务就绪
    if wait_for_service; then
        # 显示状态
        show_status
        
        # 运行测试
        echo ""
        read -p "是否运行基本测试？(y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            run_tests
        fi
        
        echo ""
        print_success "🎉 音频桥接服务启动完成！"
        print_info "使用 'docker-compose logs -f audio-bridge' 查看日志"
        print_info "使用 'docker-compose down' 停止服务"
        
    else
        print_error "服务启动失败！"
        print_info "使用 'docker-compose logs audio-bridge' 查看错误日志"
        exit 1
    fi
}

# 处理中断信号
trap 'print_warning "启动被中断"; exit 1' INT TERM

# 运行主流程
main "$@"

#!/usr/bin/env python3
"""
Audio Bridge Service - Main Entry Point
音频桥接服务主入口点
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.bridge_server import main

if __name__ == "__main__":
    main()

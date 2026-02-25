#!/bin/bash
# ABU量化交易系统 - 一键启动脚本
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=========================================="
echo "  ABU 量化交易系统"
echo "=========================================="

# Check Python 3.8
if command -v python3.8 &>/dev/null; then
    PYTHON=python3.8
elif command -v python3 &>/dev/null; then
    PYTHON=python3
else
    echo "错误: 未找到 Python 3.8+，请先安装"
    exit 1
fi

# Create venv if not exists
if [ ! -d "$VENV_DIR" ]; then
    echo "正在创建虚拟环境..."
    $PYTHON -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install dependencies
echo "正在检查依赖..."
pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null

# Start server
echo ""
echo "启动Web服务..."
echo "访问地址: http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo ""

cd "$SCRIPT_DIR"
python webapp/app.py

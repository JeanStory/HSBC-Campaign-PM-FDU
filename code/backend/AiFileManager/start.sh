#!/bin/bash

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "当前Python版本: $PYTHON_VERSION"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建Python虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "升级pip..."
pip install --upgrade pip

# 安装依赖
echo "安装项目依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "警告: requirements.txt 文件不存在"
fi

# 创建上传目录
echo "创建上传目录..."
mkdir -p ./uploads

# 启动服务器
echo "启动FastAPI服务器..."
echo "服务器将在 http://0.0.0.0:8000 上运行"
echo "API文档地址: http://0.0.0.0:8000/docs"
python main.py
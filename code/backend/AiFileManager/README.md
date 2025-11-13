# AI文件管理系统

HSBC Campaign - AI智能文件管家后端服务

## 项目简介

这是一个基于FastAPI开发的文件管理系统后端服务，提供文件上传、下载、列表查询和删除等基本功能。

## 技术栈

- Python 3.11+
- FastAPI 0.100.0+
- Uvicorn 0.22.0+
- Pydantic Settings 2.0.0+

## 功能特性

- 文件上传（支持多种文件格式）
- 文件列表查询
- 文件删除
- 健康检查
- 灵活的配置管理
- CORS支持

## 快速开始

### 1. 运行启动脚本

```bash
./start.sh
```

启动脚本会自动完成以下操作：
- 创建Python虚拟环境
- 激活虚拟环境
- 升级pip
- 安装项目依赖
- 创建上传目录
- 启动FastAPI服务器

### 2. 手动安装和运行

如果不想使用启动脚本，也可以手动执行以下步骤：

```bash
# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动服务器
python main.py
```

## API文档

服务器启动后，可以通过以下地址访问API文档：

- Swagger UI: http://0.0.0.0:8000/docs
- ReDoc: http://0.0.0.0:8000/redoc

## API端点

### 基础接口

- **GET /** - 根路径，返回欢迎信息
- **GET /health** - 健康检查接口

### 文件管理接口

- **POST /api/v1/files/upload** - 上传单个文件
- **GET /api/v1/files/list** - 获取文件列表
- **DELETE /api/v1/files/delete/{filename}** - 删除指定文件

## 配置说明

配置文件位于 `config.py`，主要配置项包括：

- **app_name**: 应用名称
- **app_version**: 应用版本
- **host**: 服务器监听地址
- **port**: 服务器监听端口
- **upload_dir**: 文件上传目录
- **max_file_size**: 最大文件大小限制
- **allowed_extensions**: 允许的文件扩展名
- **api_prefix**: API路径前缀
- **cors_origins**: CORS允许的源

也可以通过创建 `.env` 文件来覆盖默认配置。

## 项目结构

```
AiFileManager/
├── main.py          # 主应用入口
├── config.py        # 配置管理
├── requirements.txt # Python依赖
├── pyproject.toml   # 项目元数据
├── start.sh         # 启动脚本
├── README.md        # 项目说明
├── src/             # 源代码目录
│   └── aifilemanager/
│       └── __init__.py
├── tests/           # 测试目录
│   └── __init__.py
└── uploads/         # 文件上传目录
```

## 注意事项

1. 默认情况下，CORS设置为允许所有源（"*"），在生产环境中应该设置为具体的域名。
2. 文件上传大小限制默认为100MB，可以在配置中修改。
3. 生产环境部署时，建议关闭reload功能。

## 许可证

© 2023 HSBC Campaign Team
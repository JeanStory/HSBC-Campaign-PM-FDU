from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os

# 导入配置
from config import settings

# 导入文件管理模块
from file import file_router

# 导入模型管理模块
from model_router import model_router

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.app_name,
    description="HSBC Campaign - AI智能文件管家后端服务",
    version=settings.app_version
)

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# 创建上传目录
os.makedirs(settings.upload_dir, exist_ok=True)

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI File Manager API", "version": settings.app_version}

# 根路径端点
@app.get("/")
async def root():
    return {"message": f"欢迎使用{settings.app_name}API", "version": settings.app_version}

# 注册文件管理路由
app.include_router(file_router, prefix=settings.api_prefix)

# 注册模型管理路由
app.include_router(model_router, prefix=settings.api_prefix)

# 如果直接运行此文件，则启动服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
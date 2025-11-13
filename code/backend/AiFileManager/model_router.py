from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging
from pathlib import Path

# 导入模型客户端
from model import get_model_client, ModelClient
from config import settings

# 创建路由器
model_router = APIRouter(prefix="/models", tags=["models"])

# 配置日志
logger = logging.getLogger(__name__)

# 对话消息模型
class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str

# 对话请求模型
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []
    model_name: Optional[str] = None

# 文件分析请求模型
class FileAnalysisRequest(BaseModel):
    filename: str
    query: str
    model_name: Optional[str] = None

# 获取模型客户端的依赖项
async def get_model() -> ModelClient:
    try:
        client = get_model_client()
        return client
    except Exception as e:
        logger.error(f"获取模型客户端失败: {e}")
        raise HTTPException(status_code=500, detail="模型服务初始化失败")

@model_router.post("/chat", summary="与大模型对话", description="发送消息给大模型并获取回复，支持对话历史")
async def chat_with_model(request: ChatRequest, model: ModelClient = Depends(get_model)):
    try:
        # 准备对话历史
        history = [(msg.role, msg.content) for msg in request.history] if request.history else []
        
        # 调用模型获取回复
        response = await model.chat(
            message=request.message,
            history=history,
            model_name=request.model_name
        )
        
        return {
            "response": response,
            "model_used": request.model_name or settings.model_name,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"对话请求失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")

@model_router.post("/analyze-file", summary="文件分析", description="分析上传的文件并回答关于文件的问题")
async def analyze_file(request: FileAnalysisRequest, model: ModelClient = Depends(get_model)):
    try:
        # 检查文件是否存在
        file_path = Path(settings.upload_dir) / request.filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 调用模型分析文件
        response = await model.analyze_file(
            file_path=str(file_path),
            query=request.query,
            model_name=request.model_name
        )
        
        return {
            "response": response,
            "filename": request.filename,
            "model_used": request.model_name or settings.model_name,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件分析请求失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件分析失败: {str(e)}")

@model_router.get("/status", summary="模型服务状态", description="检查模型服务的运行状态")
async def model_status(model: ModelClient = Depends(get_model)):
    try:
        status = model.get_status()
        return {
            "status": "connected",
            "model_provider": settings.model_provider,
            "model_name": settings.model_name,
            "config": status
        }
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        raise HTTPException(status_code=500, detail="无法连接到模型服务")
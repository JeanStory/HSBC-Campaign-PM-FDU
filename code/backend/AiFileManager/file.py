from fastapi import UploadFile, File, HTTPException, APIRouter
import os
from pathlib import Path
from typing import List, Dict, Any

# 导入配置
from config import settings

# 创建文件管理路由器
file_router = APIRouter(prefix="/files")

# 文件上传函数
def validate_file(file: UploadFile) -> Dict[str, Any]:
    """验证文件大小和类型"""
    # 检查文件大小
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()  # 获取文件大小
    file.file.seek(0)  # 重置到文件开头
    
    if file_size > settings.max_file_size:
        raise HTTPException(status_code=413, detail=f"文件大小超过限制({settings.max_file_size/1024/1024}MB)")
    
    # 检查文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型。允许的类型: {', '.join(settings.allowed_extensions)}")
    
    return {"file_size": file_size, "file_ext": file_ext}

async def save_uploaded_file(file: UploadFile) -> str:
    """保存上传的文件"""
    file_path = os.path.join(settings.upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    return file_path

# 文件上传端点
@file_router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传单个文件"""
    # 验证文件
    validation_result = validate_file(file)
    file_size = validation_result["file_size"]
    
    # 保存文件
    file_path = await save_uploaded_file(file)
    
    return {
        "filename": file.filename,
        "size": file_size,
        "path": file_path,
        "status": "uploaded"
    }

# 获取文件列表端点
@file_router.get("/list")
async def list_files():
    """获取上传目录中的文件列表"""
    files = []
    try:
        for filename in os.listdir(settings.upload_dir):
            file_path = os.path.join(settings.upload_dir, filename)
            if os.path.isfile(file_path):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
        return {"files": files, "total": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

# 删除文件端点
@file_router.delete("/delete/{filename}")
async def delete_file(filename: str):
    """删除指定文件"""
    file_path = os.path.join(settings.upload_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        os.remove(file_path)
        return {"message": f"文件 {filename} 已成功删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
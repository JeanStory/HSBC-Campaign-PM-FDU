from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    """应用配置类"""
    # 应用基本配置
    app_name: str = "AI文件管理系统"
    app_version: str = "0.1.0"
    
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    
    # CORS配置
    cors_origins: List[str] = ["*"]  # 生产环境应该设置具体的域名
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # 文件存储配置
    upload_dir: str = "./uploads"
    max_file_size: int = 104857600  # 100MB，单位为字节
    allowed_extensions: List[str] = [
        ".txt", ".pdf", ".doc", ".docx", ".xls", ".xlsx", 
        ".ppt", ".pptx", ".jpg", ".jpeg", ".png", ".gif"
    ]

    # 模型配置
    model_provider: str = "openai"  # 模型提供商：openai, anthropic, zhipu等
    model_token: str = ""  # API密钥
    model_api_key: Optional[str] = None  # API密钥别名，与model_token功能相同
    model_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # API基础URL
    model_name: str = "qwen-plus"  # 模型名称
    model_timeout: int = 30  # API请求超时时间（秒）
    model_max_retries: int = 3  # 请求失败最大重试次数
    model_max_history_length: int = 10  # 最大对话历史轮数
    model_max_file_size: int = 100000  # 最大文件处理大小（字符数）
    model_max_tokens: int = 1000  # 生成内容的最大token数
    model_temperature: float = 0.7  # 生成温度参数（0-1）
    
    # API配置
    api_prefix: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# 创建全局配置实例
settings = Settings()
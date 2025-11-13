import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
import os
from openai import OpenAI
from config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelClient:
    """大模型客户端，提供与大模型交互的核心功能"""
    
    def __init__(self, model_name: str = None, api_key: str = None):
        """
        初始化模型客户端
        
        Args:
            model_name: 模型名称，默认为配置文件中的设置
            api_key: API密钥，默认为配置文件中的设置
        """
        self.model_name = model_name or getattr(settings, 'model_name', 'gpt-4o-mini')
        self.api_key = api_key or getattr(settings, 'model_token', None) or getattr(settings, 'model_api_key', None)
        self.base_url = getattr(settings, 'model_base_url', None)
        self.timeout = getattr(settings, 'model_timeout', 30)
        self.max_retries = getattr(settings, 'model_max_retries', 3)
        
        # 初始化对话历史
        self.conversation_history: List[Dict[str, str]] = []
        
        # 导入适当的客户端库
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化模型客户端库"""
        try:
            # 根据模型类型导入相应的客户端库
            model_provider = getattr(settings, 'model_provider', 'openai')
            
            if model_provider == "openai":
                self.client_type = "openai"
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url if self.base_url else None
                )
            elif model_provider == "anthropic":
                try:
                    import anthropic
                    self.client_type = "anthropic"
                    self.client = anthropic.Anthropic(
                        api_key=self.api_key
                    )
                except ImportError:
                    logger.warning("未安装anthropic库，回退到OpenAI客户端")
                    self.client_type = "openai"
                    self.client = OpenAI(
                        api_key=self.api_key,
                        base_url=self.base_url if self.base_url else None
                    )
            else:
                # 默认使用OpenAI兼容接口
                self.client_type = "openai_compatible"
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                
            logger.info(f"初始化{model_provider}客户端成功")
        except Exception as e:
            logger.error(f"导入客户端库失败: {e}")
            raise ImportError(f"请安装所需的客户端库: {e}")
    
    async def chat(self, message: str, system_prompt: str = None, **kwargs) -> str:
        """
        与大模型进行对话
        
        Args:
            message: 用户消息
            system_prompt: 系统提示词，可选
            **kwargs: 其他参数，如temperature, max_tokens等
            
        Returns:
            模型的回复内容
        """
        try:
            # 添加用户消息到历史
            self.conversation_history.append({"role": "user", "content": message})
            
            # 准备完整的消息列表
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.extend(self.conversation_history)
            
            # 调用模型API
            response = await self._call_model(messages, **kwargs)
            
            # 添加助手回复到历史
            self.conversation_history.append({"role": "assistant", "content": response})
            
            # 限制历史记录长度
            max_history_length = getattr(settings, 'model_max_history_length', 10)
            if len(self.conversation_history) > max_history_length * 2:
                self.conversation_history = self.conversation_history[-max_history_length * 2:]
            
            return response
        except Exception as e:
            logger.error(f"对话失败: {e}")
            raise
    
    async def analyze_file(self, file_content: str, file_type: str, prompt: str = None) -> str:
        """
        分析文件内容
        
        Args:
            file_content: 文件内容
            file_type: 文件类型
            prompt: 特定的分析提示词，可选
            
        Returns:
            分析结果
        """
        default_prompt = f"请分析以下{file_type}文件内容，并提供详细总结:"
        analysis_prompt = prompt or default_prompt
        
        # 处理大文件内容
        max_file_size = getattr(settings, 'model_max_file_size', 100000)
        if len(file_content) > max_file_size:
            file_content = file_content[:max_file_size] + "\n[文件内容过长，已截断]"
        
        # 构建完整的分析请求
        full_prompt = f"{analysis_prompt}\n```\n{file_content}\n```"
        
        return await self.chat(full_prompt, system_prompt="你是一个专业的文件分析助手。")
    
    async def _call_model(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        调用模型API，处理重试逻辑
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            模型回复内容
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                if self.client_type == "openai" or self.client_type == "openai_compatible":
                    response = await asyncio.wait_for(
                        self._call_openai(messages, **kwargs),
                        timeout=self.timeout
                    )
                    return response
                elif self.client_type == "anthropic":
                    response = await asyncio.wait_for(
                        self._call_anthropic(messages, **kwargs),
                        timeout=self.timeout
                    )
                    return response
                else:
                    raise ValueError(f"不支持的客户端类型: {self.client_type}")
                    
            except Exception as e:
                last_error = e
                retry_count += 1
                logger.warning(f"调用模型失败 (尝试 {retry_count}/{self.max_retries + 1}): {e}")
                
                if retry_count <= self.max_retries:
                    # 指数退避
                    wait_time = 2 ** (retry_count - 1) * 0.5
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
        
        raise Exception(f"达到最大重试次数，调用模型失败: {last_error}")
    
    async def _call_openai(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """调用OpenAI API"""
        # 移除不支持的参数
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = getattr(settings, 'model_max_tokens', 1000)
        if 'temperature' not in kwargs:
            kwargs['temperature'] = getattr(settings, 'model_temperature', 0.7)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs
        )
        
        return response.choices[0].message.content
    
    async def _call_anthropic(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """调用Anthropic API"""
        # 移除不支持的参数并添加Claude特定参数
        if 'max_tokens' not in kwargs:
            kwargs['max_tokens'] = getattr(settings, 'model_max_tokens', 1000)
        if 'temperature' not in kwargs:
            kwargs['temperature'] = getattr(settings, 'model_temperature', 0.7)
        
        # 提取系统提示
        system_prompt = None
        content_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                system_prompt = msg['content']
            else:
                content_messages.append(msg)
        
        response = self.client.messages.create(
            model=self.model_name,
            messages=content_messages,
            system=system_prompt,
            **kwargs
        )
        
        return response.content[0].text
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
        logger.info("对话历史已清除")
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.conversation_history.copy()

# 全局模型客户端实例
_model_client_instance = None

def get_model_client() -> ModelClient:
    """
    获取全局模型客户端实例（单例模式）
    
    Returns:
        模型客户端实例
    """
    global _model_client_instance
    if _model_client_instance is None:
        _model_client_instance = ModelClient()
    return _model_client_instance

# 保留原有的client变量以保持向后兼容性
try:
    client = OpenAI(
        api_key=getattr(settings, 'model_token', None) or getattr(settings, 'model_api_key', None),
        base_url=getattr(settings, 'model_base_url', None),
    )
except Exception as e:
    logger.warning(f"初始化默认client失败: {e}")
    client = None
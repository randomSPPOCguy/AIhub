"""
OpenAI Provider
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from ..base_provider import BaseProvider
from config import settings


class OpenAIProvider(BaseProvider):
    """OpenAI Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        if self.is_configured():
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None
    
    def get_available_models(self) -> List[str]:
        """Get available OpenAI models"""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        ]
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat request to OpenAI"""
        if not self.is_configured():
            raise ValueError("OpenAI API key not configured")
        
        model_name = model or settings.DEFAULT_OPENAI_MODEL
        
        # Send request
        response = await self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        }
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream chat response from OpenAI"""
        if not self.is_configured():
            raise ValueError("OpenAI API key not configured")
        
        model_name = model or settings.DEFAULT_OPENAI_MODEL
        
        # Stream request
        stream = await self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {
                    "content": chunk.choices[0].delta.content,
                    "finish_reason": chunk.choices[0].finish_reason
                }
            
            if chunk.choices[0].finish_reason:
                yield {
                    "content": "",
                    "finish_reason": chunk.choices[0].finish_reason
                }

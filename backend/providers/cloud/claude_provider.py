"""
Anthropic Claude Provider
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from anthropic import AsyncAnthropic
from ..base_provider import BaseProvider
from config import settings


class ClaudeProvider(BaseProvider):
    """Anthropic Claude Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        if self.is_configured():
            self.client = AsyncAnthropic(api_key=self.api_key)
        else:
            self.client = None
    
    def get_available_models(self) -> List[str]:
        """Get available Claude models"""
        return [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
        ]
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple[Optional[str], List[Dict[str, str]]]:
        """
        Convert standard messages to Claude format
        Claude requires system message to be separate
        """
        system = None
        claude_messages = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                system = content
            else:
                claude_messages.append({
                    "role": role,
                    "content": content
                })
        
        return system, claude_messages
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat request to Claude"""
        if not self.is_configured():
            raise ValueError("Claude API key not configured")
        
        model_name = model or settings.DEFAULT_CLAUDE_MODEL
        
        # Convert messages
        system, claude_messages = self._convert_messages(messages)
        
        # Build request params
        request_params = {
            "model": model_name,
            "messages": claude_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if system:
            request_params["system"] = system
        
        # Send request
        response = await self.client.messages.create(**request_params)
        
        return {
            "content": response.content[0].text,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
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
        """Stream chat response from Claude"""
        if not self.is_configured():
            raise ValueError("Claude API key not configured")
        
        model_name = model or settings.DEFAULT_CLAUDE_MODEL
        
        # Convert messages
        system, claude_messages = self._convert_messages(messages)
        
        # Build request params
        request_params = {
            "model": model_name,
            "messages": claude_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if system:
            request_params["system"] = system
        
        # Stream request
        async with self.client.messages.stream(**request_params) as stream:
            async for text in stream.text_stream:
                yield {
                    "content": text,
                    "finish_reason": None
                }
        
        yield {
            "content": "",
            "finish_reason": "stop"
        }

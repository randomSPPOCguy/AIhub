"""
Google Gemini Provider
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
import google.generativeai as genai
from ..base_provider import BaseProvider
from config import settings


class GeminiProvider(BaseProvider):
    """Google Gemini AI Provider"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        if self.is_configured():
            genai.configure(api_key=self.api_key)
    
    def get_available_models(self) -> List[str]:
        """Get available Gemini models"""
        return [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
        ]
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Convert standard message format to Gemini format"""
        gemini_messages = []
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            # Gemini uses 'user' and 'model' roles
            if role == "system":
                # Prepend system message to first user message
                gemini_messages.append({
                    "role": "user",
                    "parts": [f"System: {content}"]
                })
            elif role == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [content]
                })
            else:  # user
                gemini_messages.append({
                    "role": "user",
                    "parts": [content]
                })
        
        return gemini_messages
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat request to Gemini"""
        if not self.is_configured():
            raise ValueError("Gemini API key not configured")
        
        model_name = model or settings.DEFAULT_GEMINI_MODEL
        
        # Initialize model
        gemini_model = genai.GenerativeModel(model_name)
        
        # Convert messages
        gemini_messages = self._convert_messages(messages)
        
        # Create chat session
        chat = gemini_model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
        
        # Send message
        response = await chat.send_message_async(
            gemini_messages[-1]["parts"][0],
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )
        
        return {
            "content": response.text,
            "model": model_name,
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count,
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
        """Stream chat response from Gemini"""
        if not self.is_configured():
            raise ValueError("Gemini API key not configured")
        
        model_name = model or settings.DEFAULT_GEMINI_MODEL
        
        # Initialize model
        gemini_model = genai.GenerativeModel(model_name)
        
        # Convert messages
        gemini_messages = self._convert_messages(messages)
        
        # Create chat session
        chat = gemini_model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
        
        # Stream response
        response = await chat.send_message_async(
            gemini_messages[-1]["parts"][0],
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
            stream=True
        )
        
        async for chunk in response:
            if chunk.text:
                yield {
                    "content": chunk.text,
                    "finish_reason": None
                }
        
        yield {
            "content": "",
            "finish_reason": "stop"
        }

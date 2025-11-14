"""
Base Provider class that all AI providers must implement
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator


class BaseProvider(ABC):
    """Abstract base class for AI providers"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    def is_configured(self) -> bool:
        """Check if provider is properly configured"""
        return self.api_key is not None and len(self.api_key) > 0
    
    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat request and get a response
        
        Returns:
            {
                "content": str,
                "model": str,
                "usage": dict (optional)
            }
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a chat request and stream the response
        
        Yields:
            {
                "content": str,
                "finish_reason": str (optional)
            }
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider"""
        pass
    
    async def health_check(self) -> bool:
        """Check if provider is accessible"""
        if not self.is_configured():
            return False
        try:
            # Try a minimal request
            response = await self.chat(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return "content" in response
        except Exception:
            return False

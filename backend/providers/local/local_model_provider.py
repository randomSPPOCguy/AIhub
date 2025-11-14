"""
Local Model Provider (Generic HuggingFace Transformers)
Provides local inference for ANY HuggingFace model (Phi-3, Qwen, Llama, etc.)
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from .base_provider import BaseProvider
import asyncio

# Try to import transformers, but don't fail if not available
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None

# Try to import model_loader for progress tracking
try:
    from model_loader import model_loader
except Exception:
    model_loader = None


class LocalModelProvider(BaseProvider):
    """
    Generic Local Model Provider (supports ALL HuggingFace models)
    
    Runs ANY local HuggingFace model (Qwen, Phi-3, Llama, Mistral, etc.)
    Uses transformers and torch for inference without cloud APIs.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        # Local models don't use API keys
        super().__init__(api_key="local")
        
        self.model_name = model_name or "microsoft/Phi-3-mini-4k-instruct"
        self.model = None
        self.tokenizer = None
        self.device = None
        self.is_loading = False
        self.load_error = None
        self._initialized = False
    
    def is_configured(self) -> bool:
        """Check if transformers library is available"""
        return TRANSFORMERS_AVAILABLE
    
    async def initialize(self):
        """
        Load the local model asynchronously.
        This is called lazily on first use to avoid blocking startup.
        """
        if self._initialized or self.is_loading:
            return
        
        if not TRANSFORMERS_AVAILABLE:
            self.load_error = "transformers library not installed"
            return
        
        self.is_loading = True
        
        try:
            # Run model loading in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_model)
            self._initialized = True
            self.load_error = None
        except Exception as e:
            self.load_error = str(e)
            # Report failure to model_loader
            if model_loader:
                model_id = (self.model_name or "local-model").replace("/", "__")
                model_loader.fail(model_id, e)
            raise
        finally:
            self.is_loading = False
    
    def _load_model(self):
        """Load model synchronously (run in thread pool)"""
        model_id = (self.model_name or "local-model").replace("/", "__")
        model_display_name = self.model_name or "Local Model"
        
        # Start progress tracking
        if model_loader:
            model_loader.start(model_id, model_display_name)
        
        print(f"[Local Model] Loading: {self.model_name}")
        
        # Determine device
        self.device = "cuda" if torch and torch.cuda.is_available() else "cpu"
        print(f"[Local Model] Using device: {self.device}")
        
        # Load tokenizer
        if model_loader:
            model_loader.update(model_id, "loading_tokenizer", "Loading tokenizer", 15)
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        
        # Load model weights
        if model_loader:
            model_loader.update(model_id, "loading_weights", "Loading weights", 55)
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            trust_remote_code=True,
        )
        
        # Optimize model
        if model_loader:
            model_loader.update(model_id, "optimizing", "Optimizing model", 85)
        
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        
        # Mark as complete
        if model_loader:
            model_loader.done(model_id)
        
        print(f"[Local Model] Loaded successfully!")
    
    def get_available_models(self) -> List[str]:
        """Get list of example models (not exhaustive)"""
        return [
            "microsoft/Phi-3-mini-4k-instruct",
            "microsoft/Phi-3-mini-128k-instruct",
            "Qwen/Qwen2.5-3B-Instruct",
            "meta-llama/Llama-3.2-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ]
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat request to local model"""
        if not TRANSFORMERS_AVAILABLE:
            raise ValueError(
                "Local model provider requires transformers library. "
                "Install with: pip install transformers torch accelerate"
            )
        
        # Initialize model if not already done
        if not self._initialized and not self.is_loading:
            await self.initialize()
        
        if self.load_error:
            raise ValueError(f"Local model failed to load: {self.load_error}")
        
        # Format messages for the model
        formatted_prompt = self._format_messages(messages)
        
        # Generate response in thread pool
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None,
            self._generate,
            formatted_prompt,
            temperature,
            max_tokens
        )
        
        return {
            "content": response_text,
            "model": self.model_name,
            "usage": {
                "prompt_tokens": len(self.tokenizer.encode(formatted_prompt)),
                "completion_tokens": len(self.tokenizer.encode(response_text)),
            }
        }
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into chat template (works for most models)"""
        formatted = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                formatted += f"<|system|>\n{content}<|end|>\n"
            elif role == "user":
                formatted += f"<|user|>\n{content}<|end|>\n"
            elif role == "assistant":
                formatted += f"<|assistant|>\n{content}<|end|>\n"
        
        # Add assistant prompt
        formatted += "<|assistant|>\n"
        return formatted
    
    def _generate(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Generate response synchronously"""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        # Adjust temperature and sampling settings
        if temperature < 0.1:
            temperature = 0.7  # Use default if too low
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,  # Always sample for natural responses
                top_p=0.95,  # Nucleus sampling
                top_k=50,  # Top-k sampling
                repetition_penalty=1.1,  # Reduce repetition
                pad_token_id=self.tokenizer.eos_token_id,
            )
        
        # Decode and extract only the new tokens
        full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove the prompt from the response
        # Handle both exact matches and slight variations
        prompt_text = self.tokenizer.decode(inputs['input_ids'][0], skip_special_tokens=True)
        if full_response.startswith(prompt_text):
            response = full_response[len(prompt_text):].strip()
        else:
            # Fallback: try to find where assistant response starts
            response = full_response.split("<|assistant|>")[-1].strip()
            response = response.replace("<|end|>", "").strip()
        
        return response
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response (not implemented yet)
        Falls back to non-streaming
        """
        response = await self.chat(messages, model, temperature, max_tokens, **kwargs)
        yield {
            "content": response["content"],
            "finish_reason": "stop"
        }
    
    async def health_check(self) -> bool:
        """Check if local model provider is available"""
        if not TRANSFORMERS_AVAILABLE:
            return False
        
        try:
            # Just check if we can initialize
            if not self._initialized:
                await self.initialize()
            return self._initialized
        except Exception:
            return False


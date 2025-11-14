"""
Example client for AI Hub
Demonstrates how to integrate AI Hub into your applications
"""
import requests
import json
from typing import List, Dict, Optional


class AIHubClient:
    """Client for interacting with AI Hub"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self) -> Dict:
        """Check health of all providers"""
        response = self.session.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        return response.json()
    
    def get_providers(self) -> Dict:
        """Get available providers and their models"""
        response = self.session.get(f"{self.base_url}/api/providers")
        response.raise_for_status()
        return response.json()
    
    def chat(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False
    ) -> Dict:
        """
        Send a chat request to AI Hub
        
        Args:
            provider: One of 'gemini', 'openai', 'claude'
            messages: List of message dicts with 'role' and 'content'
            model: Optional model name (uses default if not specified)
            temperature: Temperature for response generation (0-2)
            max_tokens: Maximum tokens in response
            stream: Whether to stream the response
        
        Returns:
            Response dict with 'content', 'model', 'provider', and optional 'usage'
        """
        payload = {
            "provider": provider,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        if model:
            payload["model"] = model
        
        if stream:
            return self._chat_stream(payload)
        else:
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    def _chat_stream(self, payload: Dict):
        """Handle streaming chat response"""
        response = self.session.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True
        )
        response.raise_for_status()
        
        full_content = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: ') and line != 'data: [DONE]':
                    try:
                        data = json.loads(line[6:])
                        if data.get('content'):
                            content = data['content']
                            full_content += content
                            print(content, end='', flush=True)
                    except json.JSONDecodeError:
                        pass
        
        print()  # New line after streaming
        return {"content": full_content}


def example_simple_chat():
    """Example: Simple single-turn conversation"""
    print("=== Simple Chat Example ===\n")
    
    client = AIHubClient()
    
    # Check which providers are available
    providers = client.get_providers()
    print("Available providers:")
    for name, info in providers.items():
        print(f"  - {name}: {'✓' if info['available'] else '✗'}")
    print()
    
    # Simple chat with Gemini
    response = client.chat(
        provider="gemini",
        messages=[
            {"role": "user", "content": "What's the capital of France?"}
        ]
    )
    
    print(f"Provider: {response['provider']}")
    print(f"Model: {response['model']}")
    print(f"Response: {response['content']}")
    print()


def example_conversation():
    """Example: Multi-turn conversation with context"""
    print("=== Multi-turn Conversation Example ===\n")
    
    client = AIHubClient()
    
    # Build conversation history
    messages = [
        {"role": "user", "content": "Hi! I'm learning Python."},
        {"role": "assistant", "content": "That's great! Python is an excellent programming language to learn. What would you like to know about it?"},
        {"role": "user", "content": "What are list comprehensions?"}
    ]
    
    response = client.chat(
        provider="openai",
        messages=messages,
        temperature=0.7
    )
    
    print(f"AI: {response['content']}")
    print()


def example_streaming():
    """Example: Streaming response"""
    print("=== Streaming Response Example ===\n")
    
    client = AIHubClient()
    
    print("AI: ", end='', flush=True)
    client.chat(
        provider="claude",
        messages=[
            {"role": "user", "content": "Tell me a short story about a robot."}
        ],
        stream=True,
        max_tokens=500
    )
    print()


def example_compare_providers():
    """Example: Compare responses from different providers"""
    print("=== Compare Providers Example ===\n")
    
    client = AIHubClient()
    
    question = "Explain quantum computing in one sentence."
    
    providers = ["gemini", "openai", "claude"]
    
    for provider in providers:
        try:
            response = client.chat(
                provider=provider,
                messages=[{"role": "user", "content": question}],
                max_tokens=100
            )
            print(f"\n{provider.upper()}:")
            print(response['content'])
        except Exception as e:
            print(f"\n{provider.upper()}: Error - {e}")
    
    print()


def example_chatbot_loop():
    """Example: Interactive chatbot using AI Hub"""
    print("=== Interactive Chatbot Example ===")
    print("Type 'quit' to exit\n")
    
    client = AIHubClient()
    
    # Choose provider
    provider = input("Choose provider (gemini/openai/claude): ").lower()
    if provider not in ["gemini", "openai", "claude"]:
        print("Invalid provider!")
        return
    
    # Conversation history
    messages = []
    
    while True:
        # Get user input
        user_input = input("\nYou: ")
        if user_input.lower() == 'quit':
            break
        
        # Add to messages
        messages.append({"role": "user", "content": user_input})
        
        # Get response
        try:
            print(f"\n{provider.upper()}: ", end='', flush=True)
            response = client.chat(
                provider=provider,
                messages=messages,
                stream=True,
                temperature=0.8
            )
            
            # Add assistant response to history
            messages.append({"role": "assistant", "content": response['content']})
            print()
            
        except Exception as e:
            print(f"\nError: {e}")
            messages.pop()  # Remove failed user message


if __name__ == "__main__":
    # Run examples
    try:
        example_simple_chat()
        example_conversation()
        example_streaming()
        example_compare_providers()
        
        # Uncomment to try interactive mode
        # example_chatbot_loop()
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure AI Hub is running: python main.py")

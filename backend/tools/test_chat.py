import asyncio
import sys
from providers.cloud.claude_provider import ClaudeProvider
from providers.cloud.gemini_provider import GeminiProvider
from providers.cloud.openai_provider import OpenAIProvider
from config import settings

async def chat_loop():
    """Interactive chat loop for testing AI providers"""
    
    # Determine which provider to use based on available API keys
    provider = None
    provider_name = "unknown"
    
    if settings.GEMINI_API_KEY:
        provider = GeminiProvider(api_key=settings.GEMINI_API_KEY)
        provider_name = "gemini"
    elif settings.CLAUDE_API_KEY:
        provider = ClaudeProvider(api_key=settings.CLAUDE_API_KEY)
        provider_name = "claude"
    elif settings.OPENAI_API_KEY:
        provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
        provider_name = "openai"
    else:
        print("❌ No API keys found in .env file!")
        print("Please add at least one of:")
        print("  - GEMINI_API_KEY")
        print("  - CLAUDE_API_KEY")
        print("  - OPENAI_API_KEY")
        return
    
    print(f"🤖 AI Hub Test Chat ({provider_name.upper()})")
    print("=" * 50)
    print("Type your message and press Enter. Type 'exit' to quit.\n")
    
    conversation_history = []
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("👋 Goodbye!")
                break
                
            if not user_input:
                continue
            
            # Add user message to history
            conversation_history.append({
                "role": "user",
                "content": user_input
            })
            
            # Get AI response
            print("AI: ", end="", flush=True)
            response_data = await provider.chat(conversation_history)
            response = response_data.get("content", "") if isinstance(response_data, dict) else str(response_data)
            print(response)
            
            # Add AI response to history
            conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            print()  # Blank line for readability
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(chat_loop())

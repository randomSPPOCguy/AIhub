#!/usr/bin/env python3
"""
Simple API Client for Testing AI Hub Backend
Tests the actual API endpoints once the server is running
"""
import requests
import json
import sys
from typing import Dict, Any


class APIClient:
    """Simple client for testing AI Hub API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})
    
    def _print_response(self, response: requests.Response):
        """Pretty print response"""
        print(f"\n{'='*60}")
        print(f"Status Code: {response.status_code}")
        print(f"{'='*60}")
        
        try:
            data = response.json()
            print(json.dumps(data, indent=2))
        except:
            print(response.text)
        
        print(f"{'='*60}\n")
    
    def test_health(self):
        """Test health endpoint"""
        print("\n🔍 Testing Health Endpoint...")
        response = self.session.get(f"{self.base_url}/health")
        self._print_response(response)
        return response.status_code == 200
    
    def test_providers(self):
        """Test providers endpoint"""
        print("\n🔍 Testing Providers Endpoint...")
        response = self.session.get(f"{self.base_url}/providers")
        self._print_response(response)
        return response.status_code == 200
    
    def test_generate_key(self):
        """Test API key generation endpoint"""
        print("\n🔍 Testing Generate API Key Endpoint...")
        response = self.session.post(f"{self.base_url}/api/generate-key")
        self._print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("api_key")
        return None
    
    def test_chat(self, provider: str = "gemini", message: str = "Hello! Can you count to 5?"):
        """Test chat endpoint"""
        print(f"\n🔍 Testing Chat with {provider}...")
        
        payload = {
            "provider": provider,
            "message": message,
            "conversation_id": "test-conversation",
            "stream": False
        }
        
        response = self.session.post(f"{self.base_url}/chat", json=payload)
        self._print_response(response)
        return response.status_code == 200
    
    def test_models(self):
        """Test models endpoint"""
        print("\n🔍 Testing Models Endpoint...")
        response = self.session.get(f"{self.base_url}/models")
        self._print_response(response)
        return response.status_code == 200
    
    def test_conversations(self):
        """Test conversations endpoint"""
        print("\n🔍 Testing Conversations Endpoint...")
        response = self.session.get(f"{self.base_url}/conversations")
        self._print_response(response)
        return response.status_code == 200


def print_menu():
    """Display test menu"""
    print("\n" + "="*60)
    print("AI Hub API Tester".center(60))
    print("="*60)
    print("\n1. Test /health - Check if server is running")
    print("2. Test /providers - List available providers")
    print("3. Test /api/generate-key - Generate new API key")
    print("4. Test /chat - Send a chat message")
    print("5. Test /models - List available models")
    print("6. Test /conversations - List conversations")
    print("7. Run all tests")
    print("8. Exit")
    print()


def main():
    """Main entry point"""
    
    # Get configuration
    print("\n" + "="*60)
    print("AI Hub API Client Configuration".center(60))
    print("="*60)
    
    base_url = input("\nBackend URL [http://localhost:8000]: ").strip()
    if not base_url:
        base_url = "http://localhost:8000"
    
    api_key = input("API Key (optional): ").strip()
    if not api_key:
        api_key = None
    
    client = APIClient(base_url, api_key)
    
    # Test connection first
    print("\n🔍 Testing connection to backend...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Backend is reachable!")
        else:
            print(f"⚠ Backend responded with status code: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to backend!")
        print(f"  Make sure the server is running on {base_url}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    
    # Main loop
    while True:
        print_menu()
        choice = input("Choose an option (1-8): ").strip()
        
        if choice == "1":
            client.test_health()
        
        elif choice == "2":
            client.test_providers()
        
        elif choice == "3":
            new_key = client.test_generate_key()
            if new_key:
                use_key = input(f"\nUse this key for future requests? (y/n): ").strip().lower()
                if use_key == 'y':
                    client.api_key = new_key
                    client.session.headers.update({"X-API-Key": new_key})
                    print("✓ API key updated!")
        
        elif choice == "4":
            provider = input("\nProvider (gemini/openai/claude) [gemini]: ").strip().lower()
            if not provider:
                provider = "gemini"
            
            message = input("Message [Hello! Can you count to 5?]: ").strip()
            if not message:
                message = "Hello! Can you count to 5?"
            
            client.test_chat(provider, message)
        
        elif choice == "5":
            client.test_models()
        
        elif choice == "6":
            client.test_conversations()
        
        elif choice == "7":
            print("\n" + "="*60)
            print("Running All Tests".center(60))
            print("="*60)
            
            results = {
                "Health": client.test_health(),
                "Providers": client.test_providers(),
                "Models": client.test_models(),
                "Conversations": client.test_conversations(),
            }
            
            print("\n" + "="*60)
            print("Test Results".center(60))
            print("="*60)
            for test_name, passed in results.items():
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"{test_name}: {status}")
            print("="*60)
        
        elif choice == "8":
            print("\nExiting...")
            break
        
        else:
            print("✗ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

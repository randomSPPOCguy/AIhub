#!/usr/bin/env python3
"""
AI Chat with Wikipedia & MusicBrainz Demo
Shows how AI models can use external knowledge sources
"""
import requests
import re
import json

BASE_URL = "http://localhost:8000"

# Colors
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RED = '\033[91m'
BOLD = '\033[1m'
END = '\033[0m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}{END}")
    print(f"{BOLD}{BLUE}{text.center(70)}{END}")
    print(f"{BOLD}{BLUE}{'='*70}{END}\n")

def print_success(text):
    print(f"{GREEN}✓{END} {text}")

def print_info(text):
    print(f"{CYAN}→{END} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{END} {text}")

def check_backend():
    """Check if backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def test_wikipedia(query):
    """Test Wikipedia API"""
    print_info(f"Querying Wikipedia for: {query}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/wiki/search",
            params={"q": query},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Wikipedia search successful!")
            return data
        else:
            print_warning(f"Wikipedia returned: {response.status_code}")
            return None
    except Exception as e:
        print_warning(f"Wikipedia error: {e}")
        return None

def test_musicbrainz(artist):
    """Test MusicBrainz API"""
    print_info(f"Querying MusicBrainz for: {artist}")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/mb/artist/{artist}",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("MusicBrainz search successful!")
            return data
        else:
            print_warning(f"MusicBrainz returned: {response.status_code}")
            return None
    except Exception as e:
        print_warning(f"MusicBrainz error: {e}")
        return None

def chat_with_ai(message, model="microsoft/Phi-3-mini-4k-instruct"):
    """Send message to AI"""
    print_info("Sending to AI model...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "provider": "local",
                "model": model,
                "message": message,
                "conversation_id": "demo-chat",
                "max_tokens": 500
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("response", "No response")
        else:
            return f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error: {e}"

def demo_simple_lookup():
    """Demo 1: Simple information lookup"""
    print_header("Demo 1: Simple Information Lookup")
    
    artist = "The Beatles"
    
    # Get Wikipedia data
    wiki_data = test_wikipedia(artist)
    
    if wiki_data:
        # Show snippet of what we got
        results = wiki_data.get("results", [])
        if results:
            print()
            print(f"{BOLD}Wikipedia found:{END}")
            print(f"  Title: {results[0].get('title', 'N/A')}")
            print(f"  Snippet: {results[0].get('snippet', 'N/A')[:100]}...")
    
    print()
    input(f"{BOLD}Press Enter to continue...{END}")

def demo_enhanced_chat():
    """Demo 2: AI chat enhanced with external data"""
    print_header("Demo 2: AI Chat with External Knowledge")
    
    artist = "Pink Floyd"
    question = f"Tell me about {artist}'s most famous album"
    
    print_info(f"User asks: {question}")
    print()
    
    # Option 1: Just ask AI (no external data)
    print(f"{YELLOW}Option A: AI without external data{END}")
    response_basic = chat_with_ai(question)
    print(f"\n{response_basic}\n")
    
    print(f"{BOLD}{'─'*70}{END}\n")
    
    # Option 2: Enhance with Wikipedia
    print(f"{GREEN}Option B: AI with Wikipedia data{END}")
    wiki_data = test_wikipedia(artist)
    
    if wiki_data and wiki_data.get("results"):
        # Create enhanced prompt
        wiki_summary = wiki_data["results"][0].get("snippet", "")
        enhanced_prompt = f"""Based on this Wikipedia information about {artist}:

{wiki_summary}

{question}"""
        
        response_enhanced = chat_with_ai(enhanced_prompt)
        print(f"\n{response_enhanced}\n")
    
    print()
    input(f"{BOLD}Press Enter to continue...{END}")

def demo_music_metadata():
    """Demo 3: Get structured music metadata"""
    print_header("Demo 3: Structured Music Metadata")
    
    artist = "Queen"
    
    # Get MusicBrainz data
    mb_data = test_musicbrainz(artist)
    
    if mb_data:
        print()
        print(f"{BOLD}MusicBrainz Metadata:{END}")
        print(f"  Artist: {mb_data.get('name', 'N/A')}")
        print(f"  Type: {mb_data.get('type', 'N/A')}")
        print(f"  Country: {mb_data.get('country', 'N/A')}")
        print(f"  ID: {mb_data.get('id', 'N/A')}")
        
        # Get discography
        artist_id = mb_data.get('id')
        if artist_id:
            try:
                print()
                print_info("Fetching discography...")
                disco_response = requests.get(
                    f"{BASE_URL}/api/mb/artist/{artist_id}/discography",
                    params={"limit": 10}
                )
                
                if disco_response.status_code == 200:
                    disco_data = disco_response.json()
                    summary = disco_data.get('summary', {})
                    
                    print()
                    print(f"{BOLD}Discography Summary:{END}")
                    print(f"  Total Releases: {summary.get('totalCount', 0)}")
                    print(f"  Date Range: {summary.get('firstReleaseDate', 'N/A')} - {summary.get('lastReleaseDate', 'N/A')}")
                    
                    # Show some albums
                    releases = disco_data.get('releaseGroups', [])[:5]
                    if releases:
                        print()
                        print(f"{BOLD}Top Albums:{END}")
                        for release in releases:
                            print(f"  • {release.get('title', 'N/A')} ({release.get('first-release-date', 'N/A')})")
            except:
                pass
    
    print()
    input(f"{BOLD}Press Enter to continue...{END}")

def demo_interactive():
    """Demo 4: Interactive Q&A with knowledge"""
    print_header("Demo 4: Interactive Music Q&A")
    
    print("Ask questions about music artists!")
    print("Type 'quit' to exit")
    print()
    
    while True:
        question = input(f"{BOLD}Your question:{END} ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            break
        
        if not question:
            continue
        
        # Simple entity extraction
        # Look for quoted names or capitalized words
        entities = re.findall(r'"([^"]+)"', question)
        if not entities:
            entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question)
        
        print()
        
        # Try to enhance with data if we found an entity
        enhanced_question = question
        if entities:
            entity = entities[0]
            print_info(f"Looking up: {entity}")
            
            # Try Wikipedia
            wiki_data = test_wikipedia(entity)
            if wiki_data and wiki_data.get("results"):
                snippet = wiki_data["results"][0].get("snippet", "")
                if snippet:
                    enhanced_question = f"""Context: {snippet}

Question: {question}"""
        
        # Ask AI
        print()
        response = chat_with_ai(enhanced_question)
        print(f"\n{CYAN}{response}{END}\n")
        print(f"{BOLD}{'─'*70}{END}\n")

def main():
    """Main entry point"""
    print_header("🎵 AI + Wikipedia + MusicBrainz Demo")
    
    # Check backend
    print_info("Checking backend...")
    if not check_backend():
        print_warning("Backend is not running!")
        print()
        print("Please start the backend first:")
        print("  cd backend")
        print("  python -m uvicorn main:app --reload")
        print()
        return
    
    print_success("Backend is running!")
    print()
    
    # Menu
    while True:
        print(f"{BOLD}Choose a demo:{END}")
        print()
        print("1. Simple Wikipedia/MusicBrainz lookup")
        print("2. AI chat comparison (with/without external data)")
        print("3. Structured music metadata")
        print("4. Interactive Q&A (try it yourself!)")
        print("5. Exit")
        print()
        
        choice = input(f"{BOLD}Your choice (1-5):{END} ").strip()
        
        if choice == "1":
            demo_simple_lookup()
        elif choice == "2":
            demo_enhanced_chat()
        elif choice == "3":
            demo_music_metadata()
        elif choice == "4":
            demo_interactive()
        elif choice == "5":
            print()
            print_info("Goodbye!")
            break
        else:
            print_warning("Invalid choice")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_info("Exiting...")

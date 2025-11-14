"""
API Key Generator for AI Hub
Generates secure API keys with jpnohub- prefix
"""
import secrets
import string


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure API key with jpnohub- prefix
    
    Args:
        length: Length of the random part (default 32 characters)
        
    Returns:
        API key string in format: jpnohub-{random_string}
    """
    # Use URL-safe characters (letters, digits, - and _)
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    return f"jpnohub-{random_part}"


def is_valid_api_key(api_key: str) -> bool:
    """
    Validate if an API key follows the jpnohub- format
    
    Args:
        api_key: The API key to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not api_key:
        return False
    
    # Check prefix
    if not api_key.startswith("jpnohub-"):
        return False
    
    # Check length (prefix + at least 20 characters)
    if len(api_key) < 28:  # "jpnohub-" (8) + 20 chars minimum
        return False
    
    # Check that it only contains valid characters
    key_part = api_key[8:]  # Remove prefix
    valid_chars = set(string.ascii_letters + string.digits + "-_")
    return all(c in valid_chars for c in key_part)


if __name__ == "__main__":
    print("=" * 60)
    print("AI Hub API Key Generator")
    print("=" * 60)
    print()
    print("Generated API Keys (keep these secure!):")
    print()
    
    # Generate 3 API keys
    for i in range(3):
        api_key = generate_api_key()
        print(f"Key {i+1}: {api_key}")
    
    print()
    print("=" * 60)
    print("Usage:")
    print("1. Copy one of the keys above")
    print("2. Add to your .env file: BOT_API_KEY=jpnohub-...")
    print("3. Restart AI Hub")
    print("4. Use the key in API requests via X-API-Key header")
    print("=" * 60)

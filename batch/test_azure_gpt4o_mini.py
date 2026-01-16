"""Test Azure OpenAI GPT-4o-mini access."""

import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_settings

def test_azure_gpt4o_mini():
    """Test connection to Azure OpenAI GPT-4o-mini."""
    settings = get_settings()
    
    print(f"Azure OpenAI Endpoint: {settings.azure_openai_endpoint}")
    print(f"API Version: {settings.azure_openai_api_version}")
    print(f"GPT-4o-mini Deployment: {settings.azure_openai_gpt4o_mini_deployment}")
    print()
    
    try:
        from openai import AzureOpenAI
    except ImportError:
        print("❌ Error: openai package not installed")
        print("Install with: pip install openai")
        return False
    
    try:
        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        
        print("Testing GPT-4o-mini...")
        response = client.chat.completions.create(
            model=settings.azure_openai_gpt4o_mini_deployment,
            messages=[
                {"role": "user", "content": "Say 'Hello from GPT-4o-mini!' and nothing else."}
            ],
            max_tokens=20,
            temperature=0.1,
        )
        
        result = response.choices[0].message.content
        print(f"✓ GPT-4o-mini response: {result}")
        print(f"✓ Model used: {response.model}")
        print(f"✓ Tokens used: {response.usage.total_tokens}")
        print()
        print("✅ Azure OpenAI GPT-4o-mini is working!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_azure_gpt4o_mini()
    sys.exit(0 if success else 1)

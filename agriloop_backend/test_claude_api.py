import asyncio
from anthropic import AsyncAnthropic
import os
from dotenv import load_dotenv

load_dotenv()

async def test_claude():
    api_key = os.getenv("CLAUDE_API_KEY")
    print(f"API Key (first 20 chars): {api_key[:20]}...")
    print(f"API Key length: {len(api_key)}")
    
    client = AsyncAnthropic(api_key=api_key)
    
    # Test different models
    models_to_test = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20240620",
    ]
    
    for model in models_to_test:
        try:
            print(f"\nTesting model: {model}")
            response = await client.messages.create(
                model=model,
                max_tokens=100,
                messages=[{"role": "user", "content": "Say hello"}]
            )
            print(f"✅ SUCCESS with {model}")
            print(f"Response: {response.content[0].text}")
            break
        except Exception as e:
            print(f"❌ FAILED with {model}: {e}")

if __name__ == "__main__":
    asyncio.run(test_claude())

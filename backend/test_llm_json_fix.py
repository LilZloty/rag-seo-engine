import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.llm_providers.grok import GrokProvider

async def test_grok_non_json():
    print("Testing Grok with json_mode=False...")
    try:
        provider = GrokProvider()
        result = await provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello World' and nothing else.",
            json_mode=False
        )
        print(f"Result: {result}")
        if isinstance(result, dict) and "content" in result:
            print("✅ Success: Result is a dict with 'content' key.")
        else:
            print("❌ Failure: Result format unexpected.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_grok_non_json())

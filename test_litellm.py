import litellm
import os
import asyncio

litellm.set_verbose = True

async def main():
    try:
        response = await litellm.acompletion(
            model="gemini/gemini-1.5-flash",
            messages=[{"role": "user", "content": "hello"}],
            api_key=os.getenv("GEMINI_API_KEY")
        )
        print("SUCCESS:", response)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(main())

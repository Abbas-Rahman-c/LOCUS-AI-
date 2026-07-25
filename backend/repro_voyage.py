import asyncio
import os
import traceback
import voyageai

async def main():
    api_key = os.environ.get("VOYAGE_API_KEY")
    print("Key present:", bool(api_key), "starts with:", (api_key or "")[:6])
    try:
        response = await voyageai.Embedding.acreate(
            input=["test question"],
            model="voyage-4",
            input_type="query",
            output_dimension=1024,
            truncation=True,
            api_key=api_key,
            request_timeout=30.0,
        )
        print("SUCCESS:", response)
    except Exception as exc:
        print("REAL ERROR TYPE:", type(exc).__name__)
        print("REAL ERROR MESSAGE:", str(exc))
        print("REAL ERROR ARGS:", exc.args)
        traceback.print_exc()

asyncio.run(main())
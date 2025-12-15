# testing one threaded aiohttp server/client setup with multiple async users

import os
import asyncio
import time
import uuid
import pandas as pd
# --- CHANGE 1: Import AsyncOpenAI instead of the synchronous client ---
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CHANGE 2: Instantiate the Asynchronous Client ---
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

timeline = []
user_cache = {}

# --- The function is now truly non-blocking without using to_thread ---
async def send_message(user_id, correlation_id, message):
    previous_response_id = user_cache.get(user_id)

    # Note: Using the standard OpenAI API structure, we will use 'messages' 
    # and provide the history as context instead of a custom 'responses' endpoint
    # to maintain compatibility with the standard async client.
    messages_payload = [
        {"role": "user", "content": message}
    ]
    
    # In a real-world scenario, you would manage conversation history here.
    # For this test, we simulate varying response times by varying question length.

    payload = {
        "model": "gpt-4o-mini",  # Using a fast, modern model
        "messages": messages_payload,
        # 'stream=True' is usually for streaming, keeping it simple here.
    }

    sent_time = time.time()

    timeline.append({
        "time": sent_time,
        "event": "send",
        "user_id": user_id,
        "correlation_id": correlation_id,
        "previous_context_id": previous_response_id,
        "payload": {"model": payload["model"], "message": message},
        "response_id": None, 
        "text": message
    })

    print(f"\n➡️ Sending ({correlation_id}) from {user_id} at {sent_time:.3f}s")
    print(f"   Payload sent: Model: {payload['model']}, Message: '{message[:30]}...'")

    # ---- CALL ----
    # This is the key change: 'await client.chat.completions.create' 
    # This call is *natively non-blocking* and does not require a thread switch.
    # The single Event Loop thread manages the I/O for this call.
    try:
        # Note: Using the chat completions API, which is standard for OpenAI
        response = await client.chat.completions.create(**payload)
    except Exception as e:
        print(f"Error during OpenAI call for {user_id}: {e}")
        return None

    received_time = time.time()
    
    # Extract the necessary data
    response_id = response.id
    output_text = response.choices[0].message.content
    
    # Store the new response ID (Simulating memory context update)
    user_cache[user_id] = response_id

    output_preview = output_text[:200]

    timeline.append({
        "time": received_time,
        "event": "receive",
        "user_id": user_id,
        "correlation_id": correlation_id,
        "payload": output_preview,
        "response_id": response_id,
        "internal_request_id": None, # OpenAI API often doesn't expose a simple internal ID
        "text": output_preview
    })

    print(f"\n🔹 Received response for {correlation_id} | User: {user_id}")
    print(f"   🔗 Correlation ID (Client): {correlation_id}")
    print(f"   🔗 OpenAI Response ID:      {response_id}")
    print(f"   Text: {output_preview}\n")

    return {
        "user_id": user_id,
        "correlation_id": correlation_id,
        "response_id": response_id,
        "text": output_text,
        "sent_time": sent_time,
        "received_time": received_time
    }

async def user_session(user_id, messages):
    results = []
    for msg in messages:
        correlation_id = uuid.uuid4().hex[:8]
        # Messages within a session are sequential for that user
        resp = await send_message(user_id, correlation_id, msg)
        if resp:
            results.append(resp)
    return results

async def main():
    # --- ADDED 3 MORE USERS (d4, e5, f6) with varying lengths ---
    users = {
        "a1": [
            "Where is the Taj Mahal? (Very short, fast)",
            "Where is the Eiffel Tower?",
            "Confirm both locations again."
        ],
        "b2": [
            "Write a 100 word story.",
            "Convert it into a 100 word poem.",
            "Write the next part (100 words)."
        ],
        "c3": [
            "Hello",
            "How does a diesel engine work? (500 words detailed explanation)", # Longest request
            "Summarize in 200 words."
        ],
        "d4": [
            "What is Python?",
            "Explain Python's GIL in 200 words.", # Medium length
            "Give a short coding example."
        ],
        "e5": [
            "What is a black hole?",
            "Explain gravitational lensing in 100 words.", # Medium length
            "Name the four fundamental forces."
        ],
        "f6": [
            "Say Hi (shortest)",
            "Write a 250 word motivational speech.",
            "Translate the speech into French." # Longest processing
        ]
    }

    print("🔵 Running pure async multi-user stress test (Single Thread)...\n")
    
    start_time = time.time()

    # Main part that makes python run all 6 user sessions concurrently 
    tasks = [user_session(uid, msgs) for uid, msgs in users.items()]
    # asyncio.gather runs all 6 tasks concurrently, waiting for all of them
    results = await asyncio.gather(*tasks)

    end_time = time.time()
    total_duration = end_time - start_time
    
    # SORT TIMELINE
    sorted_log = sorted(timeline, key=lambda x: x["time"])
    t0 = sorted_log[0]["time"]

    print("\n" + "="*80)
    print(f"🚀 TOTAL EXECUTION TIME: {total_duration:.2f} seconds")
    print("="*80 + "\n")
    
    print("\n📊 FINAL MESSAGE FLOW LOG\n")
    print(f"{'Time':<7}{'Event':<10}{'User':<6}{'ClientCorrID':<12}{'ResponseID':<24}")
    print("-"*60)

    for entry in sorted_log:
        print(f"{entry['time'] - t0:<7.2f} {entry['event']:<10}{entry['user_id']:<6}"
              f"{entry['correlation_id']:<12}{str(entry.get('response_id')):<24}")

    # Save excel debug log
    df = pd.DataFrame(sorted_log)
    df["elapsed"] = df["time"] - t0
    df.to_excel("pure_async_debug_log.xlsx", index=False)
    print("\n📁 Saved debug log to: pure_async_debug_log.xlsx")

if __name__ == "__main__":
    # Note: On Python 3.11+, you can use asyncio.run(main()) 
    # to avoid issues, but using the loop directly is also fine.
    asyncio.run(main())
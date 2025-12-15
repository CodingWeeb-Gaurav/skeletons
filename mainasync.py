import os
import asyncio
import time
import uuid
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

timeline = []
user_cache = {}

async def send_message(user_id, correlation_id, message):
    previous_response_id = user_cache.get(user_id)

    payload = {
        "model": "gpt-4.1-mini",
        "input": message
    }

    if previous_response_id:
        payload["previous_response_id"] = previous_response_id

    sent_time = time.time()

    timeline.append({
        "time": sent_time,
        "event": "send",
        "user_id": user_id,
        "correlation_id": correlation_id,
        "previous_context_id": previous_response_id,
        "payload": payload,
        "response_id": None,  # Filled later
        "text": message
    })

    print(f"\n➡️ Sending ({correlation_id}) from {user_id} at {sent_time:.3f}s")
    print(f"   Payload sent: {payload}")

    # ---- CALL ----
    # Using asyncio.to_thread to run the blocking call in a separate thread
    # It will not block the main event loop, allowing other coroutines to run concurrently and keep the responses to the correct user. 
    # Because the thread that sent the request will handle the respective response when it comes back. Hence, no mix-up of responses between users.
    response = await asyncio.to_thread(client.responses.create, **payload)
    # Each blocking call to OpenAI API is run in its own thread, allowing multiple calls to be in-flight simultaneously. So more threads = more parallel users.

    received_time = time.time()

    # Store the new OPENAI response ID as memory context
    user_cache[user_id] = response.id

    # Extract internal request ID if available
    internal_req_id = getattr(response, "request_id", None)
    output = response.output_text[:200]

    timeline.append({
        "time": received_time,
        "event": "receive",
        "user_id": user_id,
        "correlation_id": correlation_id,
        "payload": output,
        "response_id": response.id,
        "internal_request_id": internal_req_id,
        "text": output
    })

    print(f"\n🔹 Received response for {correlation_id} | User: {user_id}")
    print(f"   🔗 Correlation ID (Client): {correlation_id}")
    print(f"   🔗 OpenAI Response ID:      {response.id}")
    print(f"   🔗 OpenAI Internal Req ID:  {internal_req_id}")
    print(f"   Text: {output}\n")

    return {
        "user_id": user_id,
        "correlation_id": correlation_id,
        "response_id": response.id,
        "internal_request_id": internal_req_id,
        "text": response.output_text,
        "sent_time": sent_time,
        "received_time": received_time
    }

async def user_session(user_id, messages):
    results = []
    for msg in messages:
        correlation_id = uuid.uuid4().hex[:8]
        resp = await send_message(user_id, correlation_id, msg)
        results.append(resp)
    return results

async def main():
    users = {
        "a1": [
            "Where is the Taj Mahal?",
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
            "How does a diesel engine work? (500 words)",
            "Summarize in 200 words."
        ],
        "d4": [
            "Explain quantum computing in simple terms.",
            "Based on that explanation, what are its practical applications?",
            "Compare quantum computing with classical computing in a table format.",
            "What are the biggest challenges in quantum computing today?"
        ],
        "e5": [
            "Describe the water cycle with a detailed explanation.",
            "Now explain how climate change affects the water cycle.",
            "Based on your previous answers, what mitigation strategies would you recommend?",
            "Create a short educational summary for middle school students."
        ],
        "f6": [
            "What are the main principles of agile software development?",
            "Explain Scrum methodology in detail.",
            "Compare this with similar methodologies.",
            "What are common pitfalls in agile transformations and how to avoid them?"
        ],
        "g7": [
            "Write a 150-word introduction about the history of artificial intelligence.",
            "Now discuss the ethical implications of AI development.",
            "What safeguards should be implemented for responsible AI?",
            "Summarize our conversation in 400 words."
        ],
        "h8": [
            "Explain the process of photosynthesis step by step.",
            "How does photosynthesis differ in C3, C4, and CAM plants?",
            "Can you explain this in simpler terms for a 10-year-old?",
            "Design an experiment to measure photosynthesis efficiency in different light conditions."
        ]
    }

    print("\n🔵 Running async multi-user stress test...\n")
    

    #Main part that makes python know to run multiple user sessions concurrently 
    tasks = [user_session(uid, msgs) for uid, msgs in users.items()]
    results = await asyncio.gather(*tasks)

    # SORT TIMELINE
    sorted_log = sorted(timeline, key=lambda x: x["time"])
    t0 = sorted_log[0]["time"]

    print("\n📊 FINAL MESSAGE FLOW LOG\n")
    print(f"{'Time':<7}{'Event':<10}{'User':<6}{'ClientCorrID':<12}{'ResponseID':<24}{'InternalReqID'}")
    print("-"*110)

    for entry in sorted_log:
        print(f"{entry['time'] - t0:<7.2f} {entry['event']:<10}{entry['user_id']:<6}"
              f"{entry['correlation_id']:<12}{str(entry.get('response_id')):<24}"
              f"{str(entry.get('internal_request_id'))}")

    # Save excel debug log
    df = pd.DataFrame(sorted_log)
    df["elapsed"] = df["time"] - t0
    df.to_excel("async_debug_log.xlsx", index=False)
    print("\n📁 Saved debug log to: async_debug_log.xlsx")

if __name__ == "__main__":
    asyncio.run(main())
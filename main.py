import os
import uuid
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conversation_state = {}
previous_response_id = None

print("\n🔵 Test mode: Enter exactly 3 messages.\n")

messages = []
for i in range(3):
    msg = input(f"Message {i+1}: ")
    messages.append(msg)

print("\n📤 Sending all messages (with timing)...\n")

send_times = {}
receive_times = {}

for msg in messages:
    correlation_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    request_payload = {
        "model": "gpt-4.1-mini",
        "input": msg,
    }

    if previous_response_id:
        request_payload["previous_response_id"] = previous_response_id

    print(f"➡️ Sending ({correlation_id}) at {round(start_time, 3)}s : {msg}")
    print(request_payload)
    print()

    send_times[correlation_id] = start_time

    response = client.responses.create(**request_payload)

    # Record response info
    end_time = time.time()
    receive_times[correlation_id] = end_time

    conversation_state[correlation_id] = {
        "message": msg,
        "response_id": response.id,
        "responseText": response.output_text,
        "duration": round(end_time - start_time, 3)
    }

    previous_response_id = response.id


print("\n📥 Responses received (unordered):\n")

for cid, data in conversation_state.items():
    print(f"🔹 CorrelationID: {cid}")
    print(f" Msg: {data['message']}")
    print(f" ResponseID: {data['response_id']}")
    print(f" ⏳ Duration: {data['duration']} seconds")
    print("----")


print("\n📌 Checking Execution Behavior:\n")

sorted_cids = list(send_times.keys())

for i, cid in enumerate(sorted_cids):
    print(f"Message {i+1} ({cid}):")
    print(f"  Sent at: {round(send_times[cid], 3)}s")
    print(f"  Response received at: {round(receive_times[cid], 3)}s")
    
    if i > 0:
        prev = sorted_cids[i-1]
        if send_times[cid] < receive_times[prev]:
            print("  ⚠️ Sent BEFORE previous response → PARALLEL behavior")
        else:
            print("  ✅ Sent AFTER previous response → SEQUENTIAL behavior")
    print()

print("\n📌 NOW SORTING BACK TO ORIGINAL ORDER...\n")

for msg in messages:
    match = next(v for v in conversation_state.values() if v["message"] == msg)
    print(f"🧩 {msg}  --->  {match['responseText']}\n")

print("\n✅ Timing test complete.\n")

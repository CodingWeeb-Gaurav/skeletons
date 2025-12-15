// main.js
import OpenAI from "openai";
import dotenv from "dotenv";
import { v4 as uuidv4 } from "uuid";
import fs from "fs";

dotenv.config();

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// Global timeline and per-user cache
const timeline = [];
const userCache = {};

// Send a message for a user
async function sendMessage(userId, correlationId, message) {
  const previousResponseId = userCache[userId];

  const payload = {
    model: "gpt-4.1-mini",
    input: message,
  };

  if (previousResponseId) {
    payload.previous_response_id = previousResponseId;
  }

  const sentTime = Date.now() / 1000;

  timeline.push({
    time: sentTime,
    event: "send",
    user_id: userId,
    correlation_id: correlationId,
    previous_context_id: previousResponseId,
    payload,
    response_id: null,
    text: message,
  });

  console.log(`\n➡️ Sending (${correlationId}) from ${userId} at ${sentTime.toFixed(3)}`);
  console.log("   Payload sent:", payload);

  // Non-blocking call to OpenAI API
  const response = await client.responses.create(payload);
  const receivedTime = Date.now() / 1000;

  userCache[userId] = response.id;
  const output = response.output_text.slice(0, 200);

  timeline.push({
    time: receivedTime,
    event: "receive",
    user_id: userId,
    correlation_id: correlationId,
    payload: output,
    response_id: response.id,
    internal_request_id: response.request_id || null,
    text: output,
  });

  console.log(`\n🔹 Received response for ${correlationId} | User: ${userId}`);
  console.log("   🔗 Correlation ID (Client):", correlationId);
  console.log("   🔗 OpenAI Response ID:     ", response.id);
  console.log("   🔗 OpenAI Internal Req ID: ", response.request_id || null);
  console.log("   Text:", output, "\n");

  return {
    user_id: userId,
    correlation_id: correlationId,
    response_id: response.id,
    internal_request_id: response.request_id || null,
    text: response.output_text,
    sent_time: sentTime,
    received_time: receivedTime,
  };
}

// Sequential messages per user
async function userSession(userId, messages) {
  const results = [];
  for (const msg of messages) {
    const correlationId = uuidv4().slice(0, 8);
    const resp = await sendMessage(userId, correlationId, msg);
    results.push(resp);
  }
  return results;
}

// Main function
async function main() {
  const users = {
    a1: ["Where is the Taj Mahal?", "Where is the Eiffel Tower?", "Confirm both locations again."],
    b2: ["Write a 100 word story.", "Convert it into a 100 word poem.", "Write the next part (100 words)."],
    c3: ["Hello", "How does a diesel engine work? (500 words)", "Summarize in 200 words."],
  };

  console.log("\n🔵 Running async multi-user stress test...\n");

  // Run all user sessions concurrently
  const tasks = Object.entries(users).map(([uid, msgs]) => userSession(uid, msgs));
  await Promise.all(tasks);

  // Sort timeline
  const sortedLog = timeline.sort((a, b) => a.time - b.time);
  const t0 = sortedLog[0]?.time || 0;

  console.log("\n📊 FINAL MESSAGE FLOW LOG\n");
  console.log(
    `${"Time".padEnd(7)}${"Event".padEnd(10)}${"User".padEnd(6)}${"ClientCorrID".padEnd(12)}${"ResponseID".padEnd(
      40
    )}${"InternalReqID"}`
  );
  console.log("-".repeat(110));

  for (const entry of sortedLog) {
    console.log(
      `${(entry.time - t0).toFixed(2).padEnd(7)}${entry.event.padEnd(10)}${entry.user_id.padEnd(6)}${entry.correlation_id.padEnd(
        12
      )}${String(entry.response_id).padEnd(40)}${entry.internal_request_id || ""}`
    );
  }

  // Save to JSON file for debugging
  fs.writeFileSync("async_debug_log.json", JSON.stringify(sortedLog, null, 2));
  console.log("\n📁 Saved debug log to: async_debug_log.json");
}

// Run
main().catch(console.error);

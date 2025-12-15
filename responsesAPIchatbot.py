"""
chatbot_skeleton.py
A generic template for building multi-user chatbots with custom tools and session management
"""

import os
import asyncio
import time
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Import your session manager module (assumed to exist)
# from session_manager import get_or_create_session, update_session

# ============================================================================
# SECTION 1: CONFIGURATION
# ============================================================================

CONTEXT_PAIRS_LIMIT = 6  # Create new session every N message pairs
MAX_TOKENS = 4000

# Active user sessions tracking for concurrent handling
active_user_sessions = {}  # chat_id -> { last_request_time, is_processing }

# ============================================================================
# SECTION 2: CUSTOM TOOL DEFINITIONS
# ============================================================================

# Define your custom tools here
# Each tool should return: { "success": bool, "data": Any, "message": str }
async def search_database(query: str, chat_id: str) -> Dict:
    """Example tool 1: Search database"""
    try:
        # Your custom tool implementation
        # results = await your_search_function(query)
        results = []
        return {
            "success": True,
            "data": results,
            "message": f"Found {len(results)} results"
        }
    except Exception as error:
        print(f"❌ [ChatID: {chat_id}] Error in search_database: {str(error)}")
        return {
            "success": False,
            "data": None,
            "message": "Failed to search database"
        }

async def process_data(data: Any, chat_id: str) -> Dict:
    """Example tool 2: Process data"""
    try:
        # Your custom tool implementation
        # processed = await your_processing_function(data)
        processed = {}
        return {
            "success": True,
            "data": processed,
            "message": "Data processed successfully"
        }
    except Exception as error:
        print(f"❌ [ChatID: {chat_id}] Error in process_data: {str(error)}")
        return {
            "success": False,
            "data": None,
            "message": "Failed to process data"
        }
    

# Tool mapping
available_tools = {
    "searchDatabase": search_database,
    "processData": process_data,
    # Add more tools as needed...
}

# ============================================================================
# SECTION 3: SYSTEM PROMPT & CONTEXT MANAGEMENT
# ============================================================================

# Define your system prompt with tool instructions
SYSTEM_PROMPT = """# ROLE: [YOUR BOT NAME] - [BOT PURPOSE]

[Describe your bot's purpose and personality here]

# TOOLS & INSTRUCTIONS:
You have access to the following tools. To use a tool, respond EXACTLY with:
TOOL_CALL:tool_name:parameters

Available tools:
1. searchDatabase - Use for: [describe when to use]
2. processData - Use for: [describe when to use]
[Add descriptions for other tools]

# RESPONSE FORMATS:
- [Specify expected response formats for each tool]
- [Specify general conversation format]
- [Any specific rules or constraints]

# GENERAL BEHAVIOR:
- [Bot personality traits]
- [Interaction guidelines]
- [Context handling rules]"""

def create_enhanced_system_prompt(session_context: Dict, user_history: List[str]) -> str:
    """Create enhanced system prompt with session context"""
    context_info = "🔄 CURRENT CONTEXT: No specific context available."
    
    # Add your custom context here based on session data
    if session_context:
        # Example: context_info = f"🔄 CURRENT SESSION DATA: {json.dumps(session_context, indent=2)}"
        pass
    
    history_info = ""
    if user_history and len(user_history) > 0:
        history_info = f"\n📝 RECENT INTERACTIONS: {' → '.join(user_history[-3:])}"
    
    return f"""{SYSTEM_PROMPT}

# CURRENT SESSION CONTEXT:
{context_info}{history_info}

# TOOL USAGE REMINDER:
- Call tools EXACTLY: TOOL_CALL:tool_name:parameters
- Wait for tool results before continuing
- Format tool responses appropriately"""

# ============================================================================
# SECTION 4: CORE UTILITIES
# ============================================================================

async def execute_tool_from_command(tool_command: str, current_message: str, chat_id: str) -> Optional[Dict]:
    """Execute tool based on AI's tool call command"""
    # Parse: TOOL_CALL:tool_name:parameters
    parts = tool_command.split(':')
    if len(parts) < 2 or parts[0] != 'TOOL_CALL':
        return None

    tool_name = parts[1]
    parameters = ':'.join(parts[2:]) if len(parts) > 2 else current_message

    # Find the tool
    tool_func = available_tools.get(tool_name)
    if not tool_func:
        return {
            "success": False,
            "data": None,
            "message": f'Tool "{tool_name}" is not available'
        }

    print(f"🛠️ [ChatID: {chat_id}] Executing tool: {tool_name} with parameters: '{parameters}'")
    
    try:
        result = await tool_func(parameters, chat_id)
        print(f"✅ [ChatID: {chat_id}] Tool {tool_name} completed: {result.get('message', '')}")
        return result
    except Exception as error:
        print(f"❌ [ChatID: {chat_id}] Tool {tool_name} error: {str(error)}")
        return {
            "success": False,
            "data": None,
            "message": f"Tool execution failed: {str(error)}"
        }

def extract_response_text(response) -> str:
    """Extract text from OpenAI Responses API output"""
    if not hasattr(response, 'output') or not isinstance(response.output, list):
        return ""
    
    for item in response.output:
        if hasattr(item, 'type') and item.type == "message" and hasattr(item, 'content'):
            for content_block in item.content:
                if (hasattr(content_block, 'type') and 
                    content_block.type in ["output_text", "text"] and 
                    hasattr(content_block, 'text')):
                    return content_block.text
    return ""

# ============================================================================
# SECTION 5: SESSION & CONTEXT MANAGEMENT
# ============================================================================

def should_reset_after_this_response(current_counter: int) -> bool:
    """Check if we need to reset context (create new session)"""
    return current_counter >= CONTEXT_PAIRS_LIMIT - 1

def get_recent_messages_with_current(chat_history: List[Dict], current_user_message: str, current_ai_response: str) -> List[Dict]:
    """Get recent messages for context reset"""
    if not chat_history:
        return []
    
    conversation_messages = [
        msg for msg in chat_history 
        if msg.get("role") in ["user", "assistant"]
    ]
    
    # Get last N conversation pairs (excluding current)
    recent_conversation = conversation_messages[-(2 * (CONTEXT_PAIRS_LIMIT - 1)):]
    
    # Add current conversation
    messages_with_current = [
        *recent_conversation,
        {"role": "user", "message": current_user_message},
        {"role": "assistant", "message": current_ai_response}
    ]
    
    return messages_with_current

async def update_session_fields(chat_id: str, update_data: Dict) -> Dict:
    """Helper to update session in database"""
    try:
        # Assuming session_manager has update functionality
        # return await session_manager.update_session(chat_id, update_data)
        # For now, return dummy data
        return {"success": True, "updated": update_data}
    except Exception as error:
        print(f"❌ [ChatID: {chat_id}] Error updating session: {str(error)}")
        raise error

# ============================================================================
# SECTION 6: CORE MESSAGE PROCESSING (SINGLE USER)
# ============================================================================

async def process_message_for_user(params: Dict) -> str:
    """Process message for a single user"""
    message = params.get("message", "")
    session_id = params.get("sessionID", "")
    chat_id = params.get("chatId", "")
    
    try:
        # 1. Mark user as processing (prevents duplicate concurrent requests for same user)
        active_user_sessions[chat_id] = {
            "is_processing": True,
            "last_request_time": time.time()
        }

        print(f"🎯 STARTING REQUEST [ChatID: {chat_id}]")
        print(f"💬 User Message: '{message[:100]}{'...' if len(message) > 100 else ''}'")

        # 2. Retrieve user session (memory isolation by chat_id)
        # session = await get_or_create_session(chat_id, session_id)
        # For demo, create a mock session
        session = {
            "sessionLengthCounter": 0,
            "chatSessionID": None,
            "customContext": {},
            "interactionHistory": [],
            "chatHistory": []
        }
        
        current_counter = session.get("sessionLengthCounter", 0)
        reset_after_this_response = should_reset_after_this_response(current_counter)
        previous_response_id = session.get("chatSessionID")

        # 3. Create enhanced prompt with session context
        enhanced_system_prompt = create_enhanced_system_prompt(
            session.get("customContext", {}),
            session.get("interactionHistory", [])
        )

        # 4. Prepare input for OpenAI
        input_messages = [
            {
                "type": "message",
                "role": "developer",
                "content": enhanced_system_prompt
            },
            {
                "type": "message",
                "role": "user",
                "content": message
            }
        ]

        # 5. Prepare payload for OpenAI Responses API
        openai_payload = {
            "model": "gpt-4o-mini",
            "input": input_messages,
            "max_output_tokens": MAX_TOKENS
        }
        
        if previous_response_id:
            openai_payload["previous_response_id"] = previous_response_id

        print(f"📤 [ChatID: {chat_id}] Calling OpenAI API...")
        
        # KEY POINT 1: Use asyncio.to_thread for non-blocking OpenAI calls
        # This allows multiple users to have concurrent API calls
        response = await asyncio.to_thread(client.responses.create, **openai_payload)
        
        print(f"✅ [ChatID: {chat_id}] OpenAI API call successful")
        
        new_response_id = response.id
        ai_text = extract_response_text(response)

        if not ai_text:
            raise Exception("No AI response text received from OpenAI")

        final_response = ai_text

        # 6. Check for tool calls
        if 'TOOL_CALL:' in ai_text:
            print(f"🔧 [ChatID: {chat_id}] AI requested tool call")
            
            import re
            tool_call_match = re.search(r'TOOL_CALL:[^\n]+', ai_text)
            tool_command = tool_call_match.group(0) if tool_call_match else ai_text
            
            # Execute the tool (returns to correct user via chat_id)
            tool_result = await execute_tool_from_command(tool_command, message, chat_id)
            
            if tool_result and tool_result.get("success"):
                # 7. Let AI process tool results (maintains conversational flow)
                tool_name = tool_command.split(':')[1]
                
                processing_input = [
                    {
                        "type": "message",
                        "role": "developer",
                        "content": f"""{enhanced_system_prompt}

TOOL RESULT PROCESSING: The tool "{tool_name}" returned results. 
Now provide a helpful response to the user based on these results."""
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": message
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": tool_command
                    },
                    {
                        "type": "message",
                        "role": "user",
                        "content": f"""Tool Results: {json.dumps(tool_result.get('data', {}), indent=2)}

Based on these results, provide a helpful response to my original message."""
                    }
                ]

                tool_processing_payload = {
                    "model": "gpt-4o-mini",
                    "input": processing_input,
                    "previous_response_id": new_response_id,
                    "max_output_tokens": MAX_TOKENS
                }

                # Process tool results through AI
                processed_response = await asyncio.to_thread(
                    client.responses.create, 
                    **tool_processing_payload
                )
                final_response = extract_response_text(processed_response) or tool_result.get("message", "")
                
                # Update with new response ID from tool processing
                await update_session_fields(chat_id, {
                    "chatSessionID": processed_response.id
                })
            else:
                final_response = "I encountered an error while processing your request. Please try again."

        # 8. Handle session counter and context reset
        if reset_after_this_response:
            print(f"🔄 [ChatID: {chat_id}] Creating new session (context reset)")
            
            # Get recent messages for new session
            recent_messages = get_recent_messages_with_current(
                session.get("chatHistory", []),
                message,
                final_response
            )

            valid_messages = [
                msg for msg in recent_messages 
                if msg.get("message") and msg["message"].strip()
            ]

            # Create new session input with history
            new_session_input = [
                {
                    "type": "message",
                    "role": "developer",
                    "content": create_enhanced_system_prompt(
                        session.get("customContext", {}),
                        session.get("interactionHistory", [])
                    ) + "\n\nCONTEXT: Continuing from recent conversation."
                },
                *[
                    {
                        "type": "message",
                        "role": msg.get("role"),
                        "content": msg.get("message") or msg.get("content", "")
                    }
                    for msg in valid_messages
                ]
            ]

            reset_payload = {
                "model": "gpt-4o-mini",
                "input": new_session_input,
                "max_output_tokens": MAX_TOKENS
            }

            # Create new session (no previous_response_id)
            new_session_response = await asyncio.to_thread(
                client.responses.create, 
                **reset_payload
            )
            new_session_id = new_session_response.id

            # Save new session ID and reset counter
            await update_session_fields(chat_id, {
                "chatSessionID": new_session_id,
                "sessionLengthCounter": 0
            })

            print(f"✅ [ChatID: {chat_id}] New session created with ID: {new_session_id}")
        else:
            # Normal flow - increment counter and save response ID
            new_counter = current_counter + 1
            await update_session_fields(chat_id, {
                "sessionLengthCounter": new_counter,
                "chatSessionID": new_response_id  # Save response ID for next call
            })

        print(f"🏁 COMPLETED REQUEST [ChatID: {chat_id}]")
        return final_response

    except Exception as err:
        print(f"❌ [ChatID: {chat_id}] Error: {str(err)}")
        raise err
    finally:
        # Clean up active session
        if chat_id in active_user_sessions:
            del active_user_sessions[chat_id]

# ============================================================================
# SECTION 7: MULTI-USER CONCURRENT HANDLING
# ============================================================================

async def send_message(params: Dict) -> str:
    """Main entry point for single user requests"""
    try:
        chat_id = params.get("chatId")
        
        # Prevent multiple concurrent requests from same user
        active_session = active_user_sessions.get(chat_id)
        if active_session and active_session.get("is_processing"):
            raise Exception("Please wait for your previous request to complete.")

        print(f"👥 Processing request for [ChatID: {chat_id}]")
        
        # Process this user's message
        result = await process_message_for_user(params)
        
        print(f"✅ [ChatID: {chat_id}] Request completed")
        return result

    except Exception as err:
        print(f"❌ Global error: {str(err)}")
        raise err

# KEY POINT 2: Handle multiple users concurrently
async def process_multiple_users(user_requests: List[Dict]) -> List[str]:
    """Process multiple users concurrently"""
    print(f"👥 Processing {len(user_requests)} users concurrently...")
    
    # Create independent tasks for all users
    tasks = [process_message_for_user(params) for params in user_requests]
    
    # KEY POINT: asyncio.gather sends all requests in parallel
    # Each user's request runs independently without blocking others
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle any exceptions
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ User {i} failed: {str(result)}")
            final_results.append(f"Error: {str(result)}")
        else:
            final_results.append(result)
    
    print(f"✅ All {len(user_requests)} users processed concurrently")
    return final_results

# ============================================================================
# SECTION 8: UTILITY FUNCTIONS
# ============================================================================

def get_active_user_count() -> int:
    """Get number of active users"""
    return len(active_user_sessions)

async def cleanup_inactive_sessions():
    """Clean up inactive sessions periodically"""
    while True:
        await asyncio.sleep(60)  # Run every minute
        now = time.time()
        timeout = 5 * 60  # 5 minutes
        inactive_users = []
        
        for chat_id, session in active_user_sessions.items():
            if now - session.get("last_request_time", 0) > timeout:
                inactive_users.append(chat_id)
        
        for chat_id in inactive_users:
            del active_user_sessions[chat_id]
            print(f"🧹 Cleaned up inactive session for ChatID: {chat_id}")

# ============================================================================
# SECTION 9: DEMO & TESTING
# ============================================================================

async def demo_concurrent_users():
    """Demo concurrent user processing"""
    user_requests = [
        {
            "chatId": "user1",
            "sessionID": "session1",
            "message": "Hello, how are you?"
        },
        {
            "chatId": "user2", 
            "sessionID": "session2",
            "message": "What's the weather like?"
        },
        {
            "chatId": "user3",
            "sessionID": "session3",
            "message": "Tell me a joke"
        }
    ]
    
    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_inactive_sessions())
    
    try:
        # Process users concurrently
        results = await process_multiple_users(user_requests)
        
        print("\n📊 Results:")
        for i, result in enumerate(results):
            print(f"User {i+1}: {result[:100]}{'...' if len(result) > 100 else ''}")
            
    finally:
        # Cancel cleanup task
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

# ============================================================================
# SECTION 10: HOW IT WORKS - PYTHON SPECIFIC
# ============================================================================

"""
KEY CONCEPT 1: Parallel OpenAI Requests in Python
--------------------------------------------------
In Python (unlike Node.js), we need explicit threading for concurrent I/O operations:
1. `asyncio.to_thread()` moves blocking OpenAI calls to separate threads
2. Event loop continues running while threads execute
3. Each user gets their own thread for API calls
4. Threads complete and return to their respective async contexts

KEY CONCEPT 2: Memory Isolation by chat_id
-------------------------------------------
- Each user's session is identified by chat_id
- Session data is stored/retrieved using chat_id
- Tool executions receive chat_id parameter
- Responses route back through async chain using chat_id

KEY CONCEPT 3: Custom Tools via Prompt
---------------------------------------
- Tools are async Python functions
- AI learns to call tools via prompt: "TOOL_CALL:tool_name:parameters"
- Tool results are processed by AI for natural responses

KEY CONCEPT 4: Async/Await Pattern
-----------------------------------
- All I/O operations are async (await)
- asyncio.gather() for concurrent processing
- Exception handling per user
- Clean resource management with try/finally

KEY CONCEPT 5: Responses API Session Management
------------------------------------------------
- Uses OpenAI Responses API with previous_response_id
- Creates new session every CONTEXT_PAIRS_LIMIT messages
- Maintains conversation state across calls
"""

if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_concurrent_users())
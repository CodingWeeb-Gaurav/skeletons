/* eslint-disable no-undef */
// chatbot-skeleton.js
// A generic template for building multi-user chatbots with custom tools and session management

const OpenAI = require("openai");

// Import your session manager module (assumed to exist)
const sessionManager = require("../services/sessionManager");

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// Configuration
const CONTEXT_PAIRS_LIMIT = 6; // Create new session every N message pairs
const MAX_TOKENS = 4000;

// Active user sessions tracking for concurrent handling
const activeUserSessions = new Map(); // chatId -> { lastRequestTime, isProcessing }

// ============================================================================
// SECTION 1: CUSTOM TOOL DEFINITIONS
// ============================================================================

// Define your custom tools here
// Each tool should return: { success: boolean, data: any, message: string }
const availableTools = {
  // Example tool 1: Search database
  searchDatabase: {
    function: async (query, chatId) => {
      try {
        // Your custom tool implementation
        const results = await yourSearchFunction(query);
        return {
          success: true,
          data: results,
          message: `Found ${results.length} results`
        };
      } catch (error) {
        console.error(`❌ [ChatID: ${chatId}] Error in searchDatabase:`, error.message);
        return {
          success: false,
          data: null,
          message: "Failed to search database"
        };
      }
    }
  },
  
  // Example tool 2: Process data
  processData: {
    function: async (data, chatId) => {
      try {
        // Your custom tool implementation
        const processed = await yourProcessingFunction(data);
        return {
          success: true,
          data: processed,
          message: "Data processed successfully"
        };
      } catch (error) {
        console.error(`❌ [ChatID: ${chatId}] Error in processData:`, error.message);
        return {
          success: false,
          data: null,
          message: "Failed to process data"
        };
      }
    }
  },
  
  // Add more tools as needed...
  // toolName: {
  //   function: async (parameters, chatId) => { ... }
  // }
};

// ============================================================================
// SECTION 2: SYSTEM PROMPT & CONTEXT MANAGEMENT
// ============================================================================

// Define your system prompt with tool instructions
// IMPORTANT: Teach AI to call tools using TOOL_CALL:tool_name:parameters format
const systemPrompt = `# ROLE: [YOUR BOT NAME] - [BOT PURPOSE]

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
- [Context handling rules]`;

// Create enhanced system prompt with session context
const createEnhancedSystemPrompt = (sessionContext, userHistory) => {
  let contextInfo = "🔄 CURRENT CONTEXT: No specific context available.";
  
  // Add your custom context here based on session data
  if (sessionContext) {
    // Example: contextInfo = `🔄 CURRENT SESSION DATA: ${JSON.stringify(sessionContext, null, 2)}`;
  }
  
  const historyInfo = userHistory && userHistory.length > 0
    ? `\n📝 RECENT INTERACTIONS: ${userHistory.slice(-3).join(' → ')}`
    : '';
  
  return `${systemPrompt}

# CURRENT SESSION CONTEXT:
${contextInfo}${historyInfo}

# TOOL USAGE REMINDER:
- Call tools EXACTLY: TOOL_CALL:tool_name:parameters
- Wait for tool results before continuing
- Format tool responses appropriately`;
};

// ============================================================================
// SECTION 3: CORE UTILITIES
// ============================================================================

// Execute tool based on AI's tool call command
const executeToolFromCommand = async (toolCommand, currentMessage, chatId) => {
  // Parse: TOOL_CALL:tool_name:parameters
  const parts = toolCommand.split(':');
  if (parts.length < 2 || parts[0] !== 'TOOL_CALL') {
    return null;
  }

  const toolName = parts[1];
  const parameters = parts.slice(2).join(':') || currentMessage;

  // Find and execute the tool
  const tool = availableTools[toolName];
  if (!tool) {
    return {
      success: false,
      data: null,
      message: `Tool "${toolName}" is not available`
    };
  }

  console.log(`🛠️ [ChatID: ${chatId}] Executing tool: ${toolName} with parameters: "${parameters}"`);
  
  try {
    const result = await tool.function(parameters, chatId);
    console.log(`✅ [ChatID: ${chatId}] Tool ${toolName} completed: ${result.message}`);
    return result;
  } catch (error) {
    console.error(`❌ [ChatID: ${chatId}] Tool ${toolName} error:`, error.message);
    return {
      success: false,
      data: null,
      message: `Tool execution failed: ${error.message}`
    };
  }
};

// Extract text from OpenAI Responses API output
const extractResponseText = (response) => {
  if (!response.output || !Array.isArray(response.output)) {
    return "";
  }

  for (const item of response.output) {
    if (item.type === "message" && item.content) {
      for (const contentBlock of item.content) {
        if ((contentBlock.type === "output_text" || contentBlock.type === "text") && contentBlock.text) {
          return contentBlock.text;
        }
      }
    }
  }
  return "";
};

// ============================================================================
// SECTION 4: SESSION & CONTEXT MANAGEMENT
// ============================================================================

// Check if we need to reset context (create new session)
const shouldResetAfterThisResponse = (currentCounter) => {
  return currentCounter >= CONTEXT_PAIRS_LIMIT - 1;
};

// Get recent messages for context reset
const getRecentMessagesWithCurrent = (chatHistory, currentUserMessage, currentAIResponse) => {
  if (!chatHistory || chatHistory.length === 0) {
    return [];
  }

  const conversationMessages = chatHistory.filter(msg =>
    msg.role === "user" || msg.role === "assistant"
  );

  // Get last N conversation pairs (excluding current)
  const recentConversation = conversationMessages.slice(-(2 * (CONTEXT_PAIRS_LIMIT - 1)));

  // Add current conversation
  const messagesWithCurrent = [
    ...recentConversation,
    { role: "user", message: currentUserMessage },
    { role: "assistant", message: currentAIResponse }
  ];

  return messagesWithCurrent;
};

// Helper to update session in database
const updateSessionFields = async (chatId, updateData) => {
  try {
    // Assuming sessionManager has update functionality
    return await sessionManager.updateSession(chatId, updateData);
  } catch (error) {
    console.error(`❌ [ChatID: ${chatId}] Error updating session:`, error.message);
    throw error;
  }
};

// ============================================================================
// SECTION 5: CORE MESSAGE PROCESSING (SINGLE USER)
// ============================================================================

async function processMessageForUser(params) {
  const { message, sessionID, chatId } = params;
  
  try {
    // 1. Mark user as processing (prevents duplicate concurrent requests for same user)
    activeUserSessions.set(chatId, { 
      isProcessing: true, 
      lastRequestTime: Date.now() 
    });

    console.log(`🎯 STARTING REQUEST [ChatID: ${chatId}]`);
    console.log(`💬 User Message: "${message.substring(0, 100)}${message.length > 100 ? '...' : ''}"`);

    // 2. Retrieve user session (memory isolation by chatID)
    let session = await sessionManager.getOrCreateSession(chatId, sessionID);
    
    const currentCounter = session.sessionLengthCounter || 0;
    const resetAfterThisResponse = shouldResetAfterThisResponse(currentCounter);
    let previousResponseId = session.chatSessionID; // OpenAI's previous message ID

    // 3. Create enhanced prompt with session context
    const enhancedSystemPrompt = createEnhancedSystemPrompt(
      session.customContext, // Your custom session data
      session.interactionHistory // User's history
    );

    // 4. Prepare input for OpenAI
    const input = [
      {
        type: "message",
        role: "developer",
        content: enhancedSystemPrompt
      },
      {
        type: "message",
        role: "user",
        content: message
      }
    ];

    // 5. Call OpenAI Responses API (NON-BLOCKING for other users)
    const openAIPayload = {
      model: "gpt-4o-mini", // or your preferred model
      input: input,
      previous_response_id: previousResponseId || undefined, // Stateful API
      max_output_tokens: MAX_TOKENS
    };

    console.log(`📤 [ChatID: ${chatId}] Calling OpenAI API...`);
    
    // KEY POINT 1: This await doesn't block other users because of JavaScript's async nature
    const response = await client.responses.create(openAIPayload);
    
    console.log(`✅ [ChatID: ${chatId}] OpenAI API call successful`);
    
    const newResponseID = response.id;
    let aiText = extractResponseText(response);

    if (!aiText) {
      throw new Error("No AI response text received from OpenAI");
    }

    let finalResponse = aiText;

    // 6. Check for tool calls
    if (aiText.includes('TOOL_CALL:')) {
      console.log(`🔧 [ChatID: ${chatId}] AI requested tool call`);
      
      const toolCallMatch = aiText.match(/TOOL_CALL:[^\n]+/);
      const toolCommand = toolCallMatch ? toolCallMatch[0] : aiText;
      
      // Execute the tool (returns to correct user via chatId)
      const toolResult = await executeToolFromCommand(toolCommand, message, chatId);
      
      if (toolResult && toolResult.success) {
        // 7. Let AI process tool results (maintains conversational flow)
        const toolName = toolCommand.split(':')[1];
        
        const processingInput = [
          {
            type: "message",
            role: "developer",
            content: `${enhancedSystemPrompt}

TOOL RESULT PROCESSING: The tool "${toolName}" returned results. 
Now provide a helpful response to the user based on these results.`
          },
          {
            type: "message",
            role: "user",
            content: message
          },
          {
            type: "message",
            role: "assistant",
            content: toolCommand
          },
          {
            type: "message",
            role: "user",
            content: `Tool Results: ${JSON.stringify(toolResult.data, null, 2)}

Based on these results, provide a helpful response to my original message.`
          }
        ];

        const toolProcessingPayload = {
          model: "gpt-4o-mini",
          input: processingInput,
          previous_response_id: newResponseID,
          max_output_tokens: MAX_TOKENS
        };

        // Process tool results through AI
        const processedResponse = await client.responses.create(toolProcessingPayload);
        finalResponse = extractResponseText(processedResponse) || toolResult.message;
        
        // Update with new response ID from tool processing
        await updateSessionFields(chatId, {
          chatSessionID: processedResponse.id
        });
      } else {
        finalResponse = "I encountered an error while processing your request. Please try again.";
      }
    }

    // 8. Handle session counter and context reset
    if (resetAfterThisResponse) {
      console.log(`🔄 [ChatID: ${chatId}] Creating new session (context reset)`);
      
      // Get recent messages for new session
      const recentMessages = getRecentMessagesWithCurrent(
        session.chatHistory, 
        message, 
        finalResponse
      );

      const validMessages = recentMessages.filter(msg =>
        msg.message && msg.message.trim() !== ''
      );

      // Create new session input with history
      const newSessionInput = [
        {
          type: "message",
          role: "developer",
          content: createEnhancedSystemPrompt(
            session.customContext,
            session.interactionHistory
          ) + "\n\nCONTEXT: Continuing from recent conversation."
        },
        ...validMessages.map(msg => ({
          type: "message",
          role: msg.role,
          content: msg.message || msg.content
        }))
      ];

      const resetPayload = {
        model: "gpt-4o-mini",
        input: newSessionInput,
        max_output_tokens: MAX_TOKENS
      };

      // Create new session (no previous_response_id)
      const newSessionResponse = await client.responses.create(resetPayload);
      const newSessionID = newSessionResponse.id;

      // Save new session ID and reset counter
      await updateSessionFields(chatId, {
        chatSessionID: newSessionID,
        sessionLengthCounter: 0
      });

      console.log(`✅ [ChatID: ${chatId}] New session created with ID: ${newSessionID}`);
    } else {
      // Normal flow - increment counter and save response ID
      const newCounter = currentCounter + 1;
      await updateSessionFields(chatId, {
        sessionLengthCounter: newCounter,
        chatSessionID: newResponseID // Save response ID for next call
      });
    }

    console.log(`🏁 COMPLETED REQUEST [ChatID: ${chatId}]`);
    return finalResponse;

  } catch (err) {
    console.error(`❌ [ChatID: ${chatId}] Error:`, err.message);
    throw err;
  } finally {
    // Clean up active session
    activeUserSessions.delete(chatId);
  }
}

// ============================================================================
// SECTION 6: MULTI-USER CONCURRENT HANDLING
// ============================================================================

// Main entry point for single user requests
exports.sendMessage = async (params) => {
  try {
    const { chatId } = params;
    
    // Prevent multiple concurrent requests from same user
    const activeSession = activeUserSessions.get(chatId);
    if (activeSession && activeSession.isProcessing) {
      throw new Error("Please wait for your previous request to complete.");
    }

    console.log(`👥 Processing request for [ChatID: ${chatId}]`);
    
    // Process this user's message
    const result = await processMessageForUser(params);
    
    console.log(`✅ [ChatID: ${chatId}] Request completed`);
    return result;

  } catch (err) {
    console.error(`❌ Global error:`, err.message);
    throw err;
  }
};

// KEY POINT 2: Handle multiple users concurrently
exports.processMultipleUsers = async (userRequests) => {
  console.log(`👥 Processing ${userRequests.length} users concurrently...`);
  
  // Create independent tasks for all users
  const tasks = userRequests.map(params => processMessageForUser(params));
  
  // KEY POINT: Promise.all sends all requests in parallel
  // Each user's request runs independently without blocking others
  const results = await Promise.all(tasks);
  
  console.log(`✅ All ${userRequests.length} users processed concurrently`);
  return results;
};

// ============================================================================
// SECTION 7: UTILITY FUNCTIONS
// ============================================================================

exports.getActiveUserCount = () => {
  return activeUserSessions.size;
};

// Clean up inactive sessions periodically
setInterval(() => {
  const now = Date.now();
  const timeout = 5 * 60 * 1000; // 5 minutes
  for (const [chatId, session] of activeUserSessions.entries()) {
    if (now - session.lastRequestTime > timeout) {
      activeUserSessions.delete(chatId);
      console.log(`🧹 Cleaned up inactive session for ChatID: ${chatId}`);
    }
  }
}, 60000);

// ============================================================================
// SECTION 8: HOW IT WORKS - KEY CONCEPTS
// ============================================================================

/*
KEY CONCEPT 1: Parallel OpenAI Requests for Multiple Users
----------------------------------------------------------
- Each user's `processMessageForUser()` runs independently
- `await client.responses.create()` doesn't block other users because:
  1. JavaScript's event loop continues while waiting for OpenAI response
  2. Each user has their own async function execution context
  3. When N users message simultaneously, N API calls are made in parallel
  4. The first response that comes back is processed immediately

KEY CONCEPT 2: Memory Isolation by chatID
------------------------------------------
- Each user's session is retrieved using: `sessionManager.getOrCreateSession(chatId, sessionID)`
- Session data (chatHistory, sessionLengthCounter, chatSessionID) is stored per chatId
- Tool executions receive chatId parameter to ensure results return to correct user

KEY CONCEPT 3: Custom Tools via Prompt (Not OpenAI Tools API)
-------------------------------------------------------------
- Tools are defined in `availableTools` object locally
- AI learns to call tools via prompt instructions: "TOOL_CALL:tool_name:parameters"
- Tool execution is handled manually, avoiding OpenAI tools integration complexity
- Tool results are fed back to AI for natural language processing

KEY CONCEPT 4: Response Routing to Correct User
------------------------------------------------
- chatId parameter is passed through all functions
- Tool functions receive chatId to fetch user-specific data
- Session updates use chatId to ensure data isolation
- Responses return through the original async call chain

KEY CONCEPT 5: Tool Response Format
-----------------------------------
Each tool returns: { success: boolean, data: any, message: string }
- success: Indicates if tool executed successfully
- data: The raw results from the tool
- message: Human-readable description of what happened

KEY CONCEPT 6: OpenAI Responses API & Session Management
--------------------------------------------------------
- Uses Responses API with `previous_response_id` for stateful conversations
- Creates new session every CONTEXT_PAIRS_LIMIT messages
- Saves response ID (`chatSessionID`) to user's session after each call
- Subsequent payloads include previous_response_id to maintain context
- When resetting, creates new session with last N messages, no previous_response_id
*/
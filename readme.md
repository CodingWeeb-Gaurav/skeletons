# Codes
- Purpose : Storing the skeletons of different codes. For future uses.

## main.py and main.js
    - Main ones for running different codes before saving with respective names.

## mainasync.js and mainasync.py
    - Uses OpenAI responses API instead of regular chat completions API. 
    - Simulates 3 users at same time each with 3 messages.
    - Shows that their memories are isolated.
    - Messages are sent simultaneously for different users without locking and waiting for response.
    - OpenAI's response to the API calls get routed to the correct user.
    - Enables proper concurrency and response routing.
    -Python handles concurrency differently than node, so there are 2 separate codes. 
    -Python needs asyncio.to_thread() for blocking OpenAI calls, while Node.js handles it automatically with its event loop.

## responsesAPIchatbot.js and .py
    - Full chatbot skeleton with multi tool calling.
    - Made on top of mainAsync.js and mainAsync.py
    - Here also python needs different error handling in asyncio.gather with [return_exceptions = True] and cleanup [asyncio.create_task]

    
## Testing server:
ssh -p 22 ubuntu@51.38.38.66
Techgropse@1234
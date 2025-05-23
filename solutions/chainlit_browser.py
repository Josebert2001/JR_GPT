import os
from typing import Optional, AsyncGenerator
from dotenv import load_dotenv
import chainlit as cl
import groq
from browser_tools import BrowserTools


# Load environment variables
load_dotenv()

# Initialize Groq client
client = groq.Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
TOP_P = float(os.getenv("TOP_P", "1.0"))


def get_prompt(instruction: str, history: Optional[list[str]] = None) -> str:
    if history:
        context = f"Previous conversation: {''.join(history)}\n\n"
    else:
        context = ""

    return f"{context}{instruction}"


async def generate_response(prompt: str) -> AsyncGenerator[str, None]:
    """Generate streaming response from Groq's LLaMA model."""
    system = """You are a helpful web browsing assistant powered by LLaMA 3.3 70B Versatile. You can help users browse the web by:
    1. Navigation: Use 'navigate to [url]' to visit websites
    2. Content Extraction: Use 'extract' to get and summarize webpage content
    3. Interaction: Use 'click [selector]' to click on elements
    4. Forms: Use 'fill [selector] with [value]' to input data
    
    Response Format:
    1. First, explain what you plan to do
    2. Then, use the exact command format for actions:
       - 'navigate to example.com'
       - 'extract'
       - 'click #submit-button'
       - 'fill #email with user@example.com'
    3. After each action, analyze and explain the results
    
    Important:
    - Always think step by step
    - Verify URLs and actions for safety
    - Be specific in your responses
    - Handle errors gracefully
    - Summarize extracted content concisely"""

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
            stream=True
        )

        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\nI apologize, but I encountered an error: {str(e)}\nPlease try again."


@cl.on_chat_start
async def on_chat_start():
    # Initialize browser tools
    browser_tools = BrowserTools()

    # Store in session
    cl.user_session.set("browser_tools", browser_tools)
    cl.user_session.set("history", [])

    await cl.Message(
        content="""👋 Hello! I'm your web browsing assistant powered by LLaMA 3.3 70B Versatile.

I can help you with:
• Navigating to websites
• Extracting and summarizing content
• Clicking on elements
• Filling out forms

Try asking me something like:
"Navigate to wikipedia.org and summarize the main page"
or
"Go to news.ycombinator.com and tell me the top 3 stories"

What would you like me to do?"""
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    browser_tools = cl.user_session.get("browser_tools")
    history = cl.user_session.get("history")

    try:
        # Create a new message with thinking indicator
        msg = cl.Message(content="")
        await msg.send()

        # Get LLM's response
        prompt = get_prompt(message.content, history)
        response = ""

        async for word in generate_response(prompt):
            if word:  # Only process non-empty tokens
                await msg.stream_token(word)
                response += word

        if not response.strip():  # If response is empty or just whitespace
            await msg.update(content="I apologize, but I didn't receive a proper response. Please try again.")
            return
    except Exception as e:
        await cl.Message(f"An error occurred: {str(e)}").send()
        return

    try:
        # Execute browser actions based on response
        if "navigate to" in response.lower():
            # Extract URL more reliably with error handling
            parts = response.lower().split("navigate to", 1)
            if len(parts) > 1:
                url = parts[1].split()[0].strip('"`\'., ')
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                result = await browser_tools.navigate(url)
                await msg.stream_token(f"\n\nNavigated to {url}. Result: {result}")

        elif "click" in response.lower():
            parts = response.lower().split("click", 1)
            if len(parts) > 1:
                selector = parts[1].split()[0].strip('"`\'., ')
                result = await browser_tools.click(selector)
                await msg.stream_token(f"\n\nClicked {selector}. Result: {result}")

        elif "fill" in response.lower():
            parts = response.lower().split("fill", 1)[1].split("with", 1)
            if len(parts) == 2:
                selector = parts[0].strip('"`\'., ')
                value = parts[1].strip('"`\'., ')
                result = await browser_tools.fill_form(selector, value)
                await msg.stream_token(f"\n\nFilled {selector} with value. Result: {result}")

        elif "extract" in response.lower():
            content = await browser_tools.extract_content()
            await msg.stream_token(f"\n\nExtracted content: {str(content)}")

        # Store the interaction in history
        history.append(response)
        await msg.update()

    except Exception as e:
        error_msg = f"\n\nError performing browser action: {str(e)}"
        await msg.stream_token(error_msg)


@cl.on_chat_end
async def on_chat_end():
    browser_tools = cl.user_session.get("browser_tools")
    if browser_tools:
        await browser_tools.cleanup()

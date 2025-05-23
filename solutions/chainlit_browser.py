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
MODEL = os.getenv("GROQ_MODEL", "llama2-70b-4096")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
TOP_P = float(os.getenv("TOP_P", "1.0"))


def get_prompt(instruction: str, history: Optional[list[str]] = None) -> str:
    system = """You are an AI assistant that can browse the web. You can:
    - Navigate to URLs to gather information
    - Extract and summarize page content
    - Click on elements and interact with web pages
    - Fill in forms and submit data
    Always think step by step, explain your reasoning, and verify each action for safety."""

    if history:
        context = f"\nPrevious conversation: {''.join(history)}\n"
    else:
        context = "\n"

    prompt = f"{system}{context}User: {instruction}\n\nAssistant:"
    return prompt


async def generate_response(prompt: str) -> AsyncGenerator[str, None]:
    """Generate streaming response from Groq's LLaMA model."""
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful AI assistant that can browse the web."},
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


@cl.on_chat_start
async def on_chat_start():
    # Initialize browser tools
    browser_tools = BrowserTools()

    # Store in session
    cl.user_session.set("browser_tools", browser_tools)
    cl.user_session.set("history", [])

    await cl.Message(
        "Hello! I can help you browse the web using LLaMA 3.3 70B. What would you like me to do?"
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    browser_tools = cl.user_session.get("browser_tools")
    history = cl.user_session.get("history")

    msg = cl.Message(content="")
    await msg.send()

    # Get LLM's response
    prompt = get_prompt(message.content, history)
    response = ""

    async for word in generate_response(prompt):
        await msg.stream_token(word)
        response += word

    # Execute browser actions based on response
    if "navigate to" in response.lower():
        url = response.split("navigate to")[-1].split()[0].strip('"`\'')
        result = await browser_tools.navigate(url)
        await msg.stream_token(f"\n\n{result}")

    elif "click" in response.lower():
        selector = response.split("click")[-1].split()[0].strip('"`\'')
        result = await browser_tools.click(selector)
        await msg.stream_token(f"\n\n{result}")

    elif "fill" in response.lower():
        parts = response.split("fill")[-1].split("with")
        if len(parts) == 2:
            selector = parts[0].strip().strip('"`\'')
            value = parts[1].strip().strip('"`\'')
            result = await browser_tools.fill_form(selector, value)
            await msg.stream_token(f"\n\n{result}")

    elif "extract" in response.lower():
        content = await browser_tools.extract_content()
        await msg.stream_token(f"\n\nExtracted content: {str(content)}")

    history.append(response)
    await msg.update()


@cl.on_chat_end
async def on_chat_end():
    browser_tools = cl.user_session.get("browser_tools")
    if browser_tools:
        await browser_tools.cleanup()

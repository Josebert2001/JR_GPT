import chainlit as cl
from browser_tools import BrowserTools
from ctransformers import AutoModelForCausalLM

def get_prompt(instruction: str, history: list[str] | None = None) -> str:
    system = """You are an AI assistant that can browse the web. You can:
    - Navigate to URLs
    - Extract page content
    - Click elements
    - Fill forms
    Always think step by step and verify each action."""
    
    prompt = f"### System:\n{system}\n\n### User:\n"
    if history:
        prompt += f"Previous conversation: {''.join(history)}. Now answer: "
    prompt += f"{instruction}\n\n### Response:\n"
    return prompt

@cl.on_chat_start
async def on_chat_start():
    # Initialize LLM
    llm = AutoModelForCausalLM.from_pretrained(
        "zoltanctoth/orca_mini_3B-GGUF",
        model_file="orca-mini-3b.q4_0.gguf"
    )
    
    # Initialize browser tools
    browser_tools = BrowserTools()
    
    # Store in session
    cl.user_session.set("llm", llm)
    cl.user_session.set("browser_tools", browser_tools)
    cl.user_session.set("history", [])
    
    await cl.Message(
        "Hello! I can help you browse the web. What would you like me to do?"
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    llm = cl.user_session.get("llm")
    browser_tools = cl.user_session.get("browser_tools")
    history = cl.user_session.get("history")
    
    msg = cl.Message(content="")
    await msg.send()
    
    # Get LLM's plan
    prompt = get_prompt(message.content, history)
    response = ""
    
    for word in llm(prompt, stream=True):
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
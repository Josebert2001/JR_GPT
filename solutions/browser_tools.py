from typing import Dict, Any, Optional
import asyncio
from playwright.async_api import async_playwright
import chainlit as cl

class BrowserTools:
    def __init__(self):
        self.browser = None
        self.page = None
        
    async def setup(self):
        """Initialize the browser if not already done"""
        if not self.browser:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch()
            self.page = await self.browser.new_page()
            
    async def cleanup(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None

    async def navigate(self, url: str) -> str:
        """Navigate to a URL"""
        try:
            await self.setup()
            await self.page.goto(url)
            return f"Successfully navigated to {url}"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"

    async def extract_content(self) -> Dict[str, Any]:
        """Extract content from the current page"""
        try:
            title = await self.page.title()
            content = await self.page.content()
            text = await self.page.evaluate("() => document.body.innerText")
            return {
                "title": title,
                "content": content,
                "text": text
            }
        except Exception as e:
            return {"error": f"Error extracting content: {str(e)}"}

    async def click(self, selector: str) -> str:
        """Click an element on the page"""
        try:
            await self.page.click(selector)
            return f"Clicked element: {selector}"
        except Exception as e:
            return f"Error clicking element: {str(e)}"

    async def fill_form(self, selector: str, value: str) -> str:
        """Fill a form field"""
        try:
            await self.page.fill(selector, value)
            return f"Filled form field {selector}"
        except Exception as e:
            return f"Error filling form: {str(e)}"
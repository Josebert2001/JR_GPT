from typing import Dict, Any, Optional
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout, Page, Browser


class BrowserError(Exception):
    """Base exception class for browser operations."""
    pass


class NavigationError(BrowserError):
    """Exception raised for navigation errors."""
    pass


class ContentExtractionError(BrowserError):
    """Exception raised for content extraction errors."""
    pass


class BrowserTools:
    """A class to handle browser-based operations with proper resource management and error handling.

    This class provides a wrapper around Playwright browser operations with proper
    error handling, resource management, and timeout controls.

    Attributes:
        browser (Browser): Playwright browser instance
        page (Page): Current browser page
        default_timeout (int): Default timeout for operations in milliseconds
    """

    def __init__(self, default_timeout: int = 30000):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.default_timeout = default_timeout
        self._playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate if a URL is properly formatted.

        Args:
            url (str): URL to validate

        Returns:
            bool: True if URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    async def setup(self):
        """Initialize the browser if not already done."""
        if not self.browser:
            try:
                print("Starting Playwright...")
                self._playwright = await async_playwright().start()
                print("Launching browser...")
                self.browser = await self._playwright.chromium.launch(
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--headless=new'
                    ],
                    headless=True
                )
                print("Creating new page...")
                self.page = await self.browser.new_page()
                await self.page.set_default_timeout(self.default_timeout)
                print("Setting up event handlers...")
                self.page.on("pageerror", lambda exc: print(f"Page error: {exc}"))
                self.page.on("crash", lambda: print("Page crashed"))
                print("Browser setup complete")
            except Exception as e:
                print(f"Browser initialization error: {str(e)}")
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None
                raise BrowserError(f"Failed to initialize browser: {str(e)}")

    async def cleanup(self):
        """Clean up browser resources safely."""
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass  # Ignore cleanup errors
            finally:
                self.browser = None
                self.page = None
                if self._playwright:
                    await self._playwright.stop()
                    self._playwright = None

    async def navigate(self, url: str, timeout: Optional[int] = None) -> str:
        """Navigate to a URL with enhanced error handling and validation."""
        if not self.page:
            await self.setup()

        # Validate and format URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        if not self.validate_url(url):
            raise NavigationError(f"Invalid URL format: {url}")

        try:
            response = await self.page.goto(
                url,
                timeout=timeout or self.default_timeout,
                wait_until='networkidle'
            )

            if not response:
                raise NavigationError(f"Failed to navigate to {url}: No response")

            if response.status >= 400:
                raise NavigationError(f"Failed to navigate to {url}: Status {response.status}")

            # Wait for page to be fully loaded
            await self.page.wait_for_load_state('networkidle')

            return f"Successfully navigated to {url}"

        except PlaywrightTimeout:
            raise NavigationError(f"Navigation to {url} timed out")
        except Exception as e:
            raise NavigationError(f"Failed to navigate to {url}: {str(e)}")

    async def extract_content(self, selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Extract content from the current page with enhanced selection."""
        if not self.page:
            raise BrowserError("Browser not initialized")

        try:
            # Default content extraction if no selectors provided
            content = {
                "title": await self.page.title(),
                "url": self.page.url,
                "text": await self.page.evaluate('document.body.innerText'),
                "main_content": await self.page.evaluate("""
                    () => {
                        const article = document.querySelector('article, main, [role="main"]');
                        if (article) return article.innerText;
                        const content = document.querySelector('.content, #content, [class*="content"]');
                        if (content) return content.innerText;
                        return document.body.innerText;
                    }
                """),
                "links": await self.page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]')).map(a => ({
                        text: a.innerText,
                        href: a.href
                    })).filter(link => link.text.trim() && link.href.startsWith('http'))
                """)
            }

            # Add custom selector content if provided
            if selectors:
                for key, selector in selectors.items():
                    try:
                        content[key] = await self.page.inner_text(selector)
                    except Exception as e:
                        content[key] = f"Failed to extract: {str(e)}"

            return content

        except Exception as e:
            raise ContentExtractionError(f"Failed to extract content: {str(e)}")

    async def click(self, selector: str, timeout: Optional[int] = None) -> str:
        """Click an element on the page with timeout.

        Args:
            selector (str): CSS selector for the element
            timeout (Optional[int]): Operation timeout in milliseconds

        Returns:
            str: Success message

        Raises:
            BrowserError: If click operation fails
        """
        try:
            await self.page.click(selector, timeout=timeout or self.default_timeout)
            return f"Clicked element: {selector}"
        except PlaywrightTimeout:
            raise BrowserError(f"Timeout waiting for element: {selector}")
        except Exception as e:
            raise BrowserError(f"Click operation failed: {str(e)}")

    async def fill_form(self, selector: str, value: str, timeout: Optional[int] = None) -> str:
        """Fill a form field with timeout.

        Args:
            selector (str): CSS selector for the form field
            value (str): Value to fill
            timeout (Optional[int]): Operation timeout in milliseconds

        Returns:
            str: Success message

        Raises:
            BrowserError: If form fill operation fails
        """
        try:
            await self.page.fill(selector, value, timeout=timeout or self.default_timeout)
            return f"Filled form field {selector}"
        except PlaywrightTimeout:
            raise BrowserError(f"Timeout waiting for form field: {selector}")
        except Exception as e:
            raise BrowserError(f"Form fill operation failed: {str(e)}")

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
        """Initialize the browser if not already done.

        Raises:
            BrowserError: If browser initialization fails
        """
        if not self.browser:
            try:
                self._playwright = await async_playwright().start()
                self.browser = await self._playwright.chromium.launch()
                self.page = await self.browser.new_page()
                await self.page.set_default_timeout(self.default_timeout)
            except Exception as e:
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
        """Navigate to a URL with timeout and validation.

        Args:
            url (str): URL to navigate to
            timeout (Optional[int]): Operation timeout in milliseconds

        Returns:
            str: Success message

        Raises:
            NavigationError: If navigation fails or URL is invalid
        """
        if not self.validate_url(url):
            raise NavigationError(f"Invalid URL format: {url}")

        try:
            await self.setup()
            await self.page.goto(url, timeout=timeout or self.default_timeout)
            return f"Successfully navigated to {url}"
        except PlaywrightTimeout:
            raise NavigationError(f"Navigation timeout: {url}")
        except Exception as e:
            raise NavigationError(f"Navigation failed: {str(e)}")

    async def extract_content(self, selectors: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Extract content from the current page with optional CSS selectors.

        Args:
            selectors (Optional[Dict[str, str]]): Dictionary of named selectors to extract

        Returns:
            Dict[str, Any]: Extracted content

        Raises:
            ContentExtractionError: If content extraction fails
        """
        try:
            result = {
                "title": await self.page.title(),
                "text": await self.page.evaluate("() => document.body.innerText")
            }

            # Extract content from specific selectors if provided
            if selectors:
                result["selected_content"] = {}
                for name, selector in selectors.items():
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            result["selected_content"][name] = await element.inner_text()
                    except Exception as e:
                        result["selected_content"][name] = f"Error: {str(e)}"

            return result
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

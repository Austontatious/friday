from playwright.sync_api import sync_playwright

def search_google(query: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.google.com")
        page.fill("input[name='q']", query)
        page.press("input[name='q']", "Enter")
        page.wait_for_selector("h3")
        results = page.query_selector_all("h3")
        top_results = [r.inner_text() for r in results[:3]]
        browser.close()
        return "\n".join(top_results)

def fetch_webpage(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            content = page.content()
            browser.close()
            return content[:5000]  # Trim to avoid overload
    except Exception as e:
        return f"❌ Failed to fetch {url}: {str(e)}"

from bs4 import BeautifulSoup
import re

def summarize_webpage(url: str) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")

        # Remove scripts/styles/ads
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        text = text[:5000]  # Limit context

        # You can swap this with a model call if needed
        return f"📰 Webpage Summary:\n{text[:1000]}..."

    except Exception as e:
        return f"❌ Failed to summarize {url}: {str(e)}"



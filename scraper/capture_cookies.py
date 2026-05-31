"""
One-time Twitter cookie capture using Playwright.

Opens a real Chrome browser, logs into X as @m_argus_k, then saves
the cookies to twitter_cookies.json in the format Twikit expects.
After this runs once, the main scraper uses the saved cookies
and never needs to go through the login flow again.

Run once:
  py -3 capture_cookies.py
"""
import asyncio
import json
import os
from pathlib import Path

COOKIES_FILE = Path(__file__).parent / "scraper" / "scraper" / "twitter_cookies.json"

USERNAME = os.environ.get("TWITTER_USERNAME", "m_argus_k")
EMAIL = os.environ.get("TWITTER_EMAIL", "mein0614444@gmail.com")
PASSWORD = os.environ.get("TWITTER_PASSWORD", "iamwatchingyou100")


async def capture() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Installing playwright...")
        os.system("pip install playwright && playwright install chromium")
        from playwright.async_api import async_playwright

    print(f"Opening browser to log into X as @{USERNAME}...")
    print("A browser window will open. If it gets stuck, complete the login manually.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://x.com/login")
        await page.wait_for_load_state("networkidle")

        try:
            # Enter username
            await page.wait_for_selector('[autocomplete="username"]', timeout=10000)
            await page.fill('[autocomplete="username"]', USERNAME)
            await page.press('[autocomplete="username"]', "Enter")
            await page.wait_for_timeout(2000)

            # Sometimes X asks for email/phone after username
            try:
                verify = page.locator('input[data-testid="ocfEnterTextTextInput"]')
                if await verify.is_visible(timeout=3000):
                    await verify.fill(EMAIL)
                    await page.press('input[data-testid="ocfEnterTextTextInput"]', "Enter")
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

            # Enter password
            await page.wait_for_selector('[autocomplete="current-password"]', timeout=10000)
            await page.fill('[autocomplete="current-password"]', PASSWORD)
            await page.press('[autocomplete="current-password"]', "Enter")
            await page.wait_for_timeout(5000)

        except Exception as e:
            print(f"Automated login failed ({e}). Please log in manually in the browser window.")
            print("Waiting 60 seconds for manual login...")
            await page.wait_for_timeout(60000)

        # Check if logged in
        current_url = page.url
        print(f"Current URL: {current_url}")

        if "login" not in current_url and "x.com" in current_url:
            print("Login detected! Extracting cookies...")
            cookies = await context.cookies("https://x.com")

            # Save in Twikit-compatible format
            COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(COOKIES_FILE, "w") as f:
                json.dump(cookies, f, indent=2)

            print(f"Saved {len(cookies)} cookies to {COOKIES_FILE}")
            print("Twitter scraping is now enabled. Run the scraper normally.")
        else:
            print("Could not detect successful login. Try Option A (manual cookie export).")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(capture())

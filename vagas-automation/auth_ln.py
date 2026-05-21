import asyncio
from playwright.async_api import async_playwright

async def capture_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        print("Acesse o LinkedIn e faça login manualmente...")
        await page.goto("https://www.linkedin.com/login")
        
        # Wait for user to login and reach feed
        await page.wait_for_url("**/feed/**", timeout=0)
        
        # Save state
        await context.storage_state(path="cookies.json")
        print("Sessão capturada e salva em cookies.json")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture_session())

# FILE: app/services/recon_service.py
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import asyncio
import re
import json
import random

# You would typically install this: pip install playwright-stealth
# For this code to run without it, we add a try/except block or manual injection.
try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

class Scraper:
    def __init__(self):
        self.playwright = None
        self.browser = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        
        # Launch with arguments that mimic a real display
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080"
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

    async def scrape_product_page(self, url: str):
        # Create context with random User Agent
        context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-US"
        )
        
        page = await context.new_page()
        
        # Apply Stealth (Crucial for RobotShop / Mouser)
        if stealth_async:
            await stealth_async(page)
        
        # Resource Optimization: Block junk to speed up scrape
        await page.route("**/*", lambda route: route.abort() 
            if route.request.resource_type in ["font", "media", "stylesheet", "other"] 
            else route.continue_()
        )

        try:
            # Randomize timeout to act human
            await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            
            # Anti-Lazy Load: Scroll naturally
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.0)

            content = await page.content()
            title = await page.title()
            soup = BeautifulSoup(content, 'html.parser')
            
            # --- EXTRACTION LOGIC ---
            
            # 1. Structured Data (Tables)
            tables_data = []
            for table in soup.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(cells) >= 2:
                        rows.append(" : ".join(cells))
                if rows:
                    tables_data.append("\n".join(rows))
            
            structured_specs = "\n--- SPEC TABLE ---\n".join(tables_data)

            # 2. Images
            images = self._extract_images(soup, page.url)

            # 3. Price
            price = self._extract_price(soup, content)

            # 4. Clean Text
            for tag in soup(["script", "style", "nav", "footer", "svg", "button", "iframe"]):
                tag.decompose()
            
            # Prioritize Lists (<ul> often contains "Features" or "Specs")
            ul_text = "\n".join([ul.get_text(separator="\n", strip=True) for ul in soup.find_all("ul")])
            body_text = soup.get_text(separator=' ', strip=True)
            
            clean_text = (ul_text + "\n" + body_text)[:12000]

            return {
                "title": title,
                "text": clean_text,
                "structured_tables": structured_specs,
                "image_url": images[0] if images else None,
                "images": images,
                "price": price
            }

        except Exception as e:
            print(f"   ❌ Scrape Error ({url[:30]}...): {e}")
            return None
        finally:
            await page.close()
            await context.close()

    def _extract_images(self, soup, base_url):
        candidates = set()
        # Common gallery classes in robotics ecommerce
        selectors = ['.gallery', '.product-images', '#image-block', '.slick-track', '.swiper-wrapper']
        
        for sel in selectors:
            for img in soup.select(f"{sel} img"):
                src = img.get('src') or img.get('data-src')
                if src: candidates.add(self._fix_url(src, base_url))
        
        # Fallback
        if not candidates:
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and 'product' in src.lower() and not 'icon' in src.lower():
                     candidates.add(self._fix_url(src, base_url))
                     
        return list(candidates)[:5]

    def _extract_price(self, soup, content_str):
        # 1. Regex (Fastest)
        # Look for $24.99 or 24.99 USD
        price_match = re.search(r'[\$€£]\s?(\d{1,4}\.\d{2})', content_str[:5000])
        if price_match:
            return float(price_match.group(1))
            
        # 2. Meta Tags (Most Reliable)
        meta = soup.find("meta", property="product:price:amount")
        if meta and meta.get("content"):
            return float(meta["content"])
            
        return None

    def _fix_url(self, src, base_url):
        if not src: return None
        if src.startswith("//"): return "https:" + src
        if src.startswith("/"): return urljoin(base_url, src)
        return src
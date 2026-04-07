#!/usr/bin/env python3
"""
Amazon Product Listings Scraper (ASYNC)
Scrapes Amazon search results and ensures clean product URLs and images
"""

import asyncio
import logging
import json
from typing import List, Dict
from playwright.async_api import async_playwright

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

AMAZON_BASE_URL = "https://www.amazon.com"
PLAYWRIGHT_TIMEOUT = 60000


class AmazonScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    # -----------------------------
    # Browser Setup
    # -----------------------------
    async def setup_browser(self) -> bool:
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Run in background
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-setuid-sandbox"
                ]
            )

            self.context = await self.browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )

            await self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            self.page = await self.context.new_page()
            self.page.set_default_timeout(PLAYWRIGHT_TIMEOUT)

            logger.info("✅ Browser setup successful")
            return True

        except Exception as e:
            logger.error(f"❌ Browser setup failed: {e}")
            return False

    # -----------------------------
    # URL Cleanup
    # -----------------------------
    def clean_product_url(self, url: str) -> str:
        if not url:
            return "N/A"
        if "/dp/" in url:
            asin = url.split("/dp/")[1].split("/")[0].split("?")[0]
            return f"{AMAZON_BASE_URL}/dp/{asin}"
        if "/gp/product/" in url:
            asin = url.split("/gp/product/")[1].split("/")[0].split("?")[0]
            return f"{AMAZON_BASE_URL}/dp/{asin}"
        return url

    # -----------------------------
    # Extract ASIN from various sources
    # -----------------------------
    async def extract_asin(self, product) -> str:
        """Extract ASIN from product element using multiple strategies"""

        # Strategy 1: data-asin attribute on container itself
        asin = await product.get_attribute("data-asin")
        if asin and asin != "":
            return asin

        # Strategy 2: data-asin attribute on child element (e.g., atc-faceout-container)
        try:
            asin_el = product.locator("[data-asin]").first
            if await asin_el.count() > 0:
                asin = await asin_el.get_attribute("data-asin")
                if asin and asin != "":
                    return asin
        except:
            pass

        # Strategy 3: data-csa-c-asin attribute on any child element
        try:
            asin_el = product.locator("[data-csa-c-asin]").first
            if await asin_el.count() > 0:
                asin = await asin_el.get_attribute("data-csa-c-asin")
                if asin:
                    return asin
        except:
            pass

        # Strategy 4: Extract from product link URL (/dp/ASIN/)
        try:
            link = product.locator('a[href*="/dp/"]').first
            if await link.count() > 0:
                href = await link.get_attribute("href")
                if href and "/dp/" in href:
                    # Extract ASIN from URL pattern /dp/B0XXXXXX/
                    asin = href.split("/dp/")[1].split("/")[0].split("?")[0]
                    if asin and len(asin) == 10:  # ASINs are 10 characters
                        return asin
        except:
            pass

        # Strategy 5: Extract from form input
        try:
            asin_input = product.locator('input[name="items[0.base][asin]"]').first
            if await asin_input.count() > 0:
                asin = await asin_input.get_attribute("value")
                if asin:
                    return asin
        except:
            pass

        return "N/A"

    # -----------------------------
    # Extract Product Info
    # -----------------------------
    async def extract_product(self, product) -> Dict[str, any]:
        data = {
            "asin": "N/A",
            "title": None,
            "product_url": None,
            "image_urls": [],
            "image_url": None
        }

        # ASIN - use multiple extraction strategies
        asin = await self.extract_asin(product)
        if asin and asin != "N/A":
            data["asin"] = asin
            data["product_url"] = f"{AMAZON_BASE_URL}/dp/{asin}"

        # Title - try multiple selectors
        try:
            # Try h2 span first (most common)
            title_el = product.locator("h2 span").first
            if await title_el.count() > 0:
                data["title"] = (await title_el.inner_text()).strip()
            else:
                # Fallback: h2 with aria-label
                h2_el = product.locator("h2[aria-label]").first
                if await h2_el.count() > 0:
                    data["title"] = await h2_el.get_attribute("aria-label")
        except:
            pass

        # ==============================
        # ENHANCED IMAGE EXTRACTION
        # ==============================
        try:
            image_urls_set = set()

            img_el = product.locator("img.s-image").first
            if await img_el.count() > 0:
                img_attrs = await img_el.evaluate("""
                    (el) => ({
                        src: el.src,
                        srcset: el.srcset,
                        dataDynamic: el.getAttribute('data-a-dynamic-image')
                    })
                """)

                # srcset extraction
                if img_attrs.get("srcset"):
                    parts = img_attrs["srcset"].split(",")
                    url = parts[-1].split()[0].strip()
                    if "media-amazon.com" in url:
                        image_urls_set.add(url.split("._")[0] + ".jpg")

                # data-a-dynamic-image extraction
                if img_attrs.get("dataDynamic"):
                    try:
                        images = json.loads(img_attrs["dataDynamic"])
                        for u in images.keys():
                            if "media-amazon.com" in u:
                                image_urls_set.add(u.split("._")[0] + ".jpg")
                    except:
                        pass

                # src fallback
                if img_attrs.get("src") and "media-amazon.com" in img_attrs["src"]:
                    image_urls_set.add(img_attrs["src"].split("._")[0] + ".jpg")

            if image_urls_set:
                data["image_urls"] = list(image_urls_set)
                data["image_url"] = data["image_urls"][0]

        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")

        return data

    # -----------------------------
    # Scrape Products (with pagination)
    # -----------------------------
    async def scrape_products(self, query: str, max_pages: int = None) -> List[Dict[str, any]]:
        """
        Scrape Amazon search results with pagination support.

        Args:
            query: Search term
            max_pages: Maximum pages to scrape. None = scrape all available pages.

        Returns:
            List of product dictionaries
        """
        if not await self.setup_browser():
            return []

        results = []
        current_page = 1

        try:
            logger.info(f"🔍 Searching Amazon for: '{query}'")
            await self.page.goto(AMAZON_BASE_URL, wait_until="domcontentloaded")
            await self.page.fill("#twotabsearchtextbox", query)
            await self.page.press("#twotabsearchtextbox", "Enter")
            await asyncio.sleep(3)

            while True:
                # Wait for search results - wait for any product card to appear
                await self.page.wait_for_selector('div[data-component-type="s-search-result"], div[data-cy="asin-faceout-container"]')

                # Select product cards - both regular and sponsored results
                # Regular: div[data-component-type="s-search-result"]
                # Sponsored: div[data-cy="asin-faceout-container"]
                products = self.page.locator('div[data-component-type="s-search-result"], div[data-cy="asin-faceout-container"]')

                # Extract products from current page
                page_count = await products.count()
                logger.info(f"📄 Page {current_page}: Found {page_count} products")

                for i in range(page_count):
                    item = await self.extract_product(products.nth(i))
                    if item["title"]:
                        results.append(item)

                # Check if we've reached max_pages limit
                if max_pages and current_page >= max_pages:
                    logger.info(f"✅ Reached max_pages limit ({max_pages})")
                    break

                # Scroll to bottom to ensure pagination is visible
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

                # Find the "Next" button - it's an <a> tag with class s-pagination-next
                # When on last page, Next becomes a disabled <span>, not <a>
                next_button = self.page.locator('a.s-pagination-next')

                if await next_button.count() > 0:
                    # Check if it's actually visible and clickable
                    is_visible = await next_button.is_visible()
                    if is_visible:
                        logger.info(f"➡️ Navigating to page {current_page + 1}")
                        await next_button.click()

                        # Wait for navigation and new results to load
                        await self.page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(2)
                        current_page += 1
                    else:
                        logger.info(f"✅ Next button not visible (stopped at page {current_page})")
                        break
                else:
                    logger.info(f"✅ No more pages available (stopped at page {current_page})")
                    break

            logger.info(f"✅ Successfully scraped {len(results)} products from {current_page} page(s)")

        finally:
            await self.close_browser()

        return results

    # -----------------------------
    # Close Browser
    # -----------------------------
    async def close_browser(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("✅ Browser closed")


# ==============================
# TEST RUN
# ==============================
if __name__ == "__main__":
    scraper = AmazonScraper()

    async def test():
        # Test with 2 pages for manual testing
        products = await scraper.scrape_products("laptop", max_pages=2)
        print(f"\n{'='*50}")
        print(f"Total products scraped: {len(products)}")
        print(f"{'='*50}")
        for p in products:
            print(f"\nASIN: {p['asin']}")
            print(f"Title: {p['title']}")
            print(f"Images: {len(p['image_urls'])}")

    asyncio.run(test())

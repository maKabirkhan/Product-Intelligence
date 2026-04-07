#!/usr/bin/env python3
"""
Amazon Product Detail Scraper (ASYNC)
COMPLETE scraper for ALL metadata + images
Enhanced with robust selectors and fallbacks
"""

import asyncio
import logging
import re
import json
from typing import Dict, Optional, List
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

PLAYWRIGHT_TIMEOUT = 60000


class AmazonProductScraper:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def setup_browser(self) -> bool:
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            self.page.set_default_timeout(PLAYWRIGHT_TIMEOUT)
            logger.info("✅ Browser setup successful")
            return True
        except Exception as e:
            logger.error(f"❌ Browser setup failed: {e}")
            return False

    def clean_asin(self, url: str) -> Optional[str]:
        match = re.search(r"/dp/([A-Z0-9]{10})", url)
        return match.group(1) if match else None

    async def _try_selectors(self, selectors: List[str], attribute: str = "text") -> Optional[str]:
        """Try multiple selectors and return first match"""
        for selector in selectors:
            try:
                el = self.page.locator(selector).first
                if await el.count() > 0:
                    if attribute == "text":
                        return (await el.inner_text()).strip()
                    else:
                        return await el.get_attribute(attribute)
            except:
                continue
        return None

    async def scrape_product(self, product_url: str) -> Dict:
        """Scrape COMPLETE product data with all metadata"""
        if not product_url or product_url == "N/A":
            return {}

        if not await self.setup_browser():
            return {}

        data = {
            # Core Identity
            "asin": self.clean_asin(product_url),
            "title": None,
            "brand": None,
            "brand_store_url": None,

            # Pricing & Financials
            "current_price": None,
            "list_price": None,
            "savings_percent": None,
            "price_per_unit": None,
            "currency": "USD",
            "coupon": None,

            # Ratings & Social Proof
            "average_rating": None,
            "reviews_count": None,
            "monthly_sales": None,

            # Badges & Designations
            "is_amazons_choice": False,
            "is_climate_pledge": False,
            "is_best_seller": False,
            "badges": [],

            # Inventory & Shipping
            "availability": None,
            "ships_from": None,
            "shipping_cost": None,
            "delivery_date": None,

            # Product Details
            "description": None,
            "bullet_points": [],
            "ingredients": None,
            "category": None,

            # Specifications (all product-specific details go here)
            "specifications": {},

            # Media
            "image_urls": [],
            "image_url": None,
            "video_count": None,

            # OCR Columns
            "ocr_processed": False,
            "ocr_status": "pending",
            "ocr_text": None
        }

        try:
            logger.info(f"🔍 Visiting: {product_url}")
            await self.page.goto(product_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # ==================== TITLE ====================
            try:
                data["title"] = (await self.page.locator("#productTitle").inner_text()).strip()
                logger.info(f"✓ Title: {data['title'][:50]}...")
            except:
                logger.warning("⚠️ Title not found")

            # ==================== BRAND ====================
            try:
                brand_el = self.page.locator("#bylineInfo")
                if await brand_el.count() > 0:
                    brand_text = await brand_el.inner_text()
                    brand_text = re.sub(r'^(Visit the|Brand:)\s*', '', brand_text, flags=re.IGNORECASE)
                    brand_text = brand_text.replace(" Store", "").strip()
                    data["brand"] = brand_text
                    try:
                        data["brand_store_url"] = await brand_el.get_attribute("href")
                    except:
                        pass
                    logger.info(f"✓ Brand: {data['brand']}")
            except:
                pass

            # Fallback: Extract from title
            if not data["brand"] and data["title"]:
                words = data["title"].split()
                if len(words) > 0:
                    data["brand"] = words[0].strip(',')

            # ==================== PRICING (Multiple Fallbacks) ====================
            # Current Price - try multiple selectors
            price_selectors = [
                'span.a-price.priceToPay span.a-offscreen',
                '#corePrice_feature_div span.a-price span.a-offscreen',
                '#priceblock_ourprice',
                '#priceblock_dealprice',
                'span.a-price[data-a-color="price"] span.a-offscreen',
                '#apex_offerDisplay_desktop span.a-price span.a-offscreen',
                'div[data-feature-name="corePriceDisplay_desktop"] span.a-price span.a-offscreen',
                '#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen',
            ]
            data["current_price"] = await self._try_selectors(price_selectors)
            if data["current_price"]:
                logger.info(f"✓ Current Price: {data['current_price']}")

            # List Price
            list_price_selectors = [
                'span.basisPrice span.a-price.a-text-price span.a-offscreen',
                'span.a-price.a-text-price[data-a-strike="true"] span.a-offscreen',
                '#listPrice',
                'span.priceBlockStrikePriceString',
            ]
            data["list_price"] = await self._try_selectors(list_price_selectors)
            if data["list_price"]:
                logger.info(f"✓ List Price: {data['list_price']}")

            # Savings Percentage
            savings_selectors = [
                'span.savingsPercentage',
                'td.priceBlockSavingsString',
                'span.a-color-price:has-text("%")',
            ]
            data["savings_percent"] = await self._try_selectors(savings_selectors)
            if data["savings_percent"]:
                logger.info(f"✓ Savings: {data['savings_percent']}")

            # Price Per Unit
            ppu_selectors = [
                'span.pricePerUnit',
                'span.a-price span.a-size-small',
            ]
            data["price_per_unit"] = await self._try_selectors(ppu_selectors)
            if data["price_per_unit"] and '/' in data["price_per_unit"]:
                logger.info(f"✓ Price Per Unit: {data['price_per_unit']}")
            else:
                data["price_per_unit"] = None

            # Coupon
            coupon_selectors = [
                'span.couponLabelText',
                '#couponBadgeRegularVpc span',
                'label[id*="coupon"] span',
            ]
            data["coupon"] = await self._try_selectors(coupon_selectors)
            if data["coupon"]:
                logger.info(f"✓ Coupon: {data['coupon']}")

            # ==================== RATINGS (Multiple Fallbacks) ====================
            # Average Rating
            rating_selectors = [
                '#acrPopover span.a-size-base.a-color-base',
                'span[data-hook="rating-out-of-text"]',
                'i.a-icon-star span.a-icon-alt',
                '#averageCustomerReviews span.a-size-base.a-color-base',
                'span.reviewCountTextLinkedHistogram',
            ]

            for selector in rating_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = (await el.inner_text()).strip()
                        # Extract just the number (e.g., "4.5 out of 5" -> "4.5")
                        rating_match = re.search(r'(\d+\.?\d*)', text)
                        if rating_match:
                            data["average_rating"] = rating_match.group(1)
                            logger.info(f"✓ Average Rating: {data['average_rating']}")
                            break
                except:
                    continue

            # Reviews Count
            try:
                reviews_el = self.page.locator("#acrCustomerReviewText")
                if await reviews_el.count() > 0:
                    reviews_text = await reviews_el.inner_text()
                    match = re.search(r'([\d,]+)', reviews_text)
                    if match:
                        data["reviews_count"] = match.group(1)
                        logger.info(f"✓ Reviews: {data['reviews_count']}")
            except:
                pass

            # Monthly Sales
            sales_selectors = [
                'span#social-proofing-faceout-title-tk_bought span.a-text-bold',
                '#social-proofing-faceout-title-tk_bought',
                'span:has-text("bought in past month")',
            ]
            for selector in sales_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = (await el.inner_text()).strip()
                        if 'bought' in text.lower() or 'K+' in text or '+' in text:
                            data["monthly_sales"] = text
                            logger.info(f"✓ Monthly Sales: {data['monthly_sales']}")
                            break
                except:
                    continue

            # ==================== BADGES ====================
            badges = []
            try:
                ac_el = self.page.locator('div.ac-badge-wrapper, span.ac-badge-wrapper, a[title*="Amazon\'s Choice"]').first
                if await ac_el.count() > 0:
                    data["is_amazons_choice"] = True
                    badges.append("Amazon's Choice")
                    logger.info("✓ Badge: Amazon's Choice")
            except:
                pass

            try:
                climate_el = self.page.locator('#climatePledgeFriendlyBadge, a[title*="Climate Pledge"]').first
                if await climate_el.count() > 0:
                    data["is_climate_pledge"] = True
                    badges.append("Climate Pledge Friendly")
                    logger.info("✓ Badge: Climate Pledge Friendly")
            except:
                pass

            try:
                bs_el = self.page.locator('a.badge-link:has-text("Best Seller"), i.p13n-best-seller-badge, a[title*="Best Seller"]').first
                if await bs_el.count() > 0:
                    data["is_best_seller"] = True
                    badges.append("Best Seller")
                    logger.info("✓ Badge: Best Seller")
            except:
                pass

            data["badges"] = badges

            # ==================== AVAILABILITY ====================
            try:
                avail_el = self.page.locator("#availability span, #availability")
                if await avail_el.count() > 0:
                    avail_text = (await avail_el.first.inner_text()).strip()
                    data["availability"] = avail_text
                    logger.info(f"✓ Availability: {avail_text}")
            except:
                pass

            # ==================== CATEGORY (Multiple Methods) ====================
            try:
                # Method 1: Breadcrumbs
                crumbs = self.page.locator("#wayfinding-breadcrumbs_feature_div ul li a, ul.a-horizontal li a")
                categories = []
                for c in await crumbs.all():
                    cat = (await c.inner_text()).strip()
                    if cat and cat not in ["", "‹", "›", "Back"]:
                        categories.append(cat)
                if categories:
                    data["category"] = " > ".join(categories)
                    logger.info(f"✓ Category: {data['category'][:50]}...")
            except:
                pass

            # Method 2: From product details
            if not data["category"]:
                try:
                    cat_row = self.page.locator('th:has-text("Best Sellers Rank"), th:has-text("Category")').first
                    if await cat_row.count() > 0:
                        parent = cat_row.locator('xpath=..')
                        td = parent.locator('td').first
                        if await td.count() > 0:
                            cat_links = await td.locator('a').all()
                            categories = []
                            for link in cat_links[:3]:
                                categories.append((await link.inner_text()).strip())
                            if categories:
                                data["category"] = " > ".join(categories)
                                logger.info(f"✓ Category (from details): {data['category'][:50]}...")
                except:
                    pass

            # ==================== DESCRIPTION (Multiple Methods) ====================
            desc_selectors = [
                "#productDescription p",
                "#productDescription",
                "#productDescription_feature_div p",
                "div.a-expander-content p",
                "#aplus_feature_div p",
            ]

            for selector in desc_selectors:
                try:
                    desc_el = self.page.locator(selector)
                    if await desc_el.count() > 0:
                        desc_parts = []
                        for p in await desc_el.all():
                            text = (await p.inner_text()).strip()
                            if text and len(text) > 20:
                                desc_parts.append(text)
                        if desc_parts:
                            data["description"] = " ".join(desc_parts)[:2000]
                            logger.info(f"✓ Description: {len(data['description'])} chars")
                            break
                except:
                    continue

            # ==================== BULLET POINTS ====================
            try:
                bullets = self.page.locator("#feature-bullets ul li span.a-list-item")
                bullet_list = []
                for b in await bullets.all():
                    text = (await b.inner_text()).strip()
                    if text and len(text) > 5 and not text.startswith("›"):
                        bullet_list.append(text)
                data["bullet_points"] = bullet_list[:10]
                logger.info(f"✓ Bullet points: {len(data['bullet_points'])}")
            except:
                logger.warning("⚠️ Bullet points not found")

            # ==================== SPECIFICATIONS (Comprehensive Extraction) ====================
            specifications = {}
            try:
                # Method 1: Product Overview table
                spec_rows = self.page.locator('#productOverview_feature_div tr, table.a-normal tr[class*="po-"]')
                for row in await spec_rows.all():
                    try:
                        # Try different column structures
                        cells = await row.locator('td, th').all()
                        if len(cells) >= 2:
                            label = (await cells[0].inner_text()).strip()
                            value = (await cells[1].inner_text()).strip()
                            if label and value and len(label) < 50:
                                specifications[label] = value
                    except:
                        continue

                # Method 2: Product Details tables
                detail_tables = self.page.locator('#productDetails_detailBullets_sections1, #productDetails_techSpec_section_1, #prodDetails table')
                for table in await detail_tables.all():
                    rows = await table.locator('tr').all()
                    for row in rows:
                        try:
                            th = row.locator('th').first
                            td = row.locator('td').first
                            if await th.count() > 0 and await td.count() > 0:
                                label = (await th.inner_text()).strip().replace('\n', ' ')
                                value = (await td.inner_text()).strip().replace('\n', ' ')
                                if label and value and len(label) < 50:
                                    # Clean up common suffixes
                                    label = re.sub(r'\s*[:\u200f]$', '', label)
                                    specifications[label] = value
                        except:
                            continue

                # Method 3: Detail bullets
                bullets = self.page.locator('#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li')
                for li in await bullets.all():
                    try:
                        text = await li.inner_text()
                        if ':' in text:
                            parts = text.split(':', 1)
                            if len(parts) == 2:
                                label = parts[0].strip().replace('\n', ' ')
                                value = parts[1].strip().replace('\n', ' ')
                                if label and value and len(label) < 50:
                                    # Skip some common non-useful fields
                                    if label.lower() not in ['customer reviews', 'best sellers rank']:
                                        specifications[label] = value
                    except:
                        continue

                data["specifications"] = specifications
                if specifications:
                    logger.info(f"✓ Specifications: {len(specifications)} fields")

            except Exception as e:
                logger.debug(f"Specifications extraction: {e}")

            # ==================== INGREDIENTS ====================
            # Check specifications first
            if not data["ingredients"]:
                for key, value in specifications.items():
                    if 'ingredient' in key.lower():
                        data["ingredients"] = value
                        logger.info(f"✓ Ingredients (specs): {len(data['ingredients'])} chars")
                        break

            # ==================== SHIPPING INFO ====================
            try:
                ships_from_selectors = [
                    '#tabular-buybox-truncate-0 span.a-truncate-cut',
                    'span.tabular-buybox-text[tabular-attribute-name="Ships from"]',
                    '#merchant-info a',
                ]
                data["ships_from"] = await self._try_selectors(ships_from_selectors)
                if data["ships_from"]:
                    logger.info(f"✓ Ships From: {data['ships_from']}")
            except:
                pass

            try:
                shipping_selectors = [
                    '#amazonGlobal_feature_div span.a-color-secondary',
                    '#deliveryBlockMessage',
                    '#delivery-block-ags-dcp-container span',
                ]
                shipping_text = await self._try_selectors(shipping_selectors)
                if shipping_text and ('shipping' in shipping_text.lower() or '$' in shipping_text or 'PKR' in shipping_text):
                    data["shipping_cost"] = shipping_text
                    logger.info(f"✓ Shipping: {data['shipping_cost'][:50]}...")
            except:
                pass

            try:
                delivery_selectors = [
                    '#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE span.a-text-bold',
                    '#delivery-message span.a-text-bold',
                    'span[data-csa-c-content-id*="delivery"] span.a-text-bold',
                ]
                data["delivery_date"] = await self._try_selectors(delivery_selectors)
                if data["delivery_date"]:
                    logger.info(f"✓ Delivery Date: {data['delivery_date']}")
            except:
                pass

            # ==================== VIDEO COUNT ====================
            try:
                video_el = self.page.locator('span#videoCount, span.vse-video-count, li.videoCountClass').first
                if await video_el.count() > 0:
                    video_text = (await video_el.inner_text()).strip()
                    match = re.search(r'(\d+)', video_text)
                    if match:
                        data["video_count"] = int(match.group(1))
                        logger.info(f"✓ Videos: {data['video_count']}")
            except:
                pass

            # ==================== IMAGES (COMPLETE EXTRACTION) ====================
            try:
                image_set = set()

                # Method 1: From JavaScript data
                scripts = await self.page.locator('script[type="text/javascript"]').all()
                for script in scripts:
                    try:
                        content = await script.inner_text()

                        # Look for colorImages JSON
                        if 'colorImages' in content or 'ImageBlockATF' in content:
                            match = re.search(
                                r'"colorImages"\s*:\s*\{\s*"initial"\s*:\s*\[(.*?)\]',
                                content,
                                re.DOTALL
                            )

                            if match:
                                items_text = match.group(1)
                                urls = re.findall(r'"(https://[^"]*media-amazon[^"]*\.jpg)"', items_text)
                                for url in urls:
                                    if not any(x in url for x in ['1x1', 'pixel', 'AC_SR']):
                                        image_set.add(url)
                    except:
                        continue

                # Method 2: Alternative JavaScript patterns
                if len(image_set) < 5:
                    for script in scripts:
                        try:
                            content = await script.inner_text()
                            urls = re.findall(
                                r'https://[^"\s]*media-amazon\.com/images/I/[^"\s]+\.jpg',
                                content
                            )
                            for url in urls:
                                clean_url = url.split('._')[0] + '.jpg' if '._' in url else url
                                if not any(x in clean_url for x in ['1x1', 'pixel', 'SR38', 'SR96']):
                                    image_set.add(clean_url)
                        except:
                            continue

                # Method 3: Visible img tags
                if len(image_set) < 10:
                    imgs = await self.page.locator('img[src*="media-amazon"]').all()
                    for img in imgs:
                        try:
                            src = await img.get_attribute('src')
                            if src and 'media-amazon.com/images/I/' in src:
                                clean_url = src.split('._')[0] + '.jpg' if '._' in src else src
                                if not any(x in clean_url for x in ['1x1', 'pixel', 'SR38']):
                                    image_set.add(clean_url)
                        except:
                            continue

                # Convert to list and sort
                data["image_urls"] = sorted(list(image_set))
                if data["image_urls"]:
                    data["image_url"] = data["image_urls"][0]

                logger.info(f"✓ Images: {len(data['image_urls'])} URLs extracted")

            except Exception as e:
                logger.warning(f"⚠️ Image extraction error: {e}")

            logger.info("✅ Product scraping complete")

        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")

        finally:
            await self.close_browser()

        return data

    async def close_browser(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("✅ Browser closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

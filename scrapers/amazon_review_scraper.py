"""
Amazon Review Scraper
Extracts customer reviews and performs sentiment analysis
"""

from playwright.sync_api import sync_playwright
import logging
import time
from typing import Dict, List
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#import config

logger = logging.getLogger(__name__)


class AmazonReviewScraper:
    """Scraper for Amazon product reviews"""

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    def setup_browser(self) -> bool:
        """Initialize Playwright browser"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )

            context = self.browser.new_context(
                user_agent=config.USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            self.page = context.new_page()
            self.page.set_default_timeout(config.PLAYWRIGHT_TIMEOUT)

            logger.info("✅ Browser setup successful")
            return True

        except Exception as e:
            logger.error(f"❌ Browser setup failed: {e}")
            return False

   # Correct 4-space indentation
def extract_asin(url):
    import re
    match = re.search(r'/dp/([A-Z0-9]{10})', url)
    if match:
        return match.group(1)
    return None



    def get_reviews_url(self, product_url: str) -> str:
        """Convert product URL to reviews page URL"""
        asin = self.extract_asin_from_url(product_url)
        if asin:
            return f"{config.AMAZON_BASE_URL}/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?sortBy=recent"
        return None

    def scrape_reviews(self, product_url: str, max_reviews: int = None) -> Dict:
        """
        Scrape customer reviews from Amazon product

        Returns:
            Dictionary with reviews data and sentiment analysis
        """
        if not max_reviews:
            max_reviews = config.MAX_REVIEWS_PER_PRODUCT

        if not self.setup_browser():
            return {"reviews": [], "error": "Browser setup failed"}

        reviews_data = {
            "reviews": [],
            "total_scraped": 0,
            "average_sentiment": None,
            "top_complaints": [],
            "top_praises": []
        }

        try:
            reviews_url = self.get_reviews_url(product_url)
            if not reviews_url:
                logger.error("Could not extract ASIN from URL")
                return reviews_data

            logger.info(f"🔍 Visiting reviews page: {reviews_url}")
            self.page.goto(reviews_url, wait_until="domcontentloaded")
            time.sleep(3)

            page_count = 0
            max_pages = (max_reviews // 10) + 1  # Amazon shows ~10 reviews per page

            while page_count < max_pages and len(reviews_data["reviews"]) < max_reviews:
                page_count += 1
                logger.info(f"📄 Scraping reviews page {page_count}")

                # Wait for reviews to load
                try:
                    self.page.wait_for_selector('[data-hook="review"]', timeout=10000)
                except:
                    logger.warning("No reviews found on page")
                    break

                # Get all review elements
                review_elements = self.page.locator('[data-hook="review"]').all()

                for review_elem in review_elements:
                    if len(reviews_data["reviews"]) >= max_reviews:
                        break

                    review = self.extract_review_data(review_elem)
                    if review:
                        reviews_data["reviews"].append(review)

                # Check for next page
                next_btn = self.page.locator('li.a-last a')
                if next_btn.count() == 0 or page_count >= max_pages:
                    break

                # Click next page
                try:
                    next_btn.click()
                    self.page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)
                except:
                    logger.info("No more pages or error navigating")
                    break

            reviews_data["total_scraped"] = len(reviews_data["reviews"])
            
            # Perform sentiment analysis
            if reviews_data["reviews"]:
                reviews_data = self.analyze_sentiment(reviews_data)

            logger.info(f"✅ Scraped {reviews_data['total_scraped']} reviews")

        except Exception as e:
            logger.error(f"❌ Failed to scrape reviews: {e}")
            reviews_data["error"] = str(e)

        finally:
            self.close_browser()

        return reviews_data

    def extract_review_data(self, review_elem) -> Dict:
        """Extract data from a single review element"""
        review = {
            "rating": None,
            "title": None,
            "text": None,
            "date": None,
            "verified": False,
            "helpful_count": 0
        }

        try:
            # Rating
            rating_elem = review_elem.locator('[data-hook="review-star-rating"]').first
            if rating_elem.count() > 0:
                rating_text = rating_elem.inner_text()
                review["rating"] = float(rating_text.split()[0])

            # Title
            title_elem = review_elem.locator('[data-hook="review-title"]').first
            if title_elem.count() > 0:
                review["title"] = title_elem.inner_text().strip()

            # Review text
            text_elem = review_elem.locator('[data-hook="review-body"]').first
            if text_elem.count() > 0:
                review["text"] = text_elem.inner_text().strip()

            # Date
            date_elem = review_elem.locator('[data-hook="review-date"]').first
            if date_elem.count() > 0:
                review["date"] = date_elem.inner_text().strip()

            # Verified purchase
            verified_elem = review_elem.locator('[data-hook="avp-badge"]').first
            review["verified"] = verified_elem.count() > 0

            # Helpful count
            helpful_elem = review_elem.locator('[data-hook="helpful-vote-statement"]').first
            if helpful_elem.count() > 0:
                helpful_text = helpful_elem.inner_text()
                numbers = re.findall(r'\d+', helpful_text)
                if numbers:
                    review["helpful_count"] = int(numbers[0])

        except Exception as e:
            logger.warning(f"Error extracting review data: {e}")

        return review if review["text"] else None

    def analyze_sentiment(self, reviews_data: Dict) -> Dict:
        """
        Perform basic sentiment analysis on reviews
        
        This is a simple implementation. For production, consider using:
        - TextBlob
        - VADER sentiment analyzer
        - Hugging Face transformers
        """
        if not reviews_data["reviews"]:
            return reviews_data

        # Calculate average rating as sentiment proxy
        ratings = [r["rating"] for r in reviews_data["reviews"] if r["rating"]]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            # Convert 1-5 star rating to -1 to 1 sentiment scale
            reviews_data["average_sentiment"] = round((avg_rating - 3) / 2, 2)

        # Extract complaints (1-2 star reviews)
        complaints = []
        for review in reviews_data["reviews"]:
            if review["rating"] and review["rating"] <= 2:
                if review["title"]:
                    complaints.append(review["title"])
                elif review["text"]:
                    # Take first sentence
                    first_sentence = review["text"].split('.')[0][:100]
                    complaints.append(first_sentence)

        reviews_data["top_complaints"] = complaints[:5]

        # Extract praises (5 star reviews)
        praises = []
        for review in reviews_data["reviews"]:
            if review["rating"] and review["rating"] == 5:
                if review["title"]:
                    praises.append(review["title"])
                elif review["text"]:
                    first_sentence = review["text"].split('.')[0][:100]
                    praises.append(first_sentence)

        reviews_data["top_praises"] = praises[:5]

        return reviews_data

    def close_browser(self):
        """Close browser resources"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("✅ Browser closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")


if __name__ == "__main__":
    # Test
    scraper = AmazonReviewScraper()
    test_url = "https://www.amazon.com/dp/B08N5WRWNW"
    reviews = scraper.scrape_reviews(test_url, max_reviews=20)
    print(f"Scraped {len(reviews['reviews'])} reviews")
    print(f"Average sentiment: {reviews['average_sentiment']}")
    print(f"Top complaints: {reviews['top_complaints']}")
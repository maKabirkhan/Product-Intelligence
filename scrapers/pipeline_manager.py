#!/usr/bin/env python3
"""
Pipeline Manager
✅ FIXED: Ensures 'search_query' is passed to DB to prevent NULL errors.
"""

import logging
from typing import List, Dict
import sys
import os
import asyncio

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.amazon_scraper import AmazonScraper
from scrapers.amazon_product_scraper import AmazonProductScraper
from scrapers.ocr_processor import OCRProcessor
from scrapers.ai_analyzer import AIAnalyzer
from scrapers.supabase_manager import SupabaseManager

logger = logging.getLogger(__name__)

class PipelineManager:
    def __init__(self):
        self.db = SupabaseManager()
        self.listing_scraper = AmazonScraper()
        self.product_scraper = AmazonProductScraper()
        self.ocr_processor = OCRProcessor()
        self.ai_analyzer = AIAnalyzer(db_manager=self.db)
        self._last_search_products: List[Dict] = []

    # --------------------------------------------------
    # SEARCH
    # --------------------------------------------------
    async def run_search_only(self, query: str, user_id: str, max_pages: int = 1):
        # Scrape
        products = await self.listing_scraper.scrape_products(query, max_pages)
        self._last_search_products = products
        
        # Store
        self.store_listings(products, query, user_id)

    def store_listings(self, products: List[Dict], search_query: str, user_id: str):
        stored = []
        
        # Fallback if query is somehow None
        if not search_query:
            search_query = "Unknown Query"

        for product in products:
            asin = product.get("asin")
            if not asin:
                continue

            # 🔥 THE FIX IS HERE:
            # We explicitly pass the 'search_query' variable to the dictionary
            product_data = {
                "asin": asin,
                "product_url": product.get("product_url"),
                "search_query": search_query,  # <--- MUST NOT BE NONE
                "title": product.get("title"),
                "price": product.get("price"),
                "rating": product.get("rating"),
                "image_url": product.get("image_url"),
                "image_urls": product.get("image_urls", []),
                "scrape_status": "listing_completed",
                "ocr_processed": False
            }

            ok = self.db.upsert_product(product_data, user_id=user_id)

            if ok:
                stored.append(asin)

        # Update local cache with only successfully stored items
        self._last_search_products = [
            p for p in self._last_search_products if p.get("asin") in stored
        ]

        logger.info(f"✅ Stored {len(stored)} products for user {user_id}")

    # --------------------------------------------------
    # DETAILS
    # --------------------------------------------------
    async def run_details_only(self, query: str, user_id: str, max_products: int = 10):
        if not self._last_search_products:
            await self.run_search_only(query, user_id)

        for product in self._last_search_products[:max_products]:
            asin = product.get("asin")
            if not asin:
                continue

            details = await self.product_scraper.scrape_product(product.get("product_url"))

            if details:
                self.db.update_product(asin, {
                    "title": details.get("title"),
                    "brand": details.get("brand"),
                    "description": details.get("description"),
                    "image_urls": details.get("image_urls", []),
                    "scrape_status": "details_completed"
                }, user_id=user_id)

    # --------------------------------------------------
    # OCR
    # --------------------------------------------------
    def process_ocr(self, asins: List[str], user_id: str, max_images_per_product: int = 10):
        if not asins:
            return

        if not self.ocr_processor.is_available():
            logger.error("❌ Tesseract OCR not installed or not found.")
            return

        for asin in asins:
            try:
                product = self.db.get_product_by_asin(asin)
                if not product:
                    continue

                ocr_result = self.ocr_processor.process_product(product, max_images=max_images_per_product)
                self.db.save_ocr_result(asin, ocr_result, user_id=user_id)
            except Exception as e:
                logger.error(f"❌ OCR failed for {asin}: {e}")

    # --------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------
    def run_ai_analysis_for_asins(self, asins: List[str], user_id: str):
        if not asins:
            return
        try:
            self.ai_analyzer.analyze_asins(asins, user_id=user_id)
        except Exception as e:
            logger.error(f"❌ AI pipeline failed: {e}")

    # --------------------------------------------------
    # FULL AUTO PIPELINE
    # --------------------------------------------------
    async def run_full_pipeline_auto(
        self,
        query: str,
        user_id: str,
        max_pages: int = 1,
        max_products: int = 10,
        max_images_per_product: int = 10
    ):
        logger.info("=" * 80)
        logger.info(f"🚀 AUTO PIPELINE STARTED: {query} (user {user_id})")
        logger.info("=" * 80)

        # 1. Search
        await self.run_search_only(query, user_id, max_pages)

        # 2. Details
        await self.run_details_only(query, user_id, max_products)

        # Collect ASINs
        asins = [p.get("asin") for p in self._last_search_products[:max_products] if p.get("asin")]

        if not asins:
            logger.warning("No ASINs found, stopping pipeline")
            return

        # 3. OCR
        logger.info("🔍 OCR stage")
        self.process_ocr(asins, user_id, max_images_per_product)

        # 4. AI
        logger.info("🧠 AI stage")
        self.run_ai_analysis_for_asins(asins, user_id)

        logger.info(f"✅ AUTO PIPELINE COMPLETED for user {user_id}")
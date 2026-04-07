#!/usr/bin/env python3
"""
Supabase Database Manager
✅ Added get_product_by_asin + improved logging for OCR/AI
✅ Added user_id support for all inserts/updates
"""

import os
from typing import List, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from datetime import datetime, timezone
import json

load_dotenv()
logger = logging.getLogger(__name__)

class SupabaseManager:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        if not self.url or not self.key:
            raise ValueError("Missing Supabase credentials")
        self.client: Client = create_client(self.url, self.key)
        logger.info("✅ Supabase Manager initialized")

    def _normalize_jsonb_list(self, value) -> List:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except:
                return []
        return []

    # ----------------- PRODUCT UPSERT/UPDATE -----------------
    def upsert_product(self, product_data: Dict, user_id: str) -> Optional[str]:  # 🔥 USER_ID
        try:
            product_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            product_data["image_urls"] = self._normalize_jsonb_list(product_data.get("image_urls", []))
            product_data["bullet_points"] = self._normalize_jsonb_list(product_data.get("bullet_points", []))
            product_data["user_id"] = user_id  # 🔥 USER_ID

            response = self.client.table("products").upsert(product_data, on_conflict="asin").execute()
            if response.data:
                asin = response.data[0]["asin"]
                logger.info(f"✅ Upserted product for user {user_id}: {asin}")
                return asin
            return None
        except Exception as e:
            logger.error(f"❌ Upsert failed for user {user_id}: {e}")
            return None

    def update_product(self, asin: str, updates: Dict, user_id: Optional[str] = None) -> bool:  # 🔥 USER_ID optional
        try:
            if not asin:
                logger.error("❌ Cannot update: ASIN missing")
                return False
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            if "image_urls" in updates:
                updates["image_urls"] = self._normalize_jsonb_list(updates["image_urls"])
            if "bullet_points" in updates:
                updates["bullet_points"] = self._normalize_jsonb_list(updates["bullet_points"])
            if user_id:
                updates["user_id"] = user_id  # 🔥 USER_ID

            logger.info(f"📝 Updating product {asin} for user {user_id} with fields: {list(updates.keys())}")
            self.client.table("products").update(updates).eq("asin", asin).execute()
            logger.info(f"✅ Successfully updated product: {asin}")
            return True
        except Exception as e:
            logger.error(f"❌ Update failed for {asin}: {e}")
            return False

    # ----------------- GET PRODUCT BY ASIN -----------------
    def get_product_by_asin(self, asin: str) -> Optional[Dict]:
        try:
            response = self.client.table("products").select("*").eq("asin", asin).single().execute()
            return response.data if response.data else None
        except Exception as e:
            logger.error(f"❌ get_product_by_asin failed for {asin}: {e}")
            return None

    # ----------------- OCR -----------------
    def save_ocr_result(self, asin: str, ocr_result: Dict, user_id: Optional[str] = None) -> bool:  # 🔥 USER_ID
        try:
            updates = {
                "ocr_text": ocr_result.get("ocr_text") or None,
                "ingredients": ocr_result.get("ingredients") or None,
                "ocr_processed": ocr_result.get("ocr_processed", False),
                "ocr_status": ocr_result.get("ocr_status", "FAILED"),
                "ocr_processed_at": datetime.now(timezone.utc).isoformat(),
                "scrape_status": "ocr_completed" if ocr_result.get("ocr_processed") else "ocr_failed",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            if user_id:
                updates["user_id"] = user_id  # 🔥 USER_ID

            logger.info(f"💾 Saving OCR result for {asin} (user {user_id})")
            self.client.table("products").update(updates).eq("asin", asin).execute()
            logger.info(f"✅ OCR saved for {asin}")
            return True
        except Exception as e:
            logger.error(f"❌ save_ocr_result failed for {asin}: {e}")
            return False

    # ----------------- AI ANALYSIS -----------------
    def mark_analysis_completed(self, asin: str, analysis: Dict, user_id: Optional[str] = None) -> bool:  # 🔥 USER_ID
        updates = {
            "ai_analysis": analysis,
            "analysis_flags": analysis.get("flags", []),
            "analysis_summary": analysis.get("summary"),
            "analysis_completed": True,
            "analysis_completed_at": datetime.now(timezone.utc).isoformat(),
            "scrape_status": "analysis_completed"
        }
        if user_id:
            updates["user_id"] = user_id  # 🔥 USER_ID
        return self.update_product(asin, updates, user_id=user_id)

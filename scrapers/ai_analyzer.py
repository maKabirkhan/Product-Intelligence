#!/usr/bin/env python3
"""
AI Analyzer - Enhanced with OpenAI GPT Integration
Analyzes product data to extract insights, detect issues, and generate summaries
"""

import logging
import os
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("⚠️ OpenAI package not installed. Using fallback analysis.")


class AIAnalyzer:
    def __init__(self, db_manager=None):
        """
        Initialize AI Analyzer with optional database manager
        """
        self.db = db_manager
        self.client = None
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")  # Use mini for cost efficiency

        # Initialize OpenAI client if available
        api_key = os.getenv("OPENAI_API_KEY")
        if OPENAI_AVAILABLE and api_key:
            try:
                self.client = OpenAI(api_key=api_key)
                logger.info(f"🧠 AIAnalyzer initialized with OpenAI ({self.model})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI: {e}")
                self.client = None
        else:
            logger.warning("⚠️ OpenAI not configured. Using fallback analysis.")

    def _build_product_context(self, product: Dict) -> str:
        """Build a text context from product data for analysis"""
        parts = []

        # Title
        if product.get("title"):
            parts.append(f"Product Title: {product['title']}")

        # Brand
        if product.get("brand"):
            parts.append(f"Brand: {product['brand']}")

        # Price info
        price_info = []
        if product.get("current_price"):
            price_info.append(f"Current: {product['current_price']}")
        if product.get("list_price"):
            price_info.append(f"List: {product['list_price']}")
        if product.get("savings_percent"):
            price_info.append(f"Savings: {product['savings_percent']}")
        if price_info:
            parts.append(f"Price: {', '.join(price_info)}")

        # Ratings
        rating_info = []
        if product.get("average_rating"):
            rating_info.append(f"{product['average_rating']} stars")
        if product.get("reviews_count"):
            rating_info.append(f"{product['reviews_count']} reviews")
        if product.get("monthly_sales"):
            rating_info.append(f"{product['monthly_sales']}")
        if rating_info:
            parts.append(f"Ratings: {', '.join(rating_info)}")

        # Badges
        badges = product.get("badges", [])
        if badges:
            parts.append(f"Badges: {', '.join(badges)}")

        # Description
        if product.get("description"):
            parts.append(f"Description: {product['description'][:500]}")

        # Bullet points
        bullets = product.get("bullet_points", [])
        if bullets:
            parts.append(f"Features:\n- " + "\n- ".join(bullets[:5]))

        # Specifications
        specs = product.get("specifications", {})
        if specs:
            spec_text = ", ".join([f"{k}: {v}" for k, v in list(specs.items())[:10]])
            parts.append(f"Specifications: {spec_text}")

        # OCR text (extracted from images)
        if product.get("ocr_text"):
            ocr_preview = product["ocr_text"][:500]
            parts.append(f"Image Text (OCR): {ocr_preview}")

        # Ingredients
        if product.get("ingredients"):
            parts.append(f"Ingredients: {product['ingredients'][:300]}")

        return "\n\n".join(parts)

    def analyze_product(self, product: Dict) -> Dict:
        """
        Analyze a product and return insights
        Uses OpenAI if available, otherwise falls back to basic analysis
        """
        asin = product.get("asin", "unknown")

        result = {
            "summary": None,
            "key_features": [],
            "potential_issues": [],
            "quality_indicators": [],
            "flags": [],
            "sentiment": "neutral",
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

        try:
            if self.client:
                # Use OpenAI for analysis
                result = self._analyze_with_openai(product)
            else:
                # Fallback to basic analysis
                result = self._analyze_basic(product)

            logger.info(f"✅ AI analysis done for {asin}: flags={result.get('flags', [])}")

        except Exception as e:
            logger.error(f"❌ AI analysis failed for {asin}: {e}")
            result["summary"] = f"Analysis failed: {str(e)}"
            result["flags"] = ["analysis_error"]

        return result

    def _analyze_with_openai(self, product: Dict) -> Dict:
        """Use OpenAI GPT to analyze the product"""
        context = self._build_product_context(product)

        prompt = f"""Analyze this Amazon product and provide insights in JSON format.

PRODUCT DATA:
{context}

Provide your analysis as a JSON object with these fields:
{{
  "summary": "A 2-3 sentence summary of what this product is and its key value proposition",
  "key_features": ["list", "of", "top", "3-5", "features"],
  "potential_issues": ["any", "concerns", "or", "red", "flags"],
  "quality_indicators": ["positive", "quality", "signals"],
  "sentiment": "positive/neutral/negative based on overall product presentation",
  "flags": ["safety_warning", "allergy_risk", "quality_concern", "great_value", "top_rated"] // only include applicable flags
}}

Focus on:
1. Product quality signals (brand reputation, ratings, review count)
2. Value for money (price vs features)
3. Any safety or health concerns (especially from ingredients or OCR text)
4. Missing information that buyers should know about

Return ONLY the JSON object, no additional text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a product analyst. Analyze products and return structured JSON insights. Be concise and factual."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            # Parse the response
            content = response.choices[0].message.content.strip()

            # Try to extract JSON from the response
            import json
            import re

            # Find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                return result
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.warning(f"OpenAI analysis failed, using fallback: {e}")
            return self._analyze_basic(product)

    def _analyze_basic(self, product: Dict) -> Dict:
        """Fallback basic analysis without AI"""
        title = product.get("title") or ""
        description = product.get("description") or ""
        ocr_text = product.get("ocr_text") or ""
        bullets = product.get("bullet_points") or []
        ingredients = product.get("ingredients") or ""

        # Combine all text for analysis
        all_text = f"{title} {description} {ocr_text} {' '.join(bullets)} {ingredients}".lower()

        flags = []
        potential_issues = []
        quality_indicators = []

        # Safety warnings
        safety_keywords = ["warning", "caution", "danger", "hazard", "keep out of reach", "harmful"]
        if any(kw in all_text for kw in safety_keywords):
            flags.append("safety_warning")
            potential_issues.append("Product contains safety warnings")

        # Allergy risks
        allergy_keywords = ["allergy", "allergen", "allergic", "may contain", "nut", "gluten", "dairy", "soy"]
        if any(kw in all_text for kw in allergy_keywords):
            flags.append("allergy_risk")
            potential_issues.append("Product may contain allergens")

        # Quality indicators from ratings
        reviews_count = product.get("reviews_count", "0")
        if isinstance(reviews_count, str):
            reviews_count = reviews_count.replace(",", "").replace("K", "000")
            try:
                reviews_count = int(float(reviews_count))
            except:
                reviews_count = 0

        if reviews_count > 1000:
            quality_indicators.append(f"Well-reviewed product ({product.get('reviews_count')} reviews)")

        # Badges
        if product.get("is_amazons_choice"):
            flags.append("amazons_choice")
            quality_indicators.append("Amazon's Choice badge")
        if product.get("is_best_seller"):
            flags.append("best_seller")
            quality_indicators.append("Best Seller badge")
        if product.get("is_climate_pledge"):
            flags.append("eco_friendly")
            quality_indicators.append("Climate Pledge Friendly")

        # Monthly sales indicator
        monthly_sales = product.get("monthly_sales", "")
        if monthly_sales:
            quality_indicators.append(f"Popular: {monthly_sales}")

        # Determine sentiment
        sentiment = "neutral"
        if len(quality_indicators) >= 2:
            sentiment = "positive"
        elif len(potential_issues) >= 2:
            sentiment = "negative"

        # Build summary
        summary_parts = []
        if title:
            # Extract product type from title
            summary_parts.append(f"{title[:100]}.")
        if quality_indicators:
            summary_parts.append(f"Quality signals: {', '.join(quality_indicators[:2])}.")
        if potential_issues:
            summary_parts.append(f"Note: {potential_issues[0]}.")

        return {
            "summary": " ".join(summary_parts) if summary_parts else "Product analysis completed.",
            "key_features": bullets[:5] if bullets else [],
            "potential_issues": potential_issues,
            "quality_indicators": quality_indicators,
            "flags": flags,
            "sentiment": sentiment,
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }

    def analyze_asins(self, asins: List[str], user_id: Optional[str] = None):
        """Analyze multiple products by ASIN"""
        logger.info(f"🧠 Starting AI analysis for {len(asins)} ASIN(s)")
        for asin in asins:
            product = self.db.get_product_by_asin(asin)
            if not product:
                logger.warning(f"❌ Product not found for ASIN {asin}")
                continue
            try:
                analysis_result = self.analyze_product(product)
                self.db.mark_analysis_completed(asin, analysis_result, user_id=user_id)
            except Exception as e:
                logger.error(f"❌ AI analysis failed for {asin}: {e}", exc_info=True)
        logger.info("🧠 AI analysis completed for all ASINs")

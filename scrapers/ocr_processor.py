"""
OCR Processor for Product Labels (FIXED)
High-accuracy OCR + ingredient extraction with consistent return structure
"""

import logging
from typing import List, Optional, Dict
import requests
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import pytesseract
import os
import json
import re

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        self.tesseract_cmd = self._find_tesseract()
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            logger.info("✅ OCR Processor initialized")
        else:
            logger.error("❌ Tesseract not found")

    def _find_tesseract(self) -> Optional[str]:
        paths = [
            # Windows
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            # Linux
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
            # macOS Homebrew (Apple Silicon)
            "/opt/homebrew/bin/tesseract",
            # macOS Homebrew (Intel)
            "/usr/local/Cellar/tesseract/*/bin/tesseract",
        ]
        for p in paths:
            if os.path.exists(p):
                return p

        # Try to find tesseract in PATH using 'which' command
        import subprocess
        try:
            result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                if os.path.exists(path):
                    return path
        except:
            pass

        return None

    def is_available(self) -> bool:
        return self.tesseract_cmd is not None

    def download_image(self, url: str) -> Optional[Image.Image]:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return None
            img = Image.open(BytesIO(r.content))
            img.verify()
            return Image.open(BytesIO(r.content))
        except Exception as e:
            logger.debug(f"Image download failed for {url}: {e}")
            return None

    def preprocess_image(self, img: Image.Image) -> Image.Image:
        img = img.convert("L")
        w, h = img.size
        scale = max(2200 / w, 2200 / h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(2.2)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
        return img

    def ocr_image(self, img: Image.Image) -> Dict[str, any]:
        best = {"text": "", "confidence": 0}
        configs = ["--oem 3 --psm 6", "--oem 3 --psm 4", "--oem 3 --psm 11"]
        for cfg in configs:
            try:
                data = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
                words, confidences = [], []
                for i, word in enumerate(data["text"]):
                    try:
                        conf = int(data["conf"][i])
                    except:
                        conf = 0
                    if conf > 40 and word.strip():
                        words.append(word)
                        confidences.append(conf)
                text = " ".join(words)
                avg_conf = sum(confidences) / len(confidences) if confidences else 0
                if len(text) > len(best["text"]) and avg_conf > best["confidence"]:
                    best = {"text": text, "confidence": avg_conf}
            except Exception as e:
                logger.debug(f"OCR config {cfg} failed: {e}")
                continue
        return best

    def extract_ingredients(self, text: str) -> Optional[str]:
        """Extract ingredients section from OCR text"""
        pattern = re.compile(r"(ingredients?|composition)\s*[:\-]\s*(.+)", re.IGNORECASE | re.DOTALL)
        match = pattern.search(text)
        if not match:
            return None
        block = match.group(2)
        block = re.split(r"(directions|warning|caution|storage|keep out)", block, flags=re.I)[0]
        block = re.sub(r"\s{2,}", " ", block)
        return block.strip()[:1200]

    def process_product(self, product: dict, max_images: int = 10) -> dict:
        """
        🔥 FIXED: Run OCR on product images and return CONSISTENT structure
        Returns dict with keys: ocr_text, ingredients, ocr_processed, ocr_status
        """
        # Initialize result with EXACT keys expected by database
        result = {
            "ocr_text": None,
            "ingredients": None,
            "ocr_processed": False,
            "ocr_status": "FAILED"
        }

        # Check if Tesseract is available
        if not self.is_available():
            result["ocr_status"] = "TESSERACT_NOT_FOUND"
            logger.error(f"❌ Tesseract not available for {product.get('asin')}")
            return result

        # Get image URLs
        images = product.get("image_urls", [])
        if isinstance(images, str):
            try:
                images = json.loads(images)
            except:
                images = []

        if not images:
            result["ocr_status"] = "NO_IMAGES"
            logger.warning(f"⚠️ No images found for {product.get('asin')}")
            return result

        # Process images
        all_text_blocks = []
        all_ingredient_blocks = []
        processed_count = 0

        for idx, url in enumerate(images[:max_images]):
            try:
                logger.info(f"📸 Processing image {idx + 1}/{min(len(images), max_images)}")
                
                img = self.download_image(url)
                if not img:
                    logger.debug(f"   Skipped - download failed")
                    continue
                
                img = self.preprocess_image(img)
                ocr = self.ocr_image(img)
                
                if ocr["confidence"] < 50:
                    logger.debug(f"   Skipped - low confidence ({ocr['confidence']:.1f}%)")
                    continue
                    
                if len(ocr["text"]) < 30:
                    logger.debug(f"   Skipped - insufficient text ({len(ocr['text'])} chars)")
                    continue
                
                all_text_blocks.append(ocr["text"])
                processed_count += 1
                logger.info(f"   ✓ Extracted {len(ocr['text'])} chars (confidence: {ocr['confidence']:.1f}%)")
                
                # Try to extract ingredients
                ing = self.extract_ingredients(ocr["text"])
                if ing:
                    all_ingredient_blocks.append(ing)
                    logger.info(f"   ✓ Found ingredients section ({len(ing)} chars)")
                    
            except Exception as e:
                logger.warning(f"   ⚠️ Error processing image {idx + 1}: {e}")
                continue

        # Build final result
        if not all_text_blocks:
            result["ocr_status"] = "NO_TEXT_DETECTED"
            logger.warning(f"⚠️ No text detected for {product.get('asin')}")
            return result

        # Success - combine all text
        result["ocr_text"] = "\n\n".join(all_text_blocks)
        result["ingredients"] = "\n\n".join(all_ingredient_blocks) if all_ingredient_blocks else None
        result["ocr_processed"] = True
        result["ocr_status"] = "SUCCESS"

        logger.info(f"✅ OCR complete for {product.get('asin')}: {processed_count} images, {len(all_text_blocks)} text blocks")
        logger.info(f"   - Total OCR text: {len(result['ocr_text'])} chars")
        logger.info(f"   - Ingredients found: {'Yes' if result['ingredients'] else 'No'}")

        return result
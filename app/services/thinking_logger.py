"""
Thinking Logger Service
Professional logging system for real-time "thinking" updates like Perplexity AI
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class ThinkingPhase(str, Enum):
    """Phases of the scraping/analysis process"""
    INITIALIZING = "initializing"
    URL_COLLECTION = "url_collection"
    ANALYZING_SEARCH = "analyzing_search"
    SCRAPING_PRODUCT = "scraping_product"
    EXTRACTING_DATA = "extracting_data"
    PROCESSING_IMAGES = "processing_images"
    OCR_PROCESSING = "ocr_processing"
    AI_ANALYSIS = "ai_analysis"
    SAVING_DATA = "saving_data"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ThinkingType(str, Enum):
    """Types of thinking messages"""
    THOUGHT = "thought"          # Internal reasoning
    ACTION = "action"            # Taking an action
    OBSERVATION = "observation"  # Result of an action
    PROGRESS = "progress"        # Progress update
    SUCCESS = "success"          # Successful completion
    WARNING = "warning"          # Warning/caution
    ERROR = "error"              # Error occurred
    SUMMARY = "summary"          # Summary of work


@dataclass
class ThinkingMessage:
    """Structured thinking message for frontend display"""
    type: str
    phase: str
    title: str
    content: str
    details: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class ThinkingLogger:
    """
    Professional thinking logger that generates Perplexity-style thinking updates.

    Usage:
        thinking = ThinkingLogger(query_id, user_id, db_manager, broadcast_func)
        await thinking.log_thought("Analyzing search query", "Looking for laptop products...")
        await thinking.log_action("Connecting to Amazon", "Establishing secure connection...")
    """

    def __init__(self, query_id: str, user_id: int, db_manager, broadcast_func=None):
        self.query_id = query_id
        self.user_id = user_id
        self.db = db_manager
        self.broadcast = broadcast_func
        self.current_phase = ThinkingPhase.INITIALIZING
        self.start_time = datetime.now(timezone.utc)
        self.messages: List[ThinkingMessage] = []

    def _elapsed_time(self) -> str:
        """Get elapsed time since start"""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        if elapsed < 60:
            return f"{elapsed:.1f}s"
        elif elapsed < 3600:
            return f"{elapsed/60:.1f}m"
        else:
            return f"{elapsed/3600:.1f}h"

    async def _emit(self, msg: ThinkingMessage):
        """Emit a thinking message to DB and WebSocket"""
        self.messages.append(msg)

        # Save to database
        if self.db:
            self.db.add_log(
                query_id=self.query_id,
                user_id=self.user_id,
                log_type=msg.type,
                message=f"[{msg.title}] {msg.content}",
                progress_current=msg.progress.get("current") if msg.progress else None,
                progress_total=msg.progress.get("total") if msg.progress else None,
                metadata={"phase": msg.phase, "details": msg.details}
            )

        # Broadcast via WebSocket
        if self.broadcast:
            await self.broadcast(self.query_id, {
                "type": "thinking",
                **msg.to_dict()
            })

    def set_phase(self, phase: ThinkingPhase):
        """Set current processing phase"""
        self.current_phase = phase

    # =========================================================================
    # PRIMARY LOGGING METHODS
    # =========================================================================

    async def log_thought(self, title: str, content: str, details: Dict = None):
        """Log an internal thought/reasoning step"""
        msg = ThinkingMessage(
            type=ThinkingType.THOUGHT,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details
        )
        await self._emit(msg)

    async def log_action(self, title: str, content: str, details: Dict = None):
        """Log an action being taken"""
        msg = ThinkingMessage(
            type=ThinkingType.ACTION,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details
        )
        await self._emit(msg)

    async def log_observation(self, title: str, content: str, details: Dict = None):
        """Log an observation/result"""
        msg = ThinkingMessage(
            type=ThinkingType.OBSERVATION,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details
        )
        await self._emit(msg)

    async def log_progress(self, title: str, content: str, current: int, total: int, details: Dict = None):
        """Log progress update"""
        percentage = (current / total * 100) if total > 0 else 0
        msg = ThinkingMessage(
            type=ThinkingType.PROGRESS,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details,
            progress={"current": current, "total": total, "percentage": round(percentage, 1)}
        )
        await self._emit(msg)

    async def log_success(self, title: str, content: str, details: Dict = None):
        """Log successful completion"""
        msg = ThinkingMessage(
            type=ThinkingType.SUCCESS,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details
        )
        await self._emit(msg)

    async def log_warning(self, title: str, content: str, details: Dict = None):
        """Log a warning"""
        msg = ThinkingMessage(
            type=ThinkingType.WARNING,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details
        )
        await self._emit(msg)

    async def log_error(self, title: str, content: str, details: Dict = None):
        """Log an error"""
        msg = ThinkingMessage(
            type=ThinkingType.ERROR,
            phase=self.current_phase,
            title=title,
            content=content,
            details=details
        )
        await self._emit(msg)

    async def log_summary(self, title: str, content: str, stats: Dict = None):
        """Log a summary"""
        msg = ThinkingMessage(
            type=ThinkingType.SUMMARY,
            phase=self.current_phase,
            title=title,
            content=content,
            details={"stats": stats, "elapsed_time": self._elapsed_time()}
        )
        await self._emit(msg)

    # =========================================================================
    # HIGH-LEVEL LOGGING HELPERS (Perplexity-style)
    # =========================================================================

    async def start_url_collection(self, query: str, config: Dict):
        """Log start of URL collection phase"""
        self.set_phase(ThinkingPhase.URL_COLLECTION)
        await self.log_thought(
            "Understanding Query",
            f"Analyzing search query: \"{query}\""
        )
        await self.log_action(
            "Planning Search Strategy",
            f"Will search up to {config.get('max_pages', 5)} pages of results"
        )
        await self.log_action(
            "Connecting to Amazon",
            "Establishing secure browser connection with anti-detection measures"
        )

    async def url_collection_progress(self, page: int, total_pages: int, urls_found: int):
        """Log URL collection progress"""
        await self.log_progress(
            "Scanning Search Results",
            f"Found {urls_found} products so far",
            current=page,
            total=total_pages,
            details={"urls_found": urls_found}
        )

    async def url_collection_complete(self, total_urls: int):
        """Log URL collection completion"""
        await self.log_success(
            "URL Collection Complete",
            f"Successfully collected {total_urls} product URLs"
        )
        await self.log_observation(
            "Ready for Scraping",
            "Product URLs are ready. Waiting for user to start scraping."
        )

    async def start_scraping(self, total_products: int, config: Dict):
        """Log start of scraping phase"""
        self.set_phase(ThinkingPhase.SCRAPING_PRODUCT)
        await self.log_thought(
            "Planning Scraping Strategy",
            f"Will process {total_products} products with detailed extraction"
        )

        steps = ["Product details extraction"]
        if not config.get("skip_ocr"):
            steps.append("OCR text extraction from images")
        if not config.get("skip_ai_analysis"):
            steps.append("AI-powered analysis")

        await self.log_action(
            "Processing Pipeline",
            f"Each product will go through: {' → '.join(steps)}"
        )

    async def start_product_scrape(self, index: int, total: int, asin: str, title: str):
        """Log start of individual product scraping"""
        self.set_phase(ThinkingPhase.EXTRACTING_DATA)
        await self.log_progress(
            "Processing Product",
            f"Extracting data for: {title[:60]}{'...' if len(title) > 60 else ''}",
            current=index,
            total=total,
            details={"asin": asin, "title": title}
        )

    async def product_details_extracted(self, asin: str, fields_found: List[str]):
        """Log successful product details extraction"""
        await self.log_observation(
            "Data Extracted",
            f"Found {len(fields_found)} data fields: {', '.join(fields_found[:5])}{'...' if len(fields_found) > 5 else ''}",
            details={"asin": asin, "fields": fields_found}
        )

    async def start_ocr(self, asin: str, image_count: int):
        """Log start of OCR processing"""
        self.set_phase(ThinkingPhase.OCR_PROCESSING)
        await self.log_action(
            "Analyzing Product Images",
            f"Running OCR on {image_count} product images to extract text",
            details={"asin": asin, "image_count": image_count}
        )

    async def ocr_complete(self, asin: str, text_length: int, ingredients_found: bool):
        """Log OCR completion"""
        result_desc = f"Extracted {text_length} characters of text"
        if ingredients_found:
            result_desc += " (ingredients detected)"

        await self.log_observation(
            "Image Text Extracted",
            result_desc,
            details={"asin": asin, "text_length": text_length, "ingredients_found": ingredients_found}
        )

    async def start_ai_analysis(self, asin: str):
        """Log start of AI analysis"""
        self.set_phase(ThinkingPhase.AI_ANALYSIS)
        await self.log_action(
            "Running AI Analysis",
            "Analyzing product data for insights, safety flags, and summary",
            details={"asin": asin}
        )

    async def ai_analysis_complete(self, asin: str, flags: List[str]):
        """Log AI analysis completion"""
        if flags:
            await self.log_observation(
                "Analysis Complete",
                f"Identified {len(flags)} flags: {', '.join(flags)}",
                details={"asin": asin, "flags": flags}
            )
        else:
            await self.log_observation(
                "Analysis Complete",
                "No safety or quality concerns identified",
                details={"asin": asin, "flags": []}
            )

    async def product_complete(self, index: int, total: int, asin: str):
        """Log product completion"""
        await self.log_success(
            "Product Processed",
            f"Successfully completed product {index}/{total}",
            details={"asin": asin, "remaining": total - index}
        )

    async def product_failed(self, asin: str, error: str):
        """Log product failure"""
        await self.log_warning(
            "Product Skipped",
            f"Could not process product: {error}",
            details={"asin": asin, "error": error}
        )

    async def scraping_complete(self, total_processed: int, total_failed: int):
        """Log scraping completion"""
        self.set_phase(ThinkingPhase.COMPLETED)
        await self.log_summary(
            "Scraping Complete",
            f"Successfully processed {total_processed} products",
            stats={
                "total_processed": total_processed,
                "total_failed": total_failed,
                "success_rate": f"{(total_processed/(total_processed+total_failed)*100):.1f}%" if (total_processed+total_failed) > 0 else "N/A"
            }
        )

    async def scraping_paused(self, current_index: int, total: int):
        """Log scraping paused"""
        self.set_phase(ThinkingPhase.PAUSED)
        await self.log_warning(
            "Scraping Paused",
            f"Paused at product {current_index}/{total}. Resume to continue.",
            details={"current_index": current_index, "total": total, "remaining": total - current_index}
        )

    async def scraping_cancelled(self, completed: int, total: int):
        """Log scraping cancelled"""
        self.set_phase(ThinkingPhase.CANCELLED)
        await self.log_warning(
            "Scraping Cancelled",
            f"Cancelled by user. {completed} products were saved.",
            details={"completed": completed, "total": total}
        )

    async def error_occurred(self, error: str, context: str = None):
        """Log error"""
        self.set_phase(ThinkingPhase.ERROR)
        await self.log_error(
            "Error Occurred",
            error,
            details={"context": context} if context else None
        )

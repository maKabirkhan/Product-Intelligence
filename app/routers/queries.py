"""
Scraping Queries Router
Handles query creation, URL collection, and scraping control
"""

import sys
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from app.db.session_manager import SessionManager
from app.schemas.sessions import (
    ScrapingQueryCreate,
    ScrapingQueryResponse,
    ScrapingQueryListResponse,
    ScrapingQueryUrlsResponse,
    StartScrapingRequest,
    ScrapingControlResponse,
    MessageResponse,
    UrlCollectionConfig
)
from app.auth.utils import get_current_user
from app.routers.websocket import (
    broadcast_log,
    broadcast_status_change,
    broadcast_progress,
    broadcast_complete,
    broadcast_error,
    broadcast_thinking
)
from app.services.thinking_logger import ThinkingLogger

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize database manager
db = SessionManager()

# Store for active scraping tasks (query_id -> task control)
active_scraping_tasks = {}


# ============================================================================
# SCRAPING QUERIES ENDPOINTS
# ============================================================================

@router.post("/{session_id}/queries", response_model=ScrapingQueryResponse, status_code=201)
async def create_query(
    session_id: str,
    query_data: ScrapingQueryCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new scraping query and start URL collection.

    This endpoint:
    1. Creates a new query in the session
    2. If there's a previous query in 'urls_collected' status, marks it as 'voided'
    3. Starts URL collection in the background
    4. Returns immediately with the query details

    Use WebSocket /ws/scraping/{query_id} to receive real-time logs.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Verify session exists and is active
    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    # Check for previous query in urls_collected status and void it
    existing_queries = db.list_queries(session_id=session_id, user_id=user_id, limit=10)
    for existing in existing_queries:
        if existing.get("status") == "urls_collected":
            db.void_query(existing["id"], user_id)
            logger.info(f"Voided previous query {existing['id']} (user started new query)")

    # Prepare URL collection config
    # No defaults - if user doesn't specify, scrape all available pages
    config = query_data.url_collection_config
    if config:
        config_dict = config.model_dump()
    else:
        config_dict = {}

    # Create the query
    query = db.create_query(
        session_id=session_id,
        user_id=user_id,
        query_text=query_data.query_text,
        url_collection_config=config_dict
    )

    if not query:
        raise HTTPException(status_code=500, detail="Failed to create query")

    # Start URL collection in background
    background_tasks.add_task(
        collect_urls_task,
        query_id=query["id"],
        user_id=user_id,
        query_text=query_data.query_text,
        config=config_dict
    )

    logger.info(f"Created query {query['id']} and started URL collection")

    return query


@router.get("/{session_id}/queries", response_model=ScrapingQueryListResponse)
async def list_queries(
    session_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List all queries in a session.

    Queries are ordered by creation date (newest first).
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    # Verify session access
    session = db.get_session(session_id=session_id, user_id=user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    queries = db.list_queries(
        session_id=session_id,
        user_id=user_id,
        limit=limit,
        offset=offset
    )

    return {
        "queries": queries,
        "total": len(queries)
    }


@router.get("/{session_id}/queries/{query_id}", response_model=ScrapingQueryResponse)
async def get_query(
    session_id: str,
    query_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific query.

    Returns full query data including:
    - Collected URLs
    - Scraped products data
    - Current status and progress
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Verify query belongs to session
    if str(query.get("session_id")) != session_id:
        raise HTTPException(status_code=404, detail="Query not found in this session")

    return query


@router.get("/{session_id}/queries/{query_id}/urls", response_model=ScrapingQueryUrlsResponse)
async def get_query_urls(
    session_id: str,
    query_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get only the collected URLs for a query.

    Use this endpoint to display URLs to user before they decide to start scraping.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    return {
        "query_id": query["id"],
        "query_text": query["query_text"],
        "status": query["status"],
        "collected_urls": query.get("collected_urls", []),
        "total_urls_collected": query.get("total_urls_collected", 0),
        "url_collection_config": query.get("url_collection_config")
    }


# ============================================================================
# SCRAPING CONTROL ENDPOINTS
# ============================================================================

@router.post("/{session_id}/queries/{query_id}/scrape", response_model=ScrapingControlResponse)
async def start_scraping(
    session_id: str,
    query_id: str,
    scrape_config: Optional[StartScrapingRequest] = None,
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Start scraping the collected URLs.

    Prerequisites:
    - Query must be in 'urls_collected' or 'paused' status
    - URLs must have been collected

    The scraping process:
    1. Scrapes product details from each URL
    2. Runs OCR on product images
    3. Runs AI analysis on product data
    4. Stores all data in products_data JSON

    Use WebSocket /ws/scraping/{query_id} to receive real-time progress.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Check status
    status = query.get("status")
    if status not in ["urls_collected", "paused"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start scraping: query status is '{status}'. Must be 'urls_collected' or 'paused'."
        )

    urls = query.get("collected_urls", [])
    if not urls:
        raise HTTPException(status_code=400, detail="No URLs to scrape")

    # Parse config
    config = {}
    if scrape_config:
        config = {
            "max_products": scrape_config.max_products,
            "skip_ocr": scrape_config.skip_ocr,
            "skip_ai_analysis": scrape_config.skip_ai_analysis
        }

    # Start scraping in background
    background_tasks.add_task(
        scrape_products_task,
        query_id=query_id,
        user_id=user_id,
        urls=urls,
        config=config,
        resume_from=query.get("scraping_progress", {}).get("current_index", 0) if status == "paused" else 0
    )

    # Update status
    db.update_query_status(query_id, user_id, "scraping")

    logger.info(f"Started scraping for query {query_id}")

    return {
        "query_id": query_id,
        "status": "scraping",
        "message": "Scraping started",
        "progress": None
    }


@router.post("/{session_id}/queries/{query_id}/pause", response_model=ScrapingControlResponse)
async def pause_scraping(
    session_id: str,
    query_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Pause an ongoing scraping process.

    The scraping can be resumed later from where it stopped.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    if query.get("status") != "scraping":
        raise HTTPException(status_code=400, detail="Query is not currently scraping")

    # Set pause flag for the task
    if query_id in active_scraping_tasks:
        active_scraping_tasks[query_id]["paused"] = True

    # Update status
    db.update_query_status(query_id, user_id, "paused")

    logger.info(f"Paused scraping for query {query_id}")

    return {
        "query_id": query_id,
        "status": "paused",
        "message": "Scraping paused",
        "progress": query.get("scraping_progress")
    }


@router.post("/{session_id}/queries/{query_id}/resume", response_model=ScrapingControlResponse)
async def resume_scraping(
    session_id: str,
    query_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Resume a paused scraping process.

    Continues from where it was paused.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    if query.get("status") != "paused":
        raise HTTPException(status_code=400, detail="Query is not paused")

    urls = query.get("collected_urls", [])
    progress = query.get("scraping_progress", {})
    resume_index = progress.get("current_index", 0)

    # Start scraping in background from where we left off
    background_tasks.add_task(
        scrape_products_task,
        query_id=query_id,
        user_id=user_id,
        urls=urls,
        config={},
        resume_from=resume_index
    )

    # Update status
    db.update_query_status(query_id, user_id, "scraping")

    logger.info(f"Resumed scraping for query {query_id} from index {resume_index}")

    return {
        "query_id": query_id,
        "status": "scraping",
        "message": f"Scraping resumed from product {resume_index + 1}",
        "progress": progress
    }


@router.post("/{session_id}/queries/{query_id}/cancel", response_model=ScrapingControlResponse)
async def cancel_scraping(
    session_id: str,
    query_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel an ongoing or paused scraping process.

    This marks the query as cancelled. Already scraped products are retained.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    current_status = query.get("status")
    if current_status not in ["scraping", "paused", "collecting_urls", "urls_collected"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel query with status '{current_status}'")

    # Set cancel flag for the task
    if query_id in active_scraping_tasks:
        active_scraping_tasks[query_id]["cancelled"] = True

    # Update status
    db.update_query_status(query_id, user_id, "cancelled")

    logger.info(f"Cancelled scraping for query {query_id}")

    return {
        "query_id": query_id,
        "status": "cancelled",
        "message": "Scraping cancelled",
        "progress": query.get("scraping_progress")
    }


@router.delete("/{session_id}/queries/{query_id}", response_model=MessageResponse)
async def delete_query(
    session_id: str,
    query_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete/void a query.

    If scraping is in progress, it will be cancelled first.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Cancel if in progress
    if query.get("status") in ["scraping", "collecting_urls"]:
        if query_id in active_scraping_tasks:
            active_scraping_tasks[query_id]["cancelled"] = True

    # Mark as voided
    db.void_query(query_id, user_id)

    logger.info(f"Voided query {query_id}")

    return {
        "message": "Query deleted successfully",
        "success": True
    }


@router.get("/{session_id}/queries/{query_id}/logs")
async def get_query_logs(
    session_id: str,
    query_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """
    Get logs for a query (for clients not using WebSocket).
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    query = db.get_query(query_id=query_id, user_id=user_id)
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    logs = db.get_logs(query_id=query_id, user_id=user_id, limit=limit)

    return {
        "query_id": query_id,
        "logs": logs,
        "total": len(logs)
    }


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def collect_urls_task(query_id: str, user_id: int, query_text: str, config: dict):
    """Background task to collect URLs from Amazon search with professional thinking logs"""
    from scrapers.amazon_scraper import AmazonScraper

    # Initialize thinking logger
    thinking = ThinkingLogger(query_id, user_id, db, broadcast_thinking)

    try:
        # Update status
        db.update_query_status(query_id, user_id, "collecting_urls")
        await broadcast_status_change(query_id, "pending", "collecting_urls")

        # Professional thinking logs - START
        await thinking.start_url_collection(query_text, config)

        # Initialize scraper
        scraper = AmazonScraper()
        max_pages = config.get("max_pages")  # None = scrape all pages
        limit = config.get("limit")

        await thinking.log_action(
            "Launching Browser",
            "Starting headless Chromium with anti-detection measures enabled"
        )

        await thinking.log_action(
            "Navigating to Amazon",
            f"Searching for: \"{query_text}\""
        )

        # Scrape products
        products = await scraper.scrape_products(query_text, max_pages=max_pages)

        await thinking.log_observation(
            "Search Results Retrieved",
            f"Amazon returned {len(products)} products from search results"
        )

        # Format as collected URLs (with deduplication by ASIN)
        collected_urls = []
        seen_asins = set()
        for p in products:
            asin = p.get("asin")
            if asin and asin != "N/A" and asin not in seen_asins:
                seen_asins.add(asin)
                collected_urls.append({
                    "asin": asin,
                    "url": p.get("product_url", f"https://www.amazon.com/dp/{asin}"),
                    "title": p.get("title"),
                    "image_url": p.get("image_url")
                })

        # Log if duplicates were removed
        duplicates_removed = len(products) - len(collected_urls) - sum(1 for p in products if not p.get("asin") or p.get("asin") == "N/A")
        if duplicates_removed > 0:
            await thinking.log_observation(
                "Duplicates Removed",
                f"Filtered out {duplicates_removed} duplicate product(s) based on ASIN"
            )

        # Apply limit if specified
        if limit and len(collected_urls) > limit:
            await thinking.log_thought(
                "Applying Limit",
                f"Limiting results to {limit} products as configured"
            )
            collected_urls = collected_urls[:limit]

        # Save URLs
        db.save_collected_urls(query_id, user_id, collected_urls)
        await broadcast_status_change(query_id, "collecting_urls", "urls_collected")

        # Professional completion log
        await thinking.url_collection_complete(len(collected_urls))

        logger.info(f"URL collection complete for query {query_id}: {len(collected_urls)} URLs")

    except Exception as e:
        logger.error(f"URL collection failed for query {query_id}: {e}", exc_info=True)
        db.update_query_status(query_id, user_id, "error", error_message=str(e))
        await thinking.error_occurred(str(e), "URL collection phase")


async def scrape_products_task(query_id: str, user_id: int, urls: list,
                                config: dict, resume_from: int = 0):
    """Background task to scrape product details, run OCR and AI analysis with professional thinking logs"""
    from scrapers.amazon_product_scraper import AmazonProductScraper
    from scrapers.ocr_processor import OCRProcessor
    from scrapers.ai_analyzer import AIAnalyzer
    from scrapers.supabase_manager import SupabaseManager

    # Initialize control flags and thinking logger
    active_scraping_tasks[query_id] = {"paused": False, "cancelled": False}
    thinking = ThinkingLogger(query_id, user_id, db, broadcast_thinking)
    products_failed = 0

    try:
        # Get existing products if resuming
        query = db.get_query(query_id, user_id)
        existing_products = query.get("products_data", []) or []

        # Initialize components
        product_scraper = AmazonProductScraper()
        ocr_processor = OCRProcessor()
        old_db = SupabaseManager()
        ai_analyzer = AIAnalyzer(db_manager=old_db)

        skip_ocr = config.get("skip_ocr", False)
        skip_ai = config.get("skip_ai_analysis", False)
        max_products = config.get("max_products") or len(urls)

        # Limit URLs
        urls_to_process = urls[resume_from:max_products]
        total = len(urls_to_process)

        # Professional thinking logs - START SCRAPING
        await thinking.start_scraping(total, config)

        if resume_from > 0:
            await thinking.log_thought(
                "Resuming Previous Session",
                f"Continuing from product {resume_from + 1}, {len(existing_products)} products already scraped"
            )

        products_scraped = []
        for idx, url_data in enumerate(urls_to_process):
            # Check control flags
            if active_scraping_tasks.get(query_id, {}).get("cancelled"):
                await thinking.scraping_cancelled(len(products_scraped), total)
                break

            if active_scraping_tasks.get(query_id, {}).get("paused"):
                await thinking.scraping_paused(resume_from + idx, len(urls))
                break

            asin = url_data.get("asin")
            url = url_data.get("url")
            title = url_data.get("title", asin)
            current_idx = resume_from + idx

            try:
                # Update progress
                progress = {
                    "current_index": current_idx,
                    "total": len(urls),
                    "current_asin": asin,
                    "current_stage": "details",
                    "products_completed": len(products_scraped),
                    "products_failed": products_failed
                }
                db.update_scraping_progress(query_id, user_id, progress)
                await broadcast_progress(query_id, progress)

                # PHASE 1: Scrape product details
                await thinking.start_product_scrape(current_idx + 1, len(urls), asin, title)

                await thinking.log_action(
                    "Fetching Product Page",
                    f"Loading Amazon product page for ASIN: {asin}"
                )

                product_data = await product_scraper.scrape_product(url)

                if not product_data:
                    products_failed += 1
                    await thinking.product_failed(asin, "Failed to load product page or extract data")
                    continue

                # Add base info
                product_data["asin"] = asin
                product_data["product_url"] = url
                product_data["scraped_at"] = db._now()

                # Log extracted fields
                fields_found = [k for k, v in product_data.items() if v and k not in ['asin', 'product_url', 'scraped_at']]
                await thinking.product_details_extracted(asin, fields_found)

                # PHASE 2: OCR Processing
                if not skip_ocr and ocr_processor.is_available():
                    progress["current_stage"] = "ocr"
                    db.update_scraping_progress(query_id, user_id, progress)
                    await broadcast_progress(query_id, progress)

                    image_urls = product_data.get("image_urls", [])
                    if image_urls:
                        await thinking.start_ocr(asin, len(image_urls[:5]))

                        ocr_result = ocr_processor.process_product(product_data, max_images=5)
                        product_data["ocr_text"] = ocr_result.get("ocr_text")
                        product_data["ocr_status"] = ocr_result.get("ocr_status")
                        product_data["ingredients"] = ocr_result.get("ingredients") or product_data.get("ingredients")

                        text_len = len(ocr_result.get("ocr_text") or "")
                        ingredients_found = bool(ocr_result.get("ingredients"))
                        await thinking.ocr_complete(asin, text_len, ingredients_found)
                    else:
                        await thinking.log_observation(
                            "No Images for OCR",
                            "Product has no images available for text extraction",
                            details={"asin": asin}
                        )

                # PHASE 3: AI Analysis
                if not skip_ai:
                    progress["current_stage"] = "ai_analysis"
                    db.update_scraping_progress(query_id, user_id, progress)
                    await broadcast_progress(query_id, progress)

                    await thinking.start_ai_analysis(asin)

                    analysis = ai_analyzer.analyze_product(product_data)
                    product_data["ai_analysis"] = analysis

                    flags = analysis.get("flags", []) if analysis else []
                    await thinking.ai_analysis_complete(asin, flags)

                # Add to list
                products_scraped.append(product_data)
                await thinking.product_complete(current_idx + 1, len(urls), asin)

                # Save progress periodically (every 3 products)
                if len(products_scraped) % 3 == 0:
                    all_products = existing_products + products_scraped
                    db.update_query(query_id, user_id, {
                        "products_data": all_products,
                        "total_products_scraped": len(all_products)
                    })
                    await thinking.log_thought(
                        "Saving Progress",
                        f"Checkpoint saved: {len(all_products)} products stored"
                    )

            except Exception as e:
                products_failed += 1
                logger.error(f"Error scraping {asin}: {e}")
                await thinking.product_failed(asin, str(e))
                continue

        # Final save
        all_products = existing_products + products_scraped
        final_status = "completed"

        if active_scraping_tasks.get(query_id, {}).get("cancelled"):
            final_status = "cancelled"
        elif active_scraping_tasks.get(query_id, {}).get("paused"):
            final_status = "paused"

        db.update_query(query_id, user_id, {
            "products_data": all_products,
            "total_products_scraped": len(all_products),
            "status": final_status
        })

        if final_status == "completed":
            await thinking.scraping_complete(len(products_scraped), products_failed)
            await broadcast_complete(query_id, len(all_products))

        await broadcast_status_change(query_id, "scraping", final_status)
        logger.info(f"Scraping {final_status} for query {query_id}: {len(all_products)} products")

    except Exception as e:
        logger.error(f"Scraping task failed for query {query_id}: {e}", exc_info=True)
        db.update_query_status(query_id, user_id, "error", error_message=str(e))
        await thinking.error_occurred(str(e), "Product scraping phase")

    finally:
        # Cleanup
        if query_id in active_scraping_tasks:
            del active_scraping_tasks[query_id]

import sys
import asyncio
import logging
import os
from typing import Optional

# ============================================================================
# 🛑 WINDOWS LOOP FIX
# ============================================================================
if sys.platform == "win32":
    try:
        loop = asyncio.get_running_loop()
        if not isinstance(loop, asyncio.ProactorEventLoop):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except RuntimeError:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

# 1️⃣ IMPORT PIPELINE MANAGER
from scrapers.pipeline_manager import PipelineManager
from scrapers.supabase_manager import SupabaseManager
from app.auth.utils import SECRET_KEY

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()

supabase_manager = SupabaseManager()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {
            "id": payload.get("user_id"),
            "email": payload.get("email")
        }
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@router.post("/run")
async def run_scraper(
    query: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    logger.info(f"📥 Scraper request received: query='{query}', user={user_id}")
    
    # Windows Subprocess Logic
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()
            if not isinstance(loop, asyncio.ProactorEventLoop):
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        new_loop.run_until_complete(_run_pipeline(query, user_id))
                    finally:
                        new_loop.close()
                
                import concurrent.futures
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                background_tasks.add_task(lambda: executor.submit(run_in_new_loop))
                
                return JSONResponse(
                    status_code=202,
                    content={"message": "Accepted (Windows Mode)", "query": query, "user_id": user_id}
                )
        except Exception:
            pass
    
    background_tasks.add_task(_run_pipeline, query, user_id)
    
    return JSONResponse(
        status_code=202,
        content={"message": "Accepted", "query": query, "user_id": user_id}
    )

async def _run_pipeline(query: str, user_id: int):
    """
    Executes the FULL pipeline: Search -> Details -> OCR -> AI
    """
    try:
        # 2️⃣ USE PIPELINE MANAGER instead of manual scraping
        pipeline = PipelineManager()
        
        logger.info(f"🚀 STARTING FULL PIPELINE for: {query}")
        
        # This function handles EVERYTHING (Search, Details, OCR, AI)
        await pipeline.run_full_pipeline_auto(
            query=query,
            user_id=str(user_id),
            max_pages=1,
            max_products=5,   # Adjust limit to save time/resources
            max_images_per_product=5
        )
        
        logger.info(f"✅ Full Pipeline Completed for: {query}")
        
    except Exception as e:
        logger.error(f"❌ Pipeline Error: {e}", exc_info=True)

@router.get("/products")
async def get_products(current_user: dict = Depends(get_current_user), limit: Optional[int] = 50):
    user_id = current_user.get("id")
    try:
        response = supabase_manager.client.table("products").select("*").eq("user_id", user_id).limit(limit).execute()
        return {"products": response.data or [], "count": len(response.data or [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results")
async def get_results(query: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    try:
        response = supabase_manager.client.table("products")\
            .select("*")\
            .eq("user_id", user_id)\
            .ilike("search_query", f"%{query}%")\
            .order("updated_at", desc=True)\
            .execute()
            
        data = response.data if response.data else []
        
        # Calculate status
        total = len(data)
        analyzed = len([p for p in data if p.get("scrape_status") == "analysis_completed"])
        
        # Determine overall status
        status = "processing"
        if total > 0 and analyzed == total:
            status = "done"
        elif total == 0:
            status = "processing" # or not_found
            
        return {
            "query": query,
            "total_found": total,
            "completed_analysis": analyzed,
            "status": status,
            "results": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch results")

@router.delete("/products/{product_id}")
async def delete_product(product_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    try:
        supabase_manager.client.table("products").delete().eq("asin", product_id).eq("user_id", user_id).execute()
        return {"message": "Product deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
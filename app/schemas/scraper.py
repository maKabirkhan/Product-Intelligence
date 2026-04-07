from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class ScrapeRequest(BaseModel):
    """Request schema for Amazon product scraping."""
    
    query: str = Field(
        ..., 
        description="Search query for Amazon products",
        min_length=1,
        max_length=200
    )
    max_pages: int = Field(
        default=5,
        description="Maximum number of pages to scrape",
        ge=1,
        le=20
    )
    delay: float = Field(
        default=2.0,
        description="Delay between page requests in seconds",
        ge=1.0,
        le=10.0
    )
    
    @field_validator('query')
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Query cannot be empty or only whitespace')
        return v.strip()


class ScrapeResponse(BaseModel):
    """Response schema for Amazon product scraping."""
    
    query: str = Field(..., description="Search query used")
    total_products: int = Field(..., description="Total number of unique products found")
    pages_scraped: int = Field(..., description="Number of pages successfully scraped")
    product_links: List[str] = Field(..., description="List of product URLs")
    status: str = Field(..., description="Status of the scraping operation")
    error_message: Optional[str] = Field(None, description="Error message if status is error")


class ScrapeStatusResponse(BaseModel):
    """Response schema for scraper status check."""
    
    status: str = Field(..., description="Current status of the scraper")
    message: str = Field(..., description="Status message")

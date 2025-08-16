"""
Content schemas for news articles and other content types.
Defines the data models for articles, content collections, and related structures.
"""

from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from datetime import datetime


class ContentItem(BaseModel):
    """Individual content item (news article, etc.)"""
    
    id: str = Field(..., description="Unique identifier for the content item")
    headline: str = Field(..., description="Article headline or title")
    author: str = Field(..., description="Author of the content")
    content: str = Field(..., description="Full article content")
    created_at: datetime = Field(..., description="When the content was created")
    updated_at: datetime = Field(..., description="When the content was last updated")
    summary: str = Field(..., description="Brief summary of the content")
    url: HttpUrl = Field(..., description="URL to the full article")
    symbols: List[str] = Field(default_factory=list, description="Related stock symbols")
    source: str = Field(..., description="Source of the content (e.g., benzinga)")
    type: str = Field(..., description="Type of content (e.g., news, analysis)")


class ContentCollection(BaseModel):
    """Collection of content items"""
    
    items: List[ContentItem] = Field(default_factory=list, description="List of content items")
    total_count: Optional[int] = Field(None, description="Total number of items available")
    next_page_token: Optional[str] = Field(None, description="Token for pagination")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the collection was retrieved")


class ArticleQueryParams(BaseModel):
    """Query parameters for article requests"""
    
    symbols: Optional[str] = Field(None, description="Comma-separated list of stock symbols")
    start: Optional[str] = Field(None, description="Start date in ISO format")
    end: Optional[str] = Field(None, description="End date in ISO format")
    sort: str = Field("desc", description="Sort order (asc/desc)")
    limit: int = Field(50, ge=1, le=1000, description="Number of results to return")
    include_content: bool = Field(False, description="Include full article content")
    exclude_contentless: bool = Field(True, description="Exclude articles without content")


class ArticleResponse(BaseModel):
    """Response model for article endpoints"""
    
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[ContentCollection] = Field(None, description="Article data if successful")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")

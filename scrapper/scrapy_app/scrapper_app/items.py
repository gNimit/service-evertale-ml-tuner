"""
Scrapper items definition
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class ChapterItem(BaseModel):
    id: str
    target_key: str
    url: HttpUrl
    source_domain: str
    series: Optional[str] = None
    series_tags: Optional[list[str]] = []
    series_language: Optional[str] = None
    series_status: Optional[str] = None
    author: str
    chapter_num: Optional[int] = None
    title: Optional[str] = None
    content_hash: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    chapter_text: Optional[str] = None
    chapter_notes: Optional[list[str]] = []
    chapter_reader_comments: Optional[list[str]] = []
    fetched_at: int = Field(..., description="UTC epoch seconds")
    meta: Dict[str, Any] = Field(default_factory=dict)

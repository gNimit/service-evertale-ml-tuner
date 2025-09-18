"""
Scrapper items
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class ChapterItem(BaseModel):
    id: str
    url: HttpUrl
    source_domain: str
    series: Optional[str] = None
    chapter_num: Optional[int] = None
    title: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    lang: Optional[str] = None
    fetched_at: int = Field(..., description="UTC epoch seconds")
    status: int
    meta: Dict[str, Any] = Field(default_factory=dict)

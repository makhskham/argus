from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RawSignal(BaseModel):
    source: str
    source_type: str
    external_id: str
    subreddit: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    body: str
    url: Optional[str] = None
    upvotes: int = 0
    upvote_ratio: float = 0.0
    posted_at: datetime


class RedditUserMeta(BaseModel):
    username: str
    total_karma: int = 0
    avg_upvote_ratio: float = 0.0

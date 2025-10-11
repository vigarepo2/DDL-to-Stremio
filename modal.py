from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class QualityDetail(BaseModel):
    quality: str
    url: str  # DDL URL
    name: str
    size: str

class Episode(BaseModel):
    episode_number: int
    title: str
    episode_backdrop: Optional[str] = None
    telegram: List[QualityDetail]  # Renaming this would require more refactoring, so we'll keep it

class Season(BaseModel):
    season_number: int
    episodes: List[Episode]

class MediaBase(BaseModel):
    tmdb_id: int
    title: str
    genres: List[str]
    description: Optional[str] = None
    rating: float
    release_year: int
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    logo: Optional[str] = None
    media_type: str
    updated_on: datetime = Field(default_factory=datetime.utcnow)

class MovieSchema(MediaBase):
    telegram: List[QualityDetail]

class TVShowSchema(MediaBase):
    seasons: List[Season]

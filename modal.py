from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# Defines the structure for each available stream/quality
class StreamInfo(BaseModel):
    quality: str
    url: str
    name: str
    size: str

# Defines the structure for a single episode
class Episode(BaseModel):
    episode_number: int
    title: str
    episode_backdrop: Optional[str] = None
    streams: List[StreamInfo]  # Refactored from 'telegram'

# Defines the structure for a season, which contains episodes
class Season(BaseModel):
    season_number: int
    episodes: List[Episode]

# A base model with common fields for both movies and TV shows
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

# The final schema for a movie document
class MovieSchema(MediaBase):
    streams: List[StreamInfo]  # Refactored from 'telegram'

# The final schema for a TV show document
class TVShowSchema(MediaBase):
    seasons: List[Season]

import motor.motor_asyncio
from datetime import datetime
from typing import List, Optional

from config import settings
from modal import MovieSchema, TVShowSchema

class Database:
    def __init__(self, uri: str, db_name: str = "ddl_stremio"):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[db_name]
        self.movie = self.db.movie
        self.tv = self.db.tv

    async def insert_media(self, metadata: dict, size: str, name: str):
        if metadata['media_type'] == "movie":
            existing = await self.movie.find_one({"tmdb_id": metadata['tmdb_id']})
            quality_detail = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            if existing:
                # Update existing movie: replace quality or add new one
                qualities = existing.get("telegram", [])
                quality_exists = False
                for q in qualities:
                    if q['quality'] == metadata['quality']:
                        q.update(quality_detail)
                        quality_exists = True
                        break
                if not quality_exists:
                    qualities.append(quality_detail)
                
                await self.movie.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"telegram": qualities, "updated_on": datetime.utcnow()}}
                )
            else:
                # Insert new movie
                movie_data = MovieSchema(
                    **metadata,
                    telegram=[quality_detail]
                )
                await self.movie.insert_one(movie_data.dict())
        else: # TV Show
            existing = await self.tv.find_one({"tmdb_id": metadata['tmdb_id']})
            quality_detail = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            
            if existing:
                # Update existing TV show
                season_found = False
                for s in existing.get("seasons", []):
                    if s['season_number'] == metadata['season_number']:
                        season_found = True
                        episode_found = False
                        for e in s.get("episodes", []):
                            if e['episode_number'] == metadata['episode_number']:
                                episode_found = True
                                quality_exists = False
                                for q in e.get("telegram", []):
                                    if q['quality'] == metadata['quality']:
                                        q.update(quality_detail)
                                        quality_exists = True
                                        break
                                if not quality_exists:
                                    e['telegram'].append(quality_detail)
                                break
                        if not episode_found:
                             s['episodes'].append(metadata['seasons'][0]['episodes'][0])
                        break
                if not season_found:
                    existing['seasons'].append(metadata['seasons'][0])

                await self.tv.update_one({"_id": existing["_id"]}, {"$set": {"seasons": existing['seasons'], "updated_on": datetime.utcnow()}})
            else:
                # Insert new TV show
                tv_data = TVShowSchema(**metadata)
                tv_data.seasons[0].episodes[0].telegram = [quality_detail]
                await self.tv.insert_one(tv_data.dict())

    async def get_all_media(self, media_type: str, skip: int, limit: int, search: Optional[str] = None):
        collection = self.movie if media_type == 'movie' else self.tv
        query = {}
        if search:
            query = {"title": {"$regex": search, "$options": "i"}}
        
        cursor = collection.find(query).sort("updated_on", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_media_by_tmdb_id(self, media_type: str, tmdb_id: int):
        collection = self.movie if media_type == 'movie' else self.tv
        return await collection.find_one({"tmdb_id": tmdb_id})

# Initialize the database
db = Database(settings.MONGO_URI)

import motor.motor_asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import settings
from modal import MovieSchema, TVShowSchema

class Database:
    def __init__(self, uri: str, db_name: str):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[db_name]
        self.movie_collection = self.db.movies
        self.tv_collection = self.db.tv_shows

    async def get_stats(self):
        movie_count = await self.movie_collection.count_documents({})
        tv_count = await self.tv_collection.count_documents({})
        return {"movies": movie_count, "tv_shows": tv_count}

    async def insert_media(self, metadata: dict, size: str, name: str):
        # Movie handling
        if metadata['media_type'] == "movie":
            existing = await self.movie_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            
            if existing:
                streams = existing.get("streams", [])
                if not any(q['quality'] == metadata['quality'] for q in streams):
                    streams.append(stream_info)
                await self.movie_collection.update_one({"_id": existing["_id"]}, {"$set": {"streams": streams, "updated_on": datetime.utcnow()}})
            else:
                await self.movie_collection.insert_one(MovieSchema(**metadata, streams=[stream_info]).dict())
        
        # TV Show handling
        else:
            existing = await self.tv_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            
            if existing:
                season_found = False
                for s in existing.get("seasons", []):
                    if s['season_number'] == metadata['season_number']:
                        season_found = True
                        episode_found = False
                        for e in s.get("episodes", []):
                            if e['episode_number'] == metadata['episode_number']:
                                episode_found = True
                                if not any(q['quality'] == metadata['quality'] for q in e.get("streams", [])):
                                    e['streams'].append(stream_info)
                                break
                        if not episode_found:
                            new_ep = metadata['seasons'][0]['episodes'][0]
                            new_ep['streams'] = [stream_info]
                            s['episodes'].append(new_ep)
                        break
                if not season_found:
                    new_season = metadata['seasons'][0]
                    new_season['episodes'][0]['streams'] = [stream_info]
                    existing['seasons'].append(new_season)
                
                await self.tv_collection.update_one({"_id": existing["_id"]}, {"$set": {"seasons": existing['seasons'], "updated_on": datetime.utcnow()}})
            else:
                tv_data = TVShowSchema(**metadata)
                tv_data.seasons[0].episodes[0].streams = [stream_info]
                await self.tv_collection.insert_one(tv_data.dict())

    async def get_media_list(self, media_type: str, page: int, page_size: int, search: Optional[str] = None):
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        query = {}
        if search:
            query = {"title": {"$regex": search, "$options": "i"}}
        
        total_count = await collection.count_documents(query)
        cursor = collection.find(query).sort("updated_on", -1).skip((page - 1) * page_size).limit(page_size)
        items = await cursor.to_list(length=page_size)
        return items, total_count

    async def get_media_by_tmdb_id(self, media_type: str, tmdb_id: int):
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        return await collection.find_one({"tmdb_id": tmdb_id})

    async def update_media_details(self, media_type: str, tmdb_id: int, data: Dict[str, Any]):
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        result = await collection.update_one({"tmdb_id": tmdb_id}, {"$set": data})
        return result.modified_count > 0

    async def delete_media(self, media_type: str, tmdb_id: int) -> bool:
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        result = await collection.delete_one({"tmdb_id": tmdb_id})
        return result.deleted_count > 0

db = Database(settings.MONGO_URI, settings.DB_NAME)

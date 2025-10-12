import motor.motor_asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId

from config import settings
from modal import MovieSchema, TVShowSchema, StreamInfo

# Helper function to sanitize MongoDB's special data types for JSON conversion
def sanitize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return None
    for key, value in list(doc.items()):
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

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
        if metadata['media_type'] == "movie":
            existing = await self.movie_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            
            if existing:
                streams = existing.get("streams", [])
                # Prevent adding if the exact same URL already exists
                if not any(s['url'] == stream_info['url'] for s in streams):
                    streams.append(stream_info)
                    await self.movie_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"streams": streams, "updated_on": datetime.utcnow()}}
                    )
            else:
                await self.movie_collection.insert_one(MovieSchema(**metadata, streams=[stream_info]).dict())
        
        else: # TV Show logic
            existing = await self.tv_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = StreamInfo(quality=metadata['quality'], url=metadata['url'], name=name, size=size)
            
            new_season_data = metadata['seasons'][0]
            new_episode_data = new_season_data['episodes'][0]

            if existing:
                season_found = False
                for s in existing.get("seasons", []):
                    if s['season_number'] == new_season_data['season_number']:
                        season_found = True
                        episode_found = False
                        for e in s.get("episodes", []):
                            if e['episode_number'] == new_episode_data['episode_number']:
                                episode_found = True
                                # IMPROVED: Prevent adding if the exact same URL already exists
                                if not any(q['url'] == stream_info.url for q in e.get("streams", [])):
                                    e['streams'].append(stream_info.dict())
                                break
                        if not episode_found:
                            new_episode_data['streams'] = [stream_info.dict()]
                            s['episodes'].append(new_episode_data)
                        break
                if not season_found:
                    new_season_data['episodes'][0]['streams'] = [stream_info.dict()]
                    existing.setdefault('seasons', []).append(new_season_data)
                
                await self.tv_collection.update_one(
                    {"_id": existing["_id"]}, 
                    {"$set": {"seasons": existing['seasons'], "updated_on": datetime.utcnow()}}
                )
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

        sanitized_items = [sanitize_document(item) for item in items]
        return sanitized_items, total_count

    async def get_media_by_tmdb_id(self, media_type: str, tmdb_id: int):
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        doc = await collection.find_one({"tmdb_id": tmdb_id})
        return sanitize_document(doc)

    async def update_media_details(self, media_type: str, tmdb_id: int, data: Dict[str, Any]):
        data.pop("_id", None)
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        result = await collection.update_one({"tmdb_id": tmdb_id}, {"$set": data})
        return result.modified_count > 0

    async def delete_media(self, media_type: str, tmdb_id: int) -> bool:
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        result = await collection.delete_one({"tmdb_id": tmdb_id})
        return result.deleted_count > 0

db = Database(settings.MONGO_URI, settings.DB_NAME)

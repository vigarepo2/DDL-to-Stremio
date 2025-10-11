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
    for key, value in doc.items():
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
            # This logic for movies is correct and remains the same.
            existing = await self.movie_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            
            if existing:
                streams = existing.get("streams", [])
                quality_exists = False
                for q in streams:
                    if q['quality'] == metadata['quality']:
                        q.update(stream_info)
                        quality_exists = True
                        break
                if not quality_exists:
                    streams.append(stream_info)
                
                await self.movie_collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"streams": streams, "updated_on": datetime.utcnow()}}
                )
            else:
                await self.movie_collection.insert_one(MovieSchema(**metadata, streams=[stream_info]).dict())
        
        # --- START OF CORRECTED TV SHOW LOGIC ---
        else:  # TV Show
            existing = await self.tv_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = StreamInfo(quality=metadata['quality'], url=metadata['url'], name=name, size=size)
            
            # Correctly extract the new season/episode data from the metadata
            new_season_data = metadata['seasons'][0]
            new_episode_data = new_season_data['episodes'][0]

            if existing:
                season_found = False
                # Find the correct season in the existing document
                for s in existing.get("seasons", []):
                    if s['season_number'] == new_season_data['season_number']:
                        season_found = True
                        episode_found = False
                        # Find the correct episode in the existing season
                        for e in s.get("episodes", []):
                            if e['episode_number'] == new_episode_data['episode_number']:
                                episode_found = True
                                # Check if the quality already exists, if not, add it
                                if not any(q['quality'] == stream_info.quality for q in e.get("streams", [])):
                                    e['streams'].append(stream_info.dict())
                                break
                        # If episode not found, add the new episode to the season
                        if not episode_found:
                            new_episode_data['streams'] = [stream_info.dict()]
                            s['episodes'].append(new_episode_data)
                        break
                # If season not found, add the new season to the show
                if not season_found:
                    new_season_data['episodes'][0]['streams'] = [stream_info.dict()]
                    existing.setdefault('seasons', []).append(new_season_data)

                # Update the entire document in the database
                await self.tv_collection.update_one(
                    {"_id": existing["_id"]}, 
                    {"$set": {"seasons": existing['seasons'], "updated_on": datetime.utcnow()}}
                )
            else:
                # This logic for inserting a brand new show is correct
                tv_data = TVShowSchema(**metadata)
                tv_data.seasons[0].episodes[0].streams = [stream_info]
                await self.tv_collection.insert_one(tv_data.dict())
        # --- END OF CORRECTED TV SHOW LOGIC ---

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
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        result = await collection.update_one({"tmdb_id": tmdb_id}, {"$set": data})
        return result.modified_count > 0

    async def delete_media(self, media_type: str, tmdb_id: int) -> bool:
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        result = await collection.delete_one({"tmdb_id": tmdb_id})
        return result.deleted_count > 0

db = Database(settings.MONGO_URI, settings.DB_NAME)

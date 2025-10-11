import motor.motor_asyncio
from datetime import datetime
from typing import Optional

from config import settings
from modal import MovieSchema, TVShowSchema

class Database:
    def __init__(self, uri: str, db_name: str = "ddl_stremio_db"):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[db_name]
        self.movie_collection = self.db.movies
        self.tv_collection = self.db.tv_shows

    async def insert_media(self, metadata: dict, size: str, name: str):
        if metadata['media_type'] == "movie":
            existing = await self.movie_collection.find_one({"tmdb_id": metadata['tmdb_id']})
            stream_info = {"quality": metadata['quality'], "url": metadata['url'], "name": name, "size": size}
            
            if existing:
                streams = existing.get("streams", [])
                quality_exists = False
                for q in streams:
                    if q['quality'] == metadata['quality']:
                        q.update(stream_info) # Update existing quality
                        quality_exists = True
                        break
                if not quality_exists:
                    streams.append(stream_info) # Add new quality
                
                await self.movie_collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"streams": streams, "updated_on": datetime.utcnow()}}
                )
            else:
                movie_data = MovieSchema(**metadata, streams=[stream_info])
                await self.movie_collection.insert_one(movie_data.dict())
        
        else:  # TV Show
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
                                quality_exists = False
                                for q in e.get("streams", []):
                                    if q['quality'] == metadata['quality']:
                                        q.update(stream_info)
                                        quality_exists = True
                                        break
                                if not quality_exists:
                                    e['streams'].append(stream_info)
                                break
                        if not episode_found:
                            # Add the new episode to the existing season
                            new_episode = metadata['seasons'][0]['episodes'][0]
                            new_episode['streams'] = [stream_info]
                            s['episodes'].append(new_episode)
                        break
                if not season_found:
                    # Add the new season to the existing show
                    new_season = metadata['seasons'][0]
                    new_season['episodes'][0]['streams'] = [stream_info]
                    existing['seasons'].append(new_season)

                await self.tv_collection.update_one(
                    {"_id": existing["_id"]}, 
                    {"$set": {"seasons": existing['seasons'], "updated_on": datetime.utcnow()}}
                )
            else:
                tv_data = TVShowSchema(**metadata)
                tv_data.seasons[0].episodes[0].streams = [stream_info]
                await self.tv_collection.insert_one(tv_data.dict())

    async def get_all_media(self, media_type: str, skip: int, limit: int, search: Optional[str] = None):
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        query = {}
        if search:
            query = {"title": {"$regex": search, "$options": "i"}}
        cursor = collection.find(query).sort("updated_on", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_media_by_tmdb_id(self, media_type: str, tmdb_id: int):
        collection = self.movie_collection if media_type == 'movie' else self.tv_collection
        return await collection.find_one({"tmdb_id": tmdb_id})

# Initialize the database for use in the app
db = Database(settings.MONGO_URI)

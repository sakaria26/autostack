import asyncio
from datetime import datetime
from enum import Enum
import json
from typing import Optional, Protocol
import strawberry
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
import os
from dotenv import load_dotenv
import logging


load_dotenv()
logger = logging.getLogger(__name__)

@strawberry.enum
class ProjectCreationStatus(Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    CREATING_PROJECT = "CREATING_PROJECT"
    CREATING_TECHNOLOGIES = "CREATING_TECHNOLOGIES"
    CREATING_COMPONENTS = "CREATING_COMPONENTS"
    CREATING_CONNECTIONS = "CREATING_CONNECTIONS"
    FINALIZING = "FINALIZING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    
class ProjectDeletionStatus(Enum):
    QUEUED = "QUEUED"
    DELETING_PROJECT = "DELETING_PROJECT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    
@strawberry.type
class ProjectCreationUpdate:
    operation_id: str
    status: ProjectCreationStatus
    message: str
    progress: int  # 0-100
    project_id: Optional[str] = None
    error: Optional[str] = None
    
@strawberry.type
class InitiateProjectResponse:
    success: bool
    operation_id: str
    message: str
    error: Optional[str] = None
    
                

class RedisOperationStore:
    """Redis-backed operation store for production use"""
    
    def __init__(
        self,
        redis_url: str = f'redis://{os.getenv('REDIS_USER')}:{os.getenv('REDIS_PASSWORD')}@{os.getenv('REDIS_HOST')}:6379/0',
        max_connections: int = 200,
        operation_ttl: int = 7200  # 1 hour
    ):
        self.redis_url = redis_url
        self.operation_ttl = operation_ttl
        
        # Create connection pool
        self.pool = ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            decode_responses=False
        )
        
        self.redis: Optional[redis.Redis] = None
        self._pubsub_clients = {}
    
    async def initialize(self):
        """Initialize Redis connection"""
        self.redis = redis.Redis(connection_pool=self.pool)
        await self.redis.ping()
        logger.info("Redis connection established")
    
    async def close(self):
        """Close Redis connections"""
        # Close all pubsub connections
        for pubsub in self._pubsub_clients.values():
            await pubsub.close()
        self._pubsub_clients.clear()
        
        # Close main connection
        if self.redis:
            await self.redis.close()
        
        await self.pool.disconnect()
        logger.info("Redis connections closed")
    
    async def create_operation(self, operation_id: str):
        """Create a new operation"""
        operation_data = {
            "status": ProjectCreationStatus.QUEUED.value,
            "progress": "0",
            "message": "Operation queued",
            "project_id": "",
            "error": "",
            "created_at": datetime.now().isoformat()
        }
        
        key = f"operation:{operation_id}"
        
        await self.redis.hset(key, mapping=operation_data)
        await self.redis.expire(key, self.operation_ttl)
        
        logger.info(f"Operation created: {operation_id}")
    
    async def update_operation(
        self,
        operation_id: str,
        status: ProjectCreationStatus,
        message: str,
        progress: int,
        project_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Update operation and notify subscribers"""
        key = f"operation:{operation_id}"
        
        # Update data
        update_data = {
            "status": status.value,
            "progress": str(progress),
            "message": message,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if project_id is not None:
            update_data["project_id"] = project_id
        
        if error is not None:
            update_data["error"] = error
        
        # Update hash
        await self.redis.hset(key, mapping=update_data)
        
        # Publish update to subscribers
        update_message = {
            "operation_id": operation_id,
            "status": status.value,
            "message": message,
            "progress": progress,
            "project_id": project_id,
            "error": error
        }
        
        channel = f"operation:{operation_id}:updates"
        await self.redis.publish(channel, json.dumps(update_message))
        
        logger.info(f"Operation updated: {operation_id} - {status.value} ({progress}%)")
    
    async def subscribe(self, operation_id: str) -> asyncio.Queue:
        """Subscribe to operation updates"""
        queue = asyncio.Queue(maxsize=100)
        
        # Get current state first
        key = f"operation:{operation_id}"
        current = await self.redis.hgetall(key)
        
        if current:
            await queue.put(ProjectCreationUpdate(
                operation_id=operation_id,
                status=ProjectCreationStatus(current[b'status'].decode()),
                message=current[b'message'].decode(),
                progress=int(current[b'progress']),
                project_id=current[b'project_id'].decode() or None,
                error=current[b'error'].decode() or None
            ))
        
        # Create pubsub connection
        pubsub = self.redis.pubsub()
        channel = f"operation:{operation_id}:updates"
        await pubsub.subscribe(channel)
        
        # Store for cleanup
        self._pubsub_clients[operation_id] = pubsub
        
        # Background task to forward messages
        async def listen_and_forward():
            try:
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = json.loads(message['data'])
                            update = ProjectCreationUpdate(
                                operation_id=data['operation_id'],
                                status=ProjectCreationStatus(data['status']),
                                message=data['message'],
                                progress=data['progress'],
                                project_id=data.get('project_id'),
                                error=data.get('error')
                            )
                            
                            await queue.put(update)
                            
                            # Stop after completion/failure
                            if update.status in [
                                ProjectCreationStatus.COMPLETED,
                                ProjectCreationStatus.FAILED
                            ]:
                                break
                                
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"Invalid message format: {e}")
            
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in listener: {e}")
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                if operation_id in self._pubsub_clients:
                    del self._pubsub_clients[operation_id]
        
        # Start listener
        task = asyncio.create_task(listen_and_forward())
        queue._listener_task = task  # type: ignore
        
        return queue
    
    async def cleanup(self, operation_id: str, queue: asyncio.Queue):
        """Clean up subscription"""
        # Cancel listener task
        if hasattr(queue, '_listener_task'):
            task = queue._listener_task  # type: ignore
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Close pubsub if exists
        if operation_id in self._pubsub_clients:
            pubsub = self._pubsub_clients[operation_id]
            await pubsub.close()
            del self._pubsub_clients[operation_id]



import traceback
import strawberry
from strawberry.types import Info
from typing import AsyncGenerator

from autostack_engine.utils.project.subscription import ProjectCreationStatus, ProjectCreationUpdate
from autostack_engine.gateway.graphql.resolvers.ai.ai_query import JobResult
import logging
logger = logging.getLogger(__name__)

def get_operation_store(info: Info):
    """Get operation store from GraphQL context"""
    return info.context["operation_store"]


@strawberry.type
class ProjectSubscription:
    """Project-related subscriptions"""
    @strawberry.subscription
    async def project_creation_status(
        self,
        operation_id: str,
        info: Info
    ) -> AsyncGenerator[ProjectCreationUpdate, None]:
        
        operation_store = get_operation_store(info)
        
        # Subscribe to updates from Redis
        try:
            queue = await operation_store.subscribe(operation_id)
        except Exception as e:
            logger.error(f"Failed to subscribe to operation {operation_id}: {e}")
            # Yield an error status instead of failing
            yield ProjectCreationUpdate(
                operation_id=operation_id,
                status=ProjectCreationStatus.FAILED,
                message="Failed to subscribe to operation",
                progress=0,
                error=str(e)
            )
            return
        
        try:
            # Keep yielding updates until completion or failure
            async for update in ProjectSubscription._stream_updates(queue, operation_id):
                yield update
                
                # Stop after completion or failure
                if update.status in [
                    ProjectCreationStatus.COMPLETED,
                    ProjectCreationStatus.FAILED
                ]:
                    logger.info(f"Operation {operation_id} finished with status: {update.status}")
                    break
                    
        except GeneratorExit:
            # This happens when the client disconnects before we finish
            logger.info(f"Subscription for {operation_id} closed by client")
        except Exception as e:
            # Check if this is a disconnection error to avoid noisy logs
            error_str = str(e).lower()
            if "disconnect" in error_str or "closed" in error_str:
                logger.info(f"Subscription connection for {operation_id} was lost: {e}")
            else:
                logger.error(f"Error in subscription stream for {operation_id}: {traceback.format_exc()}")
                # Try to yield error update if possible
                try:
                    yield ProjectCreationUpdate(
                        operation_id=operation_id,
                        status=ProjectCreationStatus.FAILED,
                        message="Subscription error occurred",
                        progress=0,
                        error=str(e)
                    )
                except:
                    pass
        finally:
            # Clean up subscription resources
            logger.info(f"Cleaning up subscription for operation: {operation_id}")
            try:
                await operation_store.cleanup(operation_id, queue)
            except Exception as e:
                logger.warning(f"Error during subscription cleanup for {operation_id}: {e}")
    
    @strawberry.subscription
    async def subscribe_to_job(
        self,
        job_id: str,
        info: Info
    ) -> AsyncGenerator[JobResult, None]:
        import json
        from datetime import datetime
        
        operation_store = get_operation_store(info)
        
        try:
            queue = await operation_store.subscribe(job_id)
        except Exception as e:
            logger.error(f"Failed to subscribe to job {job_id}: {e}")
            yield JobResult(
                id=job_id,
                status="FAILED",
                error=str(e),
                createdAt=datetime.now().isoformat()
            )
            return

        try:
            # We need to adapt the ProjectCreationUpdate from the operation store to JobResult
            async for update in ProjectSubscription._stream_updates(queue, job_id):
                # Retrieve the full data from Redis to get the 'result' field if it exists
                key = f"operation:{job_id}"
                raw_data = await operation_store.redis.hgetall(key)
                
                result_data = None
                if b'result' in raw_data:
                    try:
                        result_data = json.loads(raw_data[b'result'].decode())
                    except:
                        pass

                yield JobResult(
                    id=job_id,
                    status=update.status.value if hasattr(update.status, 'value') else str(update.status),
                    result=result_data,
                    error=update.error,
                    created_at=raw_data[b'created_at'].decode() if b'created_at' in raw_data else datetime.now().isoformat(),
                    completed_at=raw_data[b'updated_at'].decode() if b'updated_at' in raw_data else None
                )
                
                if update.status in [
                    ProjectCreationStatus.COMPLETED,
                    ProjectCreationStatus.FAILED
                ]:
                    break
        except GeneratorExit:
            logger.info(f"Job subscription for {job_id} closed by client")
        except Exception as e:
            error_str = str(e).lower()
            if "disconnect" not in error_str and "closed" not in error_str:
                logger.error(f"Error in job subscription {job_id}: {e}")
        finally:
            try:
                await operation_store.cleanup(job_id, queue)
            except Exception as e:
                logger.warning(f"Error during job subscription cleanup for {job_id}: {e}")

    @staticmethod
    async def _stream_updates(queue, operation_id: str):
        """Helper to stream updates from queue with timeout protection"""
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        
        while True:
            try:
                # Wait for update with timeout to prevent hanging
                update = await asyncio.wait_for(queue.get(), timeout=1000.0)  # 5 min timeout
                
                if update is not None:
                    yield update
                else:
                    logger.warning(f"Received None update for operation {operation_id}")
                    continue
                    
            except asyncio.TimeoutError:
                logger.warning(f"Subscription timeout for operation {operation_id}")
                # Yield a timeout status
                yield ProjectCreationUpdate(
                    operation_id=operation_id,
                    status=ProjectCreationStatus.FAILED,
                    message="Operation timed out",
                    progress=0,
                    error="No updates received for 5 minutes"
                )
                break
            except Exception as e:
                logger.error(f"Error getting update from queue: {e}")
                break
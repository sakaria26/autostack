import asyncio
import uuid
from typing import Optional
import strawberry
import structlog

from autostack_engine.gateway.graphql.resolvers.ai.ai_query import DeleteChatResponse, JobCreated
from autostack_engine.services.ai.services.ai import AIService
from autostack_engine.services.project.services.project import ProjectService


logger = structlog.get_logger()


@strawberry.type
class CreateSchemaRatingResponse:
    """Response type for schema rating"""
    success: bool
    message: Optional[str]
    error: Optional[str]
    
    
@strawberry.type
class ModelMutation:
    
    @strawberry.mutation
    async def create_project_description(self, info: strawberry.Info, user_input: str) -> JobCreated:
        """
        Initiate project architecture generation asynchronously.
        """
        operation_store = info.context["operation_store"]
        
        try:
            job_id = str(uuid.uuid4())
            await operation_store.create_operation(job_id)
            
            # Start background task
            asyncio.create_task(
                ModelMutation._execute_ai_generation(
                    job_id,
                    user_input,
                    operation_store
                )
            )
            
            return JobCreated(
                job_id=job_id,
                message="AI project description generation started."
            )
            
        except Exception as e:
            logger.error(f"Error initiating AI generation: {e}")
            raise e

    @staticmethod
    async def _execute_ai_generation(job_id: str, user_input: str, operation_store):
        """Background task for AI generation"""
        from autostack_engine.services.ai.services.ai import AIService
        from autostack_engine.utils.project.subscription import ProjectCreationStatus
        import json
        from datetime import datetime
        
        try:
            await operation_store.update_operation(
                job_id,
                ProjectCreationStatus.PROCESSING if hasattr(ProjectCreationStatus, 'PROCESSING') else ProjectCreationStatus.VALIDATING,
                "AI is generating your project architecture...",
                30
            )
            
            ai_service = AIService()
            success, result, chat_id, error = await ai_service.generate_project_config(user_input)
            
            if success:
                # Store the result in Redis so get_job can find it
                # We extend the operation_store mapping for 'result'
                key = f"operation:{job_id}"
                await operation_store.redis.hset(key, "result", json.dumps(result))
                
                await operation_store.update_operation(
                    job_id,
                    ProjectCreationStatus.COMPLETED,
                    "Project architecture generated successfully!",
                    100
                )
            else:
                await operation_store.update_operation(
                    job_id,
                    ProjectCreationStatus.FAILED,
                    error or "AI generation failed.",
                    100,
                    error=error
                )
                
        except Exception as e:
            logger.error(f"background_ai_generation_failed job_id={job_id} error={e}")
            await operation_store.update_operation(
                job_id,
                ProjectCreationStatus.FAILED,
                "An internal error occurred during generation.",
                100,
                error=str(e)
            )

    @strawberry.mutation
    async def delete_chat(self, chat_id: str) -> DeleteChatResponse:
        """
        Delete a chat by ID.
        
        Args:
            chat_id: The chat ID to delete
            
        Returns:
            DeleteChatResponse indicating success or failure
        """
        try:
            ai_service = AIService()
            success, error = await ai_service.delete_chat(chat_id)
            
            if success:
                logger.info(f"Deleted chat: {chat_id}")
            else:
                logger.error(f"Failed to delete chat: {error}")
            
            return DeleteChatResponse(success=success, error=error)
            
        except Exception as e:
            error_msg = f"Error deleting chat: {e}"
            logger.error(error_msg)
            return DeleteChatResponse(success=False, error=error_msg)
        
        
    @strawberry.mutation
    async def rate_schema(self, chat_id: str, score: int, comment: Optional[str]) -> CreateSchemaRatingResponse:
        """
        Rate a chat by ID.
        
        Args:
            chat_id: The chat ID to rate
            
        Returns:
            CreateSchemaRatingResponse indicating success or failure
        """
        try:
            ai_service = AIService()
            success, message, error = await ai_service.rate_chat(chat_id, score, comment)
            return CreateSchemaRatingResponse(success=success, message=message, error=error)
            
        except Exception as e:
            error_msg = f"Error rating chat: {e}"
            logger.error(error_msg)
            return CreateSchemaRatingResponse(success=False, message=None, error=error_msg)
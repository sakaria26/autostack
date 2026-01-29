import git
import strawberry
import uuid
import structlog
import yaml
from typing import Any, Dict, Optional, List
from datetime import datetime
from strawberry.scalars import JSON

from autostack_engine.services.ai.services.ai import AIService
from autostack_engine.utils.ai.util import generate_project_config

logger = structlog.get_logger()

@strawberry.type
class ChatInfo:
    """Type representing chat information"""
    id: str
    chat_title: Optional[str]
    prompt: str
    initial_schema: Optional[JSON]  # type: ignore
    created_at: str
    updated_at: str
    has_validation_error: bool
    validation_error: Optional[JSON] = None # type: ignore


@strawberry.type
class DeleteChatResponse:
    """Response type for chat deletion"""
    success: bool
    error: Optional[str]


@strawberry.type
class JobCreated:
    """Type representing a created AI job"""
    job_id: str
    message: str

@strawberry.type
class JobResult:
    """Type representing the status and result of an AI job"""
    id: str
    status: str
    result: Optional[JSON] = None # type: ignore
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

@strawberry.type
class UnsupportedItem:
    """Details about unsupported items"""
    technologies: Optional[List[str]] = None
    frameworks: Optional[List[str]] = None
    component_types: Optional[List[str]] = None


@strawberry.type
class SupportedItems:
    """Details about supported items"""
    technologies: Optional[JSON] = None  # type: ignore
    frameworks: Optional[List[str]] = None
    component_types: Optional[List[str]] = None

@strawberry.type
class GenerateArchitectureResponse:
    """Response type for architecture generation"""
    success: bool
    schema: Optional[JSON] = None  # type: ignore
    chat_id: Optional[str] = None
    error: Optional[str] = None
    unsupported_items: Optional[UnsupportedItem] = None
    supported_items: Optional[SupportedItems] = None
    is_validation_error: bool = False
    
    
@strawberry.type
class ModelQuery:
    
    @strawberry.field
    async def get_job(self, info: strawberry.Info, job_id: str) -> Optional[JobResult]:
        """
        Get the current status and result of an AI job.
        """
        operation_store = info.context["operation_store"]
        key = f"operation:{job_id}"
        
        # This is a bit of a hack to reuse the RedisOperationStore for AI "jobs"
        # We'll use the same key prefix to keep things unified.
        data = await operation_store.redis.hgetall(key)
        
        if not data:
            return None
            
        return JobResult(
            id=job_id,
            status=data[b'status'].decode() if b'status' in data else "PENDING",
            result=json.loads(data[b'result'].decode()) if b'result' in data and data[b'result'] else None,
            error=data[b'error'].decode() if b'error' in data and data[b'error'] else None,
            created_at=data[b'created_at'].decode() if b'created_at' in data else datetime.now().isoformat(),
            completed_at=data[b'updated_at'].decode() if b'updated_at' in data else None
        )

    @strawberry.field
    async def generate_architecture(
        self,
        description: str,
    ) -> GenerateArchitectureResponse:
        """
        Generate project architecture from description and save to database.
        
        Args:
            description: Natural language description of the project
            
        Returns:
            GenerateArchitectureResponse with schema and chat_id or error details
        """
        try:
            ai_service = AIService()
            success, result, chat_id, error = await ai_service.generate_project_config(description)
            
            if success:
                logger.info(f"Generated architecture for chat: {chat_id}")
                return GenerateArchitectureResponse(
                    success=True,
                    schema=result,
                    chat_id=chat_id,
                    error=None,
                    is_validation_error=False
                )
            else:
                # Check if result contains error information (validation error)
                if result and isinstance(result, dict) and "error" in result:
                    error_info = result["error"]
                    
                    # Extract unsupported items
                    unsupported = UnsupportedItem(
                        technologies=error_info.get("unsupported_technologies"),
                        frameworks=error_info.get("unsupported_frameworks"),
                        component_types=error_info.get("unsupported_component_types")
                    )
                    
                    # Extract supported items
                    supported = SupportedItems(
                        technologies=error_info.get("supported_technologies"),
                        frameworks=error_info.get("supported_frameworks"),
                        component_types=error_info.get("supported_component_types")
                    )
                    
                    logger.warning(f"Validation error for chat {chat_id}: {error_info.get('message', error)}")
                    
                    return GenerateArchitectureResponse(
                        success=False,
                        schema=None,
                        chat_id=chat_id,
                        error=error_info.get("message", error),
                        unsupported_items=unsupported,
                        supported_items=supported,
                        is_validation_error=True
                    )
                else:
                    # Regular error (not validation)
                    logger.error(f"Failed to generate architecture: {error}")
                    return GenerateArchitectureResponse(
                        success=False,
                        schema=None,
                        chat_id=chat_id,
                        error=error,
                        is_validation_error=False
                    )
                    
        except Exception as e:
            error_msg = f"Error generating architecture: {e}"
            logger.error(error_msg)
            return GenerateArchitectureResponse(
                success=False,
                schema=None,
                chat_id=None,
                error=error_msg,
                is_validation_error=False
            )
    
    @strawberry.field
    async def regenerate_architecture(
        self,
        chat_id: str,
        description: str,
    ) -> GenerateArchitectureResponse:
        """
        Regenerate architecture for an existing chat with updated description.
        
        Args:
            chat_id: ID of the existing chat
            description: Updated natural language description
            
        Returns:
            GenerateArchitectureResponse with updated schema
        """
        try:
            ai_service = AIService()
            success, result, updated_chat_id, error = await ai_service.regenerate_project_config(
                chat_id, description
            )
            
            if success:
                logger.info(f"Regenerated architecture for chat: {chat_id}")
                return GenerateArchitectureResponse(
                    success=True,
                    schema=result,
                    chat_id=updated_chat_id,
                    error=None,
                    is_validation_error=False
                )
            else:
                # Handle validation errors same as generate_architecture
                if result and isinstance(result, dict) and "error" in result:
                    error_info = result["error"]
                    
                    unsupported = UnsupportedItem(
                        technologies=error_info.get("unsupported_technologies"),
                        frameworks=error_info.get("unsupported_frameworks"),
                        component_types=error_info.get("unsupported_component_types")
                    )
                    
                    supported = SupportedItems(
                        technologies=error_info.get("supported_technologies"),
                        frameworks=error_info.get("supported_frameworks"),
                        component_types=error_info.get("supported_component_types")
                    )
                    
                    return GenerateArchitectureResponse(
                        success=False,
                        schema=None,
                        chat_id=chat_id,
                        error=error_info.get("message", error),
                        unsupported_items=unsupported,
                        supported_items=supported,
                        is_validation_error=True
                    )
                else:
                    return GenerateArchitectureResponse(
                        success=False,
                        schema=None,
                        chat_id=chat_id,
                        error=error,
                        is_validation_error=False
                    )
                    
        except Exception as e:
            error_msg = f"Error regenerating architecture: {e}"
            logger.error(error_msg)
            return GenerateArchitectureResponse(
                success=False,
                schema=None,
                chat_id=chat_id,
                error=error_msg,
                is_validation_error=False
            )
        
        
    @strawberry.field
    async def get_chat(self, chat_id: str) -> Optional[ChatInfo]:
        """
        Get a specific chat by ID.
        
        Args:
            chat_id: The chat ID to retrieve
            
        Returns:
            ChatInfo or None if not found
        """
        try:
            ai_service = AIService()
            chat = await ai_service.get_chat(chat_id)
            
            if chat:
                return ChatInfo(
                    id=str(chat.id),
                    chat_title=chat.chat_title,
                    prompt=chat.prompt,
                    initial_schema=chat.initial_schema,
                    created_at=chat.created_at.isoformat(),
                    updated_at=chat.updated_at.isoformat(),
                    has_validation_error=chat.has_validation_error,
                    validation_error=chat.validation_error
                )
            return None
            
        except Exception as e:
            logger.error(f"Error fetching chat: {e}")
            return None
    
    
    @strawberry.field
    async def list_chats(self) -> List[ChatInfo]:
        """
        List all chats, sorted by most recent first.
        
        Returns:
            List of ChatInfo objects
        """
        try:
            ai_service = AIService()
            chats = await ai_service.list_chats()
            
            return [
                ChatInfo(
                    id=str(chat.id),
                    chat_title=chat.chat_title,
                    prompt=chat.prompt,
                    initial_schema=chat.initial_schema,
                    created_at=chat.created_at.isoformat(),
                    updated_at=chat.updated_at.isoformat(),
                    has_validation_error=chat.has_validation_error,
                    validation_error=chat.validation_error
                )
                for chat in chats
            ]
            
        except Exception as e:
            logger.error(f"Error listing chats: {e}")
            return []

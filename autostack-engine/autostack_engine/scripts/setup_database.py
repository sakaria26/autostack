# autostack_engine/scripts/setup_database.py
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import logging

from autostack_engine.utils.database.models.beanie import Migration


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_database():
    """Initialize database connection and create collections/indexes"""
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "autostack")
    
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to MongoDB at {mongodb_url} (Attempt {attempt}/{max_retries})")
            
            # Create motor client
            client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
            
            # Check connection
            await client.admin.command('ping')
            
            # Initialize beanie with the document models
            await init_beanie(
                database=client[database_name],
                document_models=[Migration]
            )
            
            logger.info("Database initialized successfully")
            logger.info("Collections and indexes created")
            
            return client
            
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Database connection failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to setup database after {max_retries} attempts: {e}")
                raise

def main():
    """Main entry point for the setup-database script"""
    asyncio.run(setup_database())

if __name__ == "__main__":
    main()


from fastapi import FastAPI, WebSocket
from pydantic import ValidationError
from app.config import settings
from app.utils.logger import CustomLogger
from app.schemas.event_schema import EventSchema
from app.utils.redis_client import redis_client
# from app.utils.redis_client import get_redis_client
from uuid import uuid4
import json

logger = CustomLogger().get_logger(__name__)

INSTANCE_ID = str(uuid4())

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        try:
            claimed = False
            raw_data = await websocket.receive_text()
            event =  EventSchema(**json.loads(raw_data))
            if not event.event_id:
                logger.warning("Received event without event_id")
                continue
            
            is_new = await redis_client.set( # Redis SET NX is very fast (~100k ops/sec easily)
                f"dedup:{event.event_id}", INSTANCE_ID, nx=True, ex=settings.dedup_ttl_seconds
            )
            if is_new:
                #TODO: New event, proceed to persist on db 
                #TODO: Transaction control to ensure event persistence
                #TODO: failure handling
                #TODO: retry logic
                try:
                    await redis_client.delete(f"dedup:{event.event_id}")    
                except Exception as delete_error:
                    logger.error(f"Failed to delete dedup key: {delete_error}")
                claimed = True
                logger.info("Processed new event", event_id=event.event_id, event_type=event.event_type)
            
            logger.info("Received event", event_id=event.event_id, event_type=event.event_type)
        except ValidationError as e:
            error_msg = f"Invalid event format received: {e.errors()}"
            logger.error(error_msg)
            await websocket.send_text(error_msg)
        except Exception as e:

                #TODO : handle this case
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            await websocket.send_text(error_msg)
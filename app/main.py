from fastapi import FastAPI, WebSocket
from pydantic import ValidationError
from app.config import settings
from app.utils.logger import CustomLogger
from app.schemas.event_schema import EventSchema
# from app.utils.redis_client import get_redis_client
import json

logger = CustomLogger().get_logger(__name__)

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
            raw_data = await websocket.receive_text()
            event = EventSchema(**json.loads(raw_data))
            logger.info("Received event", event_id=event.event_id, event_type=event.event_type)
        except ValidationError as e:
            error_msg = f"Invalid event format received: {e.errors()}"
            logger.error(error_msg)
            await websocket.send_text(error_msg)
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            await websocket.send_text(error_msg)
from sqlalchemy.exc import IntegrityError
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from app.config import settings
from app.utils.logger import get_logger
from app.schemas.event_schema import EventSchema
from app.utils.redis_client import redis_client
from app.database.sessions import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.events_table import Events 
from uuid import uuid4
import json
from app.utils.logger import setup_logging

setup_logging()

logger = get_logger(__name__)
INSTANCE_ID = settings.instance_id

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

async def _release_lock_if_owner(dedup_key: str):
    """
    Safely release the dedup key from redis as some error occured while processing 
    (only if key owned by this instance).
    then other instance can pick it up again after TTL.
    This prevents accidental deletion of another instance's claim.

    Args:
        dedup_key (str): _description_
    """
    try:
        current_value = await redis_client.get(dedup_key)
        if current_value == INSTANCE_ID:
            await redis_client.delete(dedup_key)
            logger.debug("Released dedup key (owner match).", dedup_key=dedup_key)
        else:
            logger.debug("Did not release dedup key (owner mismatch).", dedup_key=dedup_key, current_value=current_value)
    except Exception as e:
        logger.error(f"Error while releasing dedup key: {e}", dedup_key=dedup_key)
    
async def process_persist(event: Events, db: AsyncSession):
    """
    Process and persist the event to the database.
    Args:
        event (EventSchema): The event data to persist.
        db (AsyncSession): The database session.
        
    IMPORTANT: all external side-effects must be idempotent and use event.event_id as idempotency key.
    Example external calls are :
    -> EXTERNAL SIDE-EFFECT (example): call payment/email APIs with idempotency key
    -> payment_gateway.charge(amount, idempotency_key=event.event_id)
    -> email_sender.send(template, idempotency_key=event.event_id)
    -> All of the above must be idempotent by using event.event_id.
    """

    db_item = Events(
        event_id=event.event_id,
        event_type=event.event_type,
        payload=event.payload
    )
    db.add(db_item)
    
    try:
        await db.commit()
        logger.info("Event persisted successfully.", event_id=event.event_id)
    except IntegrityError as e:
        await db.rollback()
        logger.warning("Integrity error while persisting event (possible duplicate).", event_id=event.event_id, error=str(e))
    except Exception as e:
        await db.rollback()
        logger.error("Error while persisting event.", event_id=event.event_id, error=str(e))
        raise

@app.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to /events", instance_id=INSTANCE_ID)
    
    async for db in get_db_session():
        try:
            while True:
                raw_data = await websocket.receive_text()
                try:
                    event =  EventSchema(**json.loads(raw_data))
                except ValidationError as ve:
                    error_msg = f"Invalid event format received: {ve.errors()}"
                    logger.error(error_msg)
                    # await websocket.send_text(error_msg)
                    continue
                except json.JSONDecodeError as je:
                    error_msg = f"JSON decode error: {str(je)}"
                    logger.error(error_msg)
                    # await websocket.send_text(error_msg)
                    continue
                except Exception as e:
                    logger.error(f"Error parsing event: {e}")
                    # await websocket.send_text(f"Error parsing event: {e}")
                    continue
                
                if not event.event_id:
                    logger.warning("Received event without event_id")
                    continue
                
                claimed = False
                dedup_key = f"dedup:{event.event_id}"
                try:
                    claimed = await redis_client.set( # Redis SET NX is very fast (~100k ops/sec easily)
                    dedup_key, INSTANCE_ID, nx=True, ex=settings.dedup_ttl_seconds
                )
                except Exception as redis_error:
                    logger.error(f"Redis error during deduplication check: {redis_error}")
                    # await websocket.send_text(f"Redis error: {redis_error}")
                    continue
                if not claimed:
                    logger.info("Duplicate event detected, skipping processing", event_id=event.event_id, event_type=event.event_type)
                    continue
                    
                # processing continues here for new events   
                try:
                    if event.payload.get("force_fail"):
                        logger.error("Forced failure triggered for testing", event_id=event.event_id)
                        raise Exception("Forced failure for testing")
                    await process_persist(event, db)
                except Exception as db_error:
                    logger.error(f"Database error during event persistence: {db_error}")
                    await _release_lock_if_owner(dedup_key)
                    logger.exception("Processing failed", event_id=event.event_id, exc_info=db_error)
                    continue
                    #TODO: retry logic
        except WebSocketDisconnect:
            logger.info("Client disconnected from /events", instance_id=INSTANCE_ID)
        except Exception as e:
            exception_msg = f"An error occurred: {str(e)}"
            logger.exception(exception_msg)
            # await websocket.send_text(exception_msg)
        finally:
            break
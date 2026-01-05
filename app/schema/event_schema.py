from pydantic import BaseModel
from typing import Optional

class EventSchema(BaseModel):
    event_id: int
    event_type: str
    payload: Optional[dict] = None
    timestamp: Optional[str] = None
    


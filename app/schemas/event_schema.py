from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class EventSchema(BaseModel):
    event_id: str = Field(...,  description="Unique identifier for the event", min_length=1)
    event_type: str = Field(..., description="Type of the event")
    payload: Dict[str, Any] = Field(None, description="Optional payload containing event data")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the event was created")
    


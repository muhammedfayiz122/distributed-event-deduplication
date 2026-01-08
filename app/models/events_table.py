from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import BaseModel

class Events(BaseModel):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(100), index=True, nullable=False)
    payload = Column(JSONB, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Event(id={self.id}, event_id='{self.event_id}', event_type='{self.event_type}')>"
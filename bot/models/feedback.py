from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class FeedbackMessage(BaseModel):
    from_user_id: int
    text: str
    timestamp: datetime = datetime.now()

class FeedbackTicket(BaseModel):
    ticket_id: str
    user_id: int
    username: str
    messages: List[FeedbackMessage] = []
    status: str = "open"  # open, closed
    created_at: datetime = datetime.now()
    closed_at: Optional[datetime] = None

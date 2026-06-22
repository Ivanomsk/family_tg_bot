from datetime import datetime
from pydantic import BaseModel, Field
from bot.models.base import ExpirableMixin

class ProxyUser(BaseModel, ExpirableMixin):
    tg_id: int
    username: str | None = None
    proxy_config: str | None = None  # IP:PORT:USER:PASS
    expiry_date: datetime = Field(default_factory=datetime.now)
    is_active: bool = True

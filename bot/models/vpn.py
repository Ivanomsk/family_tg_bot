from datetime import datetime
from pydantic import BaseModel, Field
from bot.models.base import ExpirableMixin

class VPNUser(BaseModel, ExpirableMixin):
    tg_id: int
    username: str | None = None
    first_name: str | None = None
    vpn_config: str | None = None
    expiry_date: datetime = Field(default_factory=datetime.now)
    is_active: bool = True

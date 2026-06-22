import uuid
from pathlib import Path
from typing import List, Optional
from bot.models.feedback import FeedbackTicket, FeedbackMessage
from bot.repositories.base_repository import BaseRepository
from bot.utils.logger import bot_logger

class FeedbackRepository(BaseRepository):
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.filename = "feedback_tickets.json"

    async def _get_all_tickets(self) -> List[FeedbackTicket]:
        data = await self._read_json(self.filename)
        return [FeedbackTicket(**item) for item in data]

    async def _save_tickets(self, tickets: List[FeedbackTicket]) -> bool:
        data = [t.model_dump(mode="json") for t in tickets]
        return await self._write_json(self.filename, data)

    async def create_ticket(self, user_id: int, username: str) -> str:
        tickets = await self._get_all_tickets()
        ticket_id = str(uuid.uuid4())
        ticket = FeedbackTicket(ticket_id=ticket_id, user_id=user_id, username=username)
        tickets.append(ticket)
        await self._save_tickets(tickets)
        return ticket_id

    async def get_active_ticket(self, user_id: int) -> Optional[FeedbackTicket]:
        tickets = await self._get_all_tickets()
        for t in tickets:
            if t.user_id == user_id and t.status == "open":
                return t
        return None

    async def add_message(self, ticket_id: str, from_user_id: int, text: str) -> bool:
        tickets = await self._get_all_tickets()
        for t in tickets:
            if t.ticket_id == ticket_id:
                t.messages.append(FeedbackMessage(from_user_id=from_user_id, text=text))
                await self._save_tickets(tickets)
                return True
        return False

    async def close_ticket(self, ticket_id: str) -> bool:
        tickets = await self._get_all_tickets()
        for t in tickets:
            if t.ticket_id == ticket_id:
                t.status = "closed"
                t.closed_at = datetime.now()
                await self._save_tickets(tickets)
                return True
        return False

    async def get_ticket_by_id(self, ticket_id: str) -> Optional[FeedbackTicket]:
        tickets = await self._get_all_tickets()
        for t in tickets:
            if t.ticket_id == ticket_id:
                return t
        return None

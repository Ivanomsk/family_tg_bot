from datetime import datetime

class ExpirableMixin:
    def is_expired(self) -> bool:
        return datetime.now() > self.expiry_date

    def days_left(self) -> int:
        if not self.expiry_date:
            return 0
        delta = self.expiry_date - datetime.now()
        return max(0, delta.days)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

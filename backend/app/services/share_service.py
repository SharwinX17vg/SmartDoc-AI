from datetime import datetime, timedelta, timezone
import os
from secrets import token_urlsafe

from ..models.schemas import SharedAnswer, ShareRequest, ShareResponse


class ShareService:
    def __init__(self, base_url: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.items: dict[str, SharedAnswer] = {}
        self.default_expiration_days = int(os.getenv("SHARE_LINK_EXPIRATION_DAYS", "7"))

    def create(self, request: ShareRequest) -> ShareResponse:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=request.expiration_days or self.default_expiration_days)
        token = token_urlsafe(24)
        self.items[token] = SharedAnswer(
            answer=request.answer,
            sources=request.sources,
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )
        return ShareResponse(share_id=token, share_url=f"{self.base_url}/api/v1/share/{token}", expires_at=expires.isoformat())

    def get(self, token: str) -> SharedAnswer | None:
        item = self.items.get(token)
        if not item or datetime.fromisoformat(item.expires_at) <= datetime.now(timezone.utc):
            self.items.pop(token, None)
            return None
        return item
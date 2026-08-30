from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.ChannelHttp import ChannelHttp


class ChannelHttpRepository(BaseRepository[ChannelHttp]):
    model = ChannelHttp

    def _before_create(self, item: ChannelHttp, db: Session) -> None:
        item.channel_http_id = uuid_generator.random()
        item.created_at = datetime.now(timezone.utc)

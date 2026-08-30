from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.ChannelMqtt import ChannelMqtt


class ChannelMqttRepository(BaseRepository[ChannelMqtt]):
    model = ChannelMqtt

    def _before_create(self, item: ChannelMqtt, db: Session) -> None:
        item.channel_mqtt_id = uuid_generator.random()
        item.created_at = datetime.now(timezone.utc)


from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.Control import Control


class ControlRepository(BaseRepository[Control]):
    model = Control

    def _before_create(self, item: Control, db: Session) -> None:
        item.control_id = uuid_generator.random()
        item.created_at = datetime.now(timezone.utc)
        item.status = False
        if self.exists(db, filters={"name": item.name}):
            raise ValidationError("name already exists")

    def _before_update(self, obj: Control, values: dict, db: Session) -> None:
        allowed = {
            "name", "type", "channel_id", "asset_type", "asset_id", "status",
            "mqtt_topic", "mqtt_retained", "mqtt_payload",
            "http_method", "http_path", "http_header", "http_params", "http_body",
        }
        for key in tuple(values):
            if key not in allowed:
                values.pop(key)
        if "name" in values:
            other = self.select_one(db, filters={"name": values["name"]})
            if other is not None and other.control_id != obj.control_id:
                raise ValidationError("name already exists")

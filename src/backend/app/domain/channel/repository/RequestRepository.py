from typing import Any, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.common.validators import ValidationError, validate_str
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from app.domain.channel.repository.models.Request import Request


class RequestRepository(BaseRepository[Request]):

    model = Request

    def _before_create(self, item: Request, db: Session) -> None:
        """ 创建前校验 """
        # 1. 自动生成 request_id
        item.request_id = uuid_generator.random()

        validate_str(item.name, "name", max_len=20)
        if self.exists(db, filters={"name": item.name}):
            raise ValidationError("name already exists")

        if item.type not in ("mqtt", "http"):
            raise ValidationError("type must be 'mqtt' or 'http'")

        # 4. 设置创建时间
        item.created_at = datetime.now(timezone.utc)

        # 5. 强制 is_active 为 False
        item.status = False

    def _before_update(self, obj: Request, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 允许编辑的字段
        # is_active 只由启停接口写入；编辑接口的 Schema 不暴露该字段。
        allowed_fields = {
            "name",
            "type",
            "channel_id",
            "interval_seconds",
            "time_json_path",
            "time_format",
            "status",
            "mqtt_topic",
            "http_method",
            "http_path",
            "http_header",
            "http_params",
            "http_body",
        }

        filtered_values = {
            k: v
            for k, v in values.items()
            if k in allowed_fields
        }

        # 2. 校验 name 唯一性
        if "name" in filtered_values:
            validate_str(filtered_values["name"], "name", max_len=20)
            if self.exists(db, filters={"name": filtered_values["name"]}):
                existing = self.select_one(db, filters={"name": filtered_values["name"]})
                if existing and existing.request_id != obj.request_id:
                    raise ValidationError("name already exists")

        if "type" in filtered_values:
            v = filtered_values["type"]
            validate_str(v, "type", max_len=10)
            if v not in ("mqtt", "http"):
                raise ValidationError("type must be 'mqtt' or 'http'")

        values.clear()
        values.update(filtered_values)

    def _before_delete(self, obj: Request, db: Session) -> None:
        """ 删除前校验 """

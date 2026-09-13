from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.settings.repository import LLMConfigRepository
from app.domain.settings.repository.models import LLMConfig
from app.domain.settings.schema import validate_provider_content
from app.infra.llm import LLMRuntimeConfig, llm_client_factory
from .LLMConfigCipher import LLMConfigCipher


class LLMConnectivityError(ValidationError):
    def __init__(self, result: dict):
        super().__init__(result.get("message", "模型连接失败"))
        self.result = result


class LLMConfigService:
    repository = LLMConfigRepository()

    @staticmethod
    def _get(llm_id: str, db: Session, *, for_update: bool = False) -> LLMConfig:
        statement = select(LLMConfig).where(LLMConfig.llm_id == llm_id)
        if for_update:
            statement = statement.with_for_update()
        row = db.scalar(statement)
        if row is None:
            raise ValidationError("模型配置不存在")
        return row

    @staticmethod
    def _serialize(row: LLMConfig) -> dict:
        content = dict(row.content or {})
        encrypted_key = content.pop("api_key", None)
        if row.service_type != "ollama":
            content["api_key_configured"] = bool(encrypted_key)
        return {
            "llm_id": row.llm_id,
            "service_name": row.service_name,
            "service_type": row.service_type,
            "content": content,
            "is_use": bool(row.is_use),
            "created_at": row.created_at,
        }

    @staticmethod
    def _plain(row: LLMConfig) -> dict:
        content = dict(row.content or {})
        if row.service_type != "ollama":
            encrypted = content.get("api_key")
            if not encrypted:
                raise ValidationError("模型 API Key 未配置")
            content["api_key"] = LLMConfigCipher.decrypt(encrypted)
        return content

    @classmethod
    def _resolve_plain(cls, service_type: str, content: dict, existing: LLMConfig | None = None) -> dict:
        content = validate_provider_content(service_type, content)
        if service_type == "ollama":
            return content
        api_key = content.get("api_key")
        if not api_key and existing is not None and existing.service_type != "ollama":
            api_key = cls._plain(existing)["api_key"]
        if not api_key:
            raise ValidationError("vLLM 和 DeepSeek 必须配置 API Key")
        content["api_key"] = api_key
        return content

    @staticmethod
    def _encrypted(service_type: str, plain: dict) -> dict:
        content = dict(plain)
        if service_type != "ollama":
            content["api_key"] = LLMConfigCipher.encrypt(content["api_key"])
        return content

    @staticmethod
    def _runtime(llm_id: str | None, service_name: str, service_type: str, plain: dict):
        return LLMRuntimeConfig(llm_id, service_type, service_name, plain)

    @classmethod
    def list(cls, db: Session, page: int, limit: int, filters):
        total, rows = cls.repository.list_page(db, page, limit, filters)
        return {"total": total, "items": [cls._serialize(row) for row in rows]}

    @classmethod
    def find(cls, llm_id: str, db: Session):
        return cls._serialize(cls._get(llm_id, db))

    @classmethod
    def add(cls, data, db: Session):
        plain = cls._resolve_plain(data.service_type, data.content)
        row = LLMConfig(
            llm_id=uuid_generator.random(),
            service_name=data.service_name,
            service_type=data.service_type,
            content=cls._encrypted(data.service_type, plain),
            is_use=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        return cls._serialize(row)

    @classmethod
    async def edit(cls, llm_id: str, data, db: Session):
        # Do not keep a database row lock while waiting for an external model.
        row = cls._get(llm_id, db)
        plain = cls._resolve_plain(data.service_type, data.content, row)
        if row.is_use:
            result = await llm_client_factory.probe(
                cls._runtime(llm_id, data.service_name, data.service_type, plain)
            )
            if not result["connected"]:
                raise LLMConnectivityError(result)
        row = cls._get(llm_id, db, for_update=True)
        row.service_name = data.service_name
        row.service_type = data.service_type
        row.content = cls._encrypted(data.service_type, plain)
        db.add(row)
        db.flush()
        return cls._serialize(row)

    @classmethod
    def drop(cls, llm_id: str, db: Session):
        row = cls._get(llm_id, db, for_update=True)
        if row.is_use:
            raise ValidationError("活动模型不能删除，请先停用或切换模型")
        db.delete(row)
        db.flush()
        return True

    @classmethod
    async def test_draft(cls, data):
        plain = cls._resolve_plain(data.service_type, data.content)
        return await llm_client_factory.probe(
            cls._runtime(None, "未保存配置", data.service_type, plain)
        )

    @classmethod
    async def test_saved(cls, llm_id: str, db: Session, override=None):
        row = cls._get(llm_id, db)
        if override is None:
            service_type, plain, service_name = row.service_type, cls._plain(row), row.service_name
        else:
            service_type = override.service_type
            plain = cls._resolve_plain(service_type, override.content, row)
            service_name = row.service_name
        return await llm_client_factory.probe(
            cls._runtime(llm_id, service_name, service_type, plain)
        )

    @classmethod
    async def activate(cls, llm_id: str, db: Session):
        target = cls._get(llm_id, db)
        result = await llm_client_factory.probe(
            cls._runtime(target.llm_id, target.service_name, target.service_type, cls._plain(target))
        )
        if not result["connected"]:
            raise LLMConnectivityError(result)
        try:
            # Lock every current candidate before applying the one-active invariant.
            list(db.scalars(select(LLMConfig).with_for_update()).all())
            db.execute(update(LLMConfig).values(is_use=False))
            target = cls._get(llm_id, db, for_update=True)
            target.is_use = True
            db.add(target)
            db.flush()
        except IntegrityError as exc:
            raise ValidationError("模型激活冲突，请刷新后重试") from exc
        return {"config": cls._serialize(target), "test": result}

    @classmethod
    def deactivate(cls, llm_id: str, db: Session):
        row = cls._get(llm_id, db, for_update=True)
        row.is_use = False
        db.add(row)
        db.flush()
        return cls._serialize(row)

    @classmethod
    def active_runtime(cls, db: Session) -> LLMRuntimeConfig:
        row = cls.repository.active(db)
        if row is None:
            raise ValidationError("模型服务未配置或未激活")
        return cls._runtime(row.llm_id, row.service_name, row.service_type, cls._plain(row))


llm_config_service = LLMConfigService()

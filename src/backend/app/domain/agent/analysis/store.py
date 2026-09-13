"""按用户隔离的智能分析 Agent 短期摘要。"""

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.Redis import redis_manager
from . import config


class AnalysisContextUnavailableError(RuntimeError):
    pass


class AnalysisContextExpiredError(RuntimeError):
    pass


class AnalysisSnapshotStore:
    KEY_PREFIX = "agent:analysis:snapshot:"

    @classmethod
    def key(cls, analysis_id: str) -> str:
        return f"{cls.KEY_PREFIX}{analysis_id}"

    @staticmethod
    def _validate_id(analysis_id: str) -> None:
        try:
            UUID(analysis_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("分析 ID 格式无效") from exc

    @staticmethod
    def _decode(value):
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def create(self, user_id: str, context: dict) -> dict:
        analysis_id = uuid_generator.random()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=config.SNAPSHOT_TTL_SECONDS)
        document = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "context": context,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            redis_manager.set(
                self.key(analysis_id),
                json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                ex=config.SNAPSHOT_TTL_SECONDS,
            )
        except Exception as exc:
            raise AnalysisContextUnavailableError("AI分析上下文服务暂不可用") from exc
        return {
            "available": True,
            "analysis_id": analysis_id,
            "expires_at": expires_at.isoformat(),
            "reason_code": None,
        }

    def load(self, user_id: str, analysis_id: str) -> dict:
        self._validate_id(analysis_id)
        try:
            raw = redis_manager.get(self.key(analysis_id))
        except Exception as exc:
            raise AnalysisContextUnavailableError("AI分析上下文服务暂不可用") from exc
        if not raw:
            raise AnalysisContextExpiredError("分析结果已过期，请重新执行分析")
        try:
            document = json.loads(self._decode(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise AnalysisContextUnavailableError("AI分析上下文数据损坏") from exc
        if document.get("user_id") != user_id:
            raise PermissionError("无权访问该分析结果")
        try:
            redis_manager.expire(self.key(analysis_id), config.SNAPSHOT_TTL_SECONDS)
        except Exception as exc:
            raise AnalysisContextUnavailableError("AI分析上下文服务暂不可用") from exc
        return document


analysis_snapshot_store = AnalysisSnapshotStore()

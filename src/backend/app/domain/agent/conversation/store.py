"""Short-lived Redis conversation storage."""

import json
from datetime import datetime, timezone
from uuid import UUID

from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.Redis import redis_manager


class ConversationUnavailableError(RuntimeError):
    pass


class ConversationStore:
    TTL_SECONDS = 30 * 60
    MAX_TURNS = 10
    MAX_CONTEXT_CHARS = 24_000
    KEY_PREFIX = "agent:conversation:"
    OWNER_PREFIX = "agent:conversation:owner:"

    @classmethod
    def key(cls, user_id: str, conversation_id: str) -> str:
        return f"{cls.KEY_PREFIX}{user_id}:{conversation_id}"

    @classmethod
    def owner_key(cls, conversation_id: str) -> str:
        return f"{cls.OWNER_PREFIX}{conversation_id}"

    @staticmethod
    def _validate_id(conversation_id: str) -> None:
        try:
            UUID(conversation_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("会话 ID 格式无效") from exc

    @staticmethod
    def _decode(value):
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def _new(self, user_id: str, agent_type: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "conversation_id": uuid_generator.random(),
            "user_id": user_id,
            "agent_type": agent_type,
            "created_at": now,
            "updated_at": now,
            "turns": [],
        }

    def _write(self, document: dict) -> None:
        try:
            payload = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
            pipeline = redis_manager.pipeline(transaction=True)
            pipeline.set(
                self.key(document["user_id"], document["conversation_id"]),
                payload,
                ex=self.TTL_SECONDS,
            )
            pipeline.set(
                self.owner_key(document["conversation_id"]),
                document["user_id"],
                ex=self.TTL_SECONDS,
            )
            pipeline.execute()
        except Exception as exc:
            raise ConversationUnavailableError("连续对话服务暂时不可用") from exc

    def load_or_create(
        self,
        user_id: str,
        conversation_id: str | None,
        agent_type: str,
    ) -> tuple[dict, bool]:
        if not conversation_id:
            document = self._new(user_id, agent_type)
            self._write(document)
            return document, False

        self._validate_id(conversation_id)
        try:
            owner = self._decode(redis_manager.get(self.owner_key(conversation_id)))
            if owner and owner != user_id:
                raise PermissionError("无权访问该对话")
            raw = redis_manager.get(self.key(user_id, conversation_id))
        except PermissionError:
            raise
        except Exception as exc:
            raise ConversationUnavailableError("连续对话服务暂时不可用") from exc

        if not raw:
            document = self._new(user_id, agent_type)
            self._write(document)
            return document, True
        try:
            document = json.loads(self._decode(raw))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ConversationUnavailableError("连续对话数据损坏，请新建对话") from exc
        if document.get("user_id") != user_id or document.get("agent_type") != agent_type:
            raise PermissionError("无权访问该对话")
        return document, False

    @classmethod
    def _trim(cls, turns: list[dict]) -> list[dict]:
        turns = turns[-cls.MAX_TURNS :]
        while turns and len(json.dumps(turns, ensure_ascii=False)) > cls.MAX_CONTEXT_CHARS:
            turns.pop(0)
        return turns

    def append(self, document: dict, user_message: str, assistant_output: dict) -> None:
        document["turns"] = self._trim([
            *document.get("turns", []),
            {"user": user_message, "assistant": assistant_output},
        ])
        document["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(document)

    def delete(self, user_id: str, conversation_id: str) -> bool:
        self._validate_id(conversation_id)
        try:
            owner = self._decode(redis_manager.get(self.owner_key(conversation_id)))
            if owner and owner != user_id:
                raise PermissionError("无权访问该对话")
            if not owner:
                return True
            redis_manager.delete(
                self.key(user_id, conversation_id),
                self.owner_key(conversation_id),
            )
            return True
        except PermissionError:
            raise
        except Exception as exc:
            raise ConversationUnavailableError("连续对话服务暂时不可用") from exc


conversation_store = ConversationStore()

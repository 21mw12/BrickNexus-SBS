"""智能分析结果解读业务编排。"""

from app.domain.agent.conversation import ConversationRunResult
from app.domain.common.PermissionChecker import get_user_id_from_token
from app.domain.data.service.PointDataAccessService import point_data_access_service
from .context import analysis_context_builder
from .model import analysis_model_client
from .store import analysis_snapshot_store


class AnalysisSnapshotService:
    def __init__(self, builder=None, store=None):
        self.builder = builder or analysis_context_builder
        self.store = store or analysis_snapshot_store

    def create(self, user_id, analytics_result, point_ids, metadata):
        context = self.builder.build(analytics_result, point_ids, metadata)
        return self.store.create(user_id, context)


class AnalysisAgentService:
    def __init__(self, model=None, store=None, user_resolver=None, access_service=None):
        self.model = model or analysis_model_client
        self.store = store or analysis_snapshot_store
        self.user_resolver = user_resolver or get_user_id_from_token
        self.access_service = access_service or point_data_access_service

    async def respond(self, data, authorization, db):
        user_id = self.user_resolver(authorization)
        document = self.store.load(user_id, data.analysis_id)
        snapshot = document["context"]
        self.access_service.require_read(snapshot.get("point_ids", []), authorization, db)
        result = await self.model.respond(
            context={"snapshot": snapshot, "db": db},
            message=data.message,
            user_id=user_id,
            conversation_id=data.conversation_id,
        )
        if not isinstance(result, ConversationRunResult):
            output = result
            conversation_id = data.conversation_id
            conversation_reset = False
        else:
            output = result.output
            conversation_id = result.conversation_id
            conversation_reset = result.conversation_reset
        return {
            "conversation_id": conversation_id,
            "conversation_reset": conversation_reset,
            **output.model_dump(),
        }


analysis_snapshot_service = AnalysisSnapshotService()
analysis_agent_service = AnalysisAgentService()

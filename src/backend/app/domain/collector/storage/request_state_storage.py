"""采集器自动停止 Request 时使用的数据库状态写入。"""

from sqlalchemy import update

from app.domain.channel.repository.models.Request import Request
from app.infra.DB.SQLConnection import sql_manager


class RequestStateStorage:
    """不经过业务接口，直接持久化采集器触发的 Request 状态变化。"""

    @staticmethod
    def deactivate(request_id: str) -> None:
        """将自动停止的 Request 持久化为未启用，防止应用重启后再次加载。"""
        with sql_manager.get_db("main") as db:
            db.execute(
                update(Request)
                .where(Request.request_id == request_id)
                .values(status=False)
            )


request_state_storage = RequestStateStorage()

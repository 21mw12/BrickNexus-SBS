from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.DB.BaseRepository import BaseRepository
from .models import LLMConfig


class LLMConfigRepository(BaseRepository[LLMConfig]):
    model = LLMConfig

    @staticmethod
    def active(db: Session, *, for_update: bool = False) -> LLMConfig | None:
        statement = select(LLMConfig).where(LLMConfig.is_use.is_(True))
        if for_update:
            statement = statement.with_for_update()
        return db.scalar(statement)

    @staticmethod
    def list_page(db: Session, page: int, limit: int, filters):
        statement = select(LLMConfig)
        count_statement = select(func.count()).select_from(LLMConfig)
        conditions = []
        if filters and filters.service_name:
            conditions.append(LLMConfig.service_name.ilike(f"%{filters.service_name}%"))
        if filters and filters.service_type:
            conditions.append(LLMConfig.service_type == filters.service_type)
        if filters and filters.is_use is not None:
            conditions.append(LLMConfig.is_use.is_(filters.is_use))
        if conditions:
            statement = statement.where(*conditions)
            count_statement = count_statement.where(*conditions)
        total = int(db.scalar(count_statement) or 0)
        rows = db.scalars(
            statement.order_by(
                LLMConfig.is_use.desc(), LLMConfig.service_name.asc(), LLMConfig.llm_id.asc()
            ).offset((page - 1) * limit).limit(limit)
        ).all()
        return total, list(rows)


from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.DB.BaseRepository import BaseRepository
from .models import Sandbox


class SandboxRepository(BaseRepository[Sandbox]):
    model = Sandbox

    @staticmethod
    def list_page(db: Session, page: int, limit: int) -> tuple[int, list[Sandbox]]:
        total = db.scalar(select(func.count()).select_from(Sandbox)) or 0
        rows = db.scalars(
            select(Sandbox)
            .order_by(Sandbox.created_at.desc(), Sandbox.sandbox_id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        return int(total), list(rows)

    @staticmethod
    def get_for_update(sandbox_id: str, db: Session) -> Sandbox | None:
        return db.scalar(
            select(Sandbox)
            .where(Sandbox.sandbox_id == sandbox_id)
            .with_for_update()
        )


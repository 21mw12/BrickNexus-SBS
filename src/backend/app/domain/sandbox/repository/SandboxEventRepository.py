from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import SandboxEvent


class SandboxEventRepository:
    @staticmethod
    def list_page(
        sandbox_id: str,
        db: Session,
        page: int,
        limit: int,
        event_type: str | None = None,
    ) -> tuple[int, list[SandboxEvent]]:
        conditions = [SandboxEvent.sandbox_id == sandbox_id]
        if event_type:
            conditions.append(SandboxEvent.event_type == event_type)
        total = db.scalar(
            select(func.count()).select_from(SandboxEvent).where(*conditions)
        ) or 0
        rows = db.scalars(
            select(SandboxEvent)
            .where(*conditions)
            .order_by(SandboxEvent.tick.desc(), SandboxEvent.event_id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        return int(total), list(rows)

    @staticmethod
    def all_fault_events(sandbox_id: str, db: Session) -> list[SandboxEvent]:
        return list(
            db.scalars(
                select(SandboxEvent)
                .where(
                    SandboxEvent.sandbox_id == sandbox_id,
                    SandboxEvent.event_type.in_(("fault_started", "fault_stopped")),
                )
                .order_by(SandboxEvent.tick.asc(), SandboxEvent.event_id.asc())
            ).all()
        )


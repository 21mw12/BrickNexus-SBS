from typing import List
from sqlalchemy.orm import Session

from app.infra.DB.BaseRepository import BaseRepository
from .models.ModelPoint import ModelPoint


class ModelPointRepository(BaseRepository[ModelPoint]):

    model = ModelPoint

    def create_points(self, model_id: str, point_ids: list[str], db: Session) -> List[ModelPoint]:
        """为指定型号批量创建全局测点绑定。"""
        result = []
        for point_id in point_ids:
            created = self.create(
                ModelPoint(model_id=model_id, point_id=point_id),
                db=db,
            )
            if created is not None:
                result.append(created)
        return result

    def get_by_model_id(self, model_id: str, db: Session) -> List[ModelPoint]:
        """ 查询指定型号的所有测点 """
        return self.select(db, filters={"model_id": model_id})

    def get_by_model_ids(self, model_ids: List[str], db: Session) -> dict[str, List[ModelPoint]]:
        """ 批量查询多个型号的测点，返回 {model_id: [points]} """
        if not model_ids:
            return {}
        all_points = self.select(db, filters={"model_id__in": model_ids})
        result: dict[str, List[ModelPoint]] = {}
        for p in all_points:
            result.setdefault(p.model_id, []).append(p)
        return result

    def delete_by_model_id(self, model_id: str, db: Session) -> int:
        """ 删除指定型号的所有测点 """
        return self.bulk_delete("model_id", [model_id], db)

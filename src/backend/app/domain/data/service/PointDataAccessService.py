"""Permission checks shared by all point-data APIs."""

from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
from app.domain.common.PermissionChecker import check_asset_instance_permission


class PointDataAccessService:
    def __init__(self, repository: SensorPointRepository | None = None) -> None:
        self.repository = repository or SensorPointRepository()

    def require_read(self, point_ids: list[str], authorization: str, db: Session, *, repository=None, checker=None) -> None:
        repository = repository or self.repository
        checker = checker or check_asset_instance_permission
        mapping = repository.get_sensor_ids_by_point_ids(point_ids, db)
        if len(mapping) != len(point_ids):
            raise ValidationError("invalid point_ids")
        for sensor_id in dict.fromkeys(mapping.values()):
            if not checker(authorization, sensor_id, "R", db):
                raise PermissionError("permission denied")


point_data_access_service = PointDataAccessService()

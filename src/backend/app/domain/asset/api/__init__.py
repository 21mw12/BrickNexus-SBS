from app.domain.asset.api.AssetAPI import router as asset_router
from app.domain.asset.api.SensorModelAPI import router as sensor_model_router
from app.domain.asset.api.PointAPI import router as point_router

__all__ = ["asset_router", "sensor_model_router", "point_router"]

"""候选查询、草稿和最终规则提交共用的对象权限校验。"""

from sqlalchemy import select

from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.domain.channel.repository.models.Control import Control
from app.domain.common.PermissionChecker import (
    get_viewable_asset_ids, check_asset_instance_permission,
)


class RulePermissionService:
    def __init__(self, authorization, db):
        self.authorization = authorization
        self.db = db
        self.visible = get_viewable_asset_ids(authorization, db)

    def readable(self, asset_id):
        return self.visible is None or asset_id in self.visible

    def asset(self, asset_id):
        asset = self.db.get(Asset, asset_id)
        if not asset or not self.readable(asset_id):
            raise PermissionError("对象不存在或无访问权限，请重新选择")
        return asset

    def point(self, point_id):
        point = self.db.get(SensorPoint, point_id)
        if not point or not self.readable(point.sensor_id):
            raise PermissionError("测点不存在或无读取权限，请重新选择")
        self.asset(point.sensor_id)
        return point

    def location(self, location_id, location_type=""):
        location = self.asset(location_id)
        if location.asset_type not in {"building", "floor", "room"} or (
            location_type and location.asset_type != location_type
        ):
            raise PermissionError("监控位置类型不匹配")
        # R 向上穿透只保证祖先可见，不代表有权监控该祖先的整个子树。
        prefix = (location.asset_path or location.asset_id).rstrip("/") + "/"
        descendants = self.db.scalars(select(Asset.asset_id).where(
            Asset.asset_path.startswith(prefix, autoescape=True)
        ))
        if any(not self.readable(asset_id) for asset_id in descendants):
            raise PermissionError("该位置包含未授权资产，请缩小到有权限的房间或测点")
        return location

    def control(self, control_id):
        control = self.db.get(Control, control_id)
        if not control or not self.readable(control.asset_id) or not check_asset_instance_permission(
            self.authorization, control.asset_id, "O", self.db
        ):
            raise PermissionError("控制项不存在或无操作权限，请重新选择")
        return control

    def validate_config(self, config):
        selector = config.selector
        if selector.type == "PointIdSelector":
            self.point(selector.point_id)
        else:
            self.location(selector.location_id, selector.location_type)
        for action in config.actions:
            if action.type == "SensorControlAction":
                self.control(action.params.control_id)

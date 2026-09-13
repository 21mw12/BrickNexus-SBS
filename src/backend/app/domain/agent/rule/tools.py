"""请求级只读候选工具。身份不出现在模型工具参数中。"""

from sqlalchemy import select, or_

from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.Point import Point
from app.domain.asset.repository.models.SensorPoint import SensorPoint
from app.domain.channel.repository.models.Control import Control
from app.domain.rule.service.RulePermissionService import RulePermissionService
from .schema import SearchQuery, RuleFormDraft


class RuleCandidateTools:
    def __init__(self, authorization, db):
        self.permissions = RulePermissionService(authorization, db)
        self.db = db

    def validate_draft(self, draft: RuleFormDraft):
        fields = draft.form
        if draft.sensor_id:
            if self.permissions.asset(draft.sensor_id).asset_type != "sensor":
                raise PermissionError("请选择传感器资产")
        if fields.point_id:
            point = self.permissions.point(fields.point_id)
            if draft.sensor_id != point.sensor_id:
                raise PermissionError("传感器与测点不匹配，请重新选择")
        if fields.location_id:
            self.permissions.location(fields.location_id, fields.location_type)
        if fields.point_definition_id:
            definition = self.db.get(Point, fields.point_definition_id)
            if definition is None:
                raise PermissionError("测点定义不存在，请重新选择")
        for action in draft.actions:
            if action.params.control_id:
                self.permissions.control(action.params.control_id)

    def describe_current(self, draft):
        """只发送当前已选对象的显示信息，避免模型仅凭不透明ID猜单位。"""
        context = {}
        if draft.sensor_id:
            sensor = self.permissions.asset(draft.sensor_id)
            context["sensor"] = {"name": sensor.name, "path": self._path(sensor)}
        if draft.form.point_id:
            point = self.permissions.point(draft.form.point_id)
            context["point"] = {"name": point.point_name, "unit": point.point_unit}
        if draft.form.location_id:
            location = self.permissions.location(draft.form.location_id, draft.form.location_type)
            context["location"] = {"name": location.name, "path": self._path(location)}
        if draft.form.point_definition_id:
            definition = self.db.get(Point, draft.form.point_definition_id)
            context["point_definition"] = {"name": definition.point_name, "unit": definition.point_unit}
        context["controls"] = [{"control_id": action.params.control_id,
            "name": self.permissions.control(action.params.control_id).name}
            for action in draft.actions if action.params.control_id]
        return context

    def _scope(self, statement, query):
        visible = self.permissions.visible
        if visible is not None:
            statement = statement.where(Asset.asset_id.in_(visible))
        if query.location_id:
            location = self.permissions.asset(query.location_id)
            prefix = (location.asset_path or location.asset_id).rstrip("/") + "/"
            statement = statement.where(or_(
                Asset.asset_id == location.asset_id,
                Asset.asset_path.startswith(prefix, autoescape=True),
            ))
        return statement

    def _path(self, asset):
        ids = (asset.asset_path or asset.asset_id).split("/")
        names = dict(self.db.execute(select(Asset.asset_id, Asset.name).where(
            Asset.asset_id.in_([key for key in ids if self.permissions.readable(key)])
        )).all())
        return " / ".join(names[key] for key in ids if key in names)

    def dispatch(self, name, arguments):
        if name not in {"search_locations", "search_points", "search_controls"}:
            raise ValueError("unsupported read-only tool")
        query = SearchQuery.model_validate(arguments)
        if name == "search_locations":
            statement = select(Asset).where(
                Asset.asset_type.in_([query.asset_type] if query.asset_type else ["building", "floor", "room"]),
                Asset.name.contains(query.keyword, autoescape=True),
                Asset.is_use.is_(True),
            )
        elif name == "search_points":
            statement = select(SensorPoint, Asset).join(Asset, Asset.asset_id == SensorPoint.sensor_id).where(
                SensorPoint.point_name.contains(query.keyword, autoescape=True), Asset.is_use.is_(True)
            )
            if query.unit:
                statement = statement.where(SensorPoint.point_unit == query.unit)
        else:
            statement = select(Control, Asset).join(Asset, Asset.asset_id == Control.asset_id).where(
                or_(Control.name.contains(query.keyword, autoescape=True), Asset.name.contains(query.keyword, autoescape=True)),
                Asset.is_use.is_(True), Control.status.is_(True),
            )
        statement = self._scope(statement, query).order_by(Asset.name, Asset.asset_id)
        if name == "search_points":
            statement = statement.order_by(SensorPoint.point_id)
        elif name == "search_controls":
            statement = statement.order_by(Control.control_id)
        # 检查操作权限/子树权限后再分页，避免未授权条目进入候选或分页计数。
        offset = (query.page - 1) * 20
        accepted = 0
        items = []
        rows = self.db.execute(statement.execution_options(yield_per=100))
        try:
            for row in rows:
                if name == "search_locations":
                    asset = row[0]
                    try:
                        self.permissions.location(asset.asset_id)
                    except PermissionError:
                        continue
                    item = {"location_id": asset.asset_id, "location_type": asset.asset_type, "name": asset.name}
                elif name == "search_points":
                    point, asset = row
                    item = {"point_id": point.point_id, "sensor_id": point.sensor_id, "point_definition_id": point.source_point_id,
                            "name": point.point_name, "unit": point.point_unit, "sensor_name": asset.name}
                else:
                    control, asset = row
                    try:
                        self.permissions.control(control.control_id)
                    except PermissionError:
                        continue
                    item = {"control_id": control.control_id, "name": control.name, "asset_name": asset.name}
                accepted += 1
                if accepted <= offset:
                    continue
                if len(items) == 20:
                    return {"items": items, "has_more": True, "page": query.page}
                item["path"] = self._path(asset)
                items.append(item)
        finally:
            rows.close()
        return {"items": items, "has_more": False, "page": query.page}


TOOL_DESCRIPTIONS = {
    "search_locations": "查询有权限监控完整子树的楼宇、楼层、房间。keyword 为名称片段；location_id 用于限定父级。返回真实位置ID和路径。",
    "search_points": "查询权限内实例测点。keyword 为测点名称片段（如二氧化碳），可按location_id和unit缩小范围。返回传感器ID、实例测点ID、全局定义ID。",
    "search_controls": "查询有读取及操作权限、已启用的控制项。按名称片段和位置查找，不返回控制协议或凭据。",
}

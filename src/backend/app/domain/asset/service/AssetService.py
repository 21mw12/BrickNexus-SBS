import os
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from sqlalchemy import func, select
from app.core.utils.ExcelUtil import ExcelUtil
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.asset.repository.models import *
from app.domain.asset.repository import *
from app.domain.asset.schema import *
from app.domain.channel.repository.models.Request import Request



class AssetService:
    """资产相关业务逻辑封装"""

    TYPE_MAP = {
        "building": {
            "model": AssetBuilding,
            "repo": AssetBuildingRepository,
            "response": BuildingResponseSchema
        },
        "floor": {
            "model": AssetFloor,
            "repo": AssetFloorRepository,
            "response": FloorResponseSchema
        },
        "room": {
            "model": AssetRoom,
            "repo": AssetRoomRepository,
            "response": RoomResponseSchema
        },
        "terminal": {
            "model": AssetTerminal,
            "repo": AssetTerminalRepository,
            "response": TerminalResponseSchema
        },
        "sensor": {
            "model": AssetSensor,
            "repo": AssetSensorRepository,
            "response": SensorResponseSchema
        },
    }

    # ==========================================================
    # 辅助函数
    # ==========================================================

    @staticmethod
    def _prune_tree(nodes: list, viewable: set) -> list:
        """按 viewable 集合递归剪枝，移除不可查看的分支"""
        result = []
        for node in nodes:
            aid = node.get("asset_id")
            children = node.get("sub_assets") or []
            pruned_children = AssetService._prune_tree(children, viewable)
            if aid in viewable or pruned_children:
                node_copy = dict(node)
                node_copy["sub_assets"] = pruned_children
                result.append(node_copy)
        return result

    @staticmethod
    def _validate_terminal_request_binding(
        db: Session,
        target_request_id: str | None,
        current_request_id: str | None = None,
    ) -> None:
        """在 Service 层校验 Terminal 不能绑定、解绑或切换运行中的 Request。"""
        if current_request_id:
            current_request = db.get(Request, current_request_id)
            if current_request is not None and current_request.is_active:
                raise ValidationError("terminal bound to a running request cannot be edited")

        if target_request_id is not None:
            target_request = db.get(Request, target_request_id)
            if target_request is None:
                raise ValidationError("request not found")
            if target_request.is_active:
                raise ValidationError("terminal cannot bind to a running request")

    # ==========================================================
    # API相关Service
    # ==========================================================

    def save_new_asset(self, asset_data: AssetAddSchema, db: Session, creator_user_id: str | None = None) -> Dict[str, Any]:
        """
        创建资产。传入 creator_user_id 时自动授予创建者全部权限。
        :param asset_data: 用于新建资产 Schema 对象
        :param db: 数据库会话
        :param creator_user_id: 创建者用户ID（可选）
        :return: 新建的资产对象的字典
        """
        # 1. schema 转 dict
        if hasattr(asset_data, "model_dump"):
            payload = asset_data.model_dump(exclude_none=True)
        else:
            payload = asset_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        # 2. 获取资产类型
        asset_type = payload.get("asset_type")
        type_info  = self.TYPE_MAP.get(asset_type)
        if not type_info :
            raise ValidationError("unsupported asset_type")

        # Terminal 新建时的 Request 绑定校验属于业务规则，由 Service 负责。
        if asset_type == "terminal" and payload.get("request_id") is not None:
            self._validate_terminal_request_binding(db, payload["request_id"])

        # 3. Repository
        asset_repo = AssetRepository()
        type_repo = type_info["repo"]()
        response_cls = type_info["response"]

        # 4. 开启事务
        try:
            # 5. 构造主资产，并创建
            asset = asset_data.to_asset_model()
            asset = asset_repo.create(asset, db=db)
            if asset is None:
                raise ValidationError("create asset failed")

            # 8. 创建类型资产
            asset_attr = asset_data.to_type_model(asset.asset_id)
            asset_attr = type_repo.create(asset_attr, db=db)

            # 9. 更新祖先 count
            asset_repo.increase_ancestor_counts(asset.asset_path, asset.asset_type, db=db)

            # 10. 提交事务 & refresh
            db.commit()
            db.refresh(asset)
            if asset_attr is not None:
                db.refresh(asset_attr)
            from app.infra.RDF import asset_rdf_runtime
            asset_rdf_runtime.request_rebuild()

            # 11. 传感器类型时，关联查询 SensorModel 获取型号信息和测点
            sensor_model_info = None
            points = []
            sensor_points = []
            if asset.asset_type == "sensor" and asset_attr is not None and asset_attr.model_id:
                sensor_model_info = db.get(SensorModel, asset_attr.model_id)
                point_repo = ModelPointRepository()
                points = point_repo.get_by_model_id(asset_attr.model_id, db)
                from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
                sensor_point_repo = SensorPointRepository()
                sensor_points = sensor_point_repo.get_by_sensor_id(asset.asset_id, db)

            # 12. 构造响应
            result = response_cls.from_models(asset, asset_attr, sensor_model_info=sensor_model_info, points=points, sensor_points=sensor_points).model_dump()

            # 13. 创建者自动获得该资产的全部权限
            if creator_user_id:
                from app.domain.auth.service.UserAssetService import UserAssetService
                UserAssetService.grant_creator_permissions(
                    creator_user_id, result["asset_id"], asset.asset_type, db=db
                )

            return result

        except Exception:
            # 12. 回滚事务
            db.rollback()

            raise

    def query_asset_by_id(self, asset_id: str, db: Session) -> Dict[str, Any]:
        """
        根据资产 ID 查询资产信息
        :param asset_id: 要查询的资产 ID
        :param db: 数据库会话
        :return: 新建的资产对象的字典
        """
        # 1. Repository
        asset_repo = AssetRepository()

        # 2. 查询主资产
        asset = asset_repo.get(asset_id, db=db)
        if asset is None:
            raise ValidationError("asset not exists")

        # 3. 获取类型配置
        type_info = self.TYPE_MAP.get(asset.asset_type)
        if not type_info:
            raise ValidationError("unsupported asset_type")

        # 4. 查询类型资产
        type_repo = type_info["repo"]()
        asset_attr = type_repo.get(asset.asset_id, db=db)

        # 5. 查询父资产名称
        parent_name = None
        if asset.asset_id_parent:
            parent = asset_repo.get(asset.asset_id_parent, db=db)
            if parent is not None:
                parent_name = parent.name

        # 6. 传感器类型时，关联查询 SensorModel 获取型号信息和测点
        sensor_model_info = None
        points = []
        sensor_points = []
        if asset.asset_type == "sensor" and asset_attr is not None and asset_attr.model_id:
            sensor_model_info = db.get(SensorModel, asset_attr.model_id)
            point_repo = ModelPointRepository()
            points = point_repo.get_by_model_id(asset_attr.model_id, db)
            from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
            sensor_point_repo = SensorPointRepository()
            sensor_points = sensor_point_repo.get_by_sensor_id(asset.asset_id, db)

        # 7. 构造响应
        response_cls = type_info["response"]
        result = response_cls.from_models(asset, asset_attr, sensor_model_info=sensor_model_info, points=points, sensor_points=sensor_points, parent_name=parent_name)
        return result.model_dump()

    def alter_asset_by_id(self, asset_id: str, asset_data: AssetUpdateSchema, db: Session) -> Dict[str, Any]:
        """
        根据资产 ID 修改资产
        :param asset_id: 要修改的资产 ID
        :param asset_data: 用于修改资产 Schema 对象
        :param db: 数据库会话
        :return: 修改的资产对象的字典
        """
        # 1. schema 转 dict
        if hasattr(asset_data, "model_dump"):
            payload = asset_data.model_dump(exclude_none=True)
        else:
            payload = asset_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        # 2. 查询主资产
        asset_repo = AssetRepository()
        asset = asset_repo.get(asset_id, db=db)
        if asset is None:
            raise ValidationError("asset not exists")

        # 3. 获取资产类型
        asset_type = payload.get("asset_type")
        type_info  = self.TYPE_MAP.get(asset_type)
        if not type_info :
            raise ValidationError("unsupported asset_type")

        # 4. 校验资产类型
        if asset.asset_type != asset_data.asset_type:
            raise ValidationError("asset exists but isn't this type")

        # 通用资产编辑入口也必须遵守运行中 Request 不可变更绑定的规则。
        request_field_set = (
            "request_id" in asset_data.model_fields_set
            if hasattr(asset_data, "model_fields_set")
            else "request_id" in payload
        )
        if asset_type == "terminal" and request_field_set:
            terminal_attr = db.get(AssetTerminal, asset_id)
            current_request_id = terminal_attr.request_id if terminal_attr else None
            target_request_id = getattr(asset_data, "request_id", payload.get("request_id"))
            self._validate_terminal_request_binding(
                db,
                target_request_id,
                current_request_id,
            )
            # exclude_none 会移除显式解绑值，这里重新放回 payload。
            payload["request_id"] = target_request_id

        # 5. Repository
        type_repo = type_info["repo"]()
        response_cls = type_info["response"]

        # 6. 保存旧状态（用于父资产变更和 is_use 传播）
        prev_is_use = asset.is_use
        new_is_use = payload.get("is_use", prev_is_use)
        is_use_all = payload.get("is_use_all", False)
        new_parent_id = payload.get("asset_id_parent")
        old_path = asset.asset_path

        # 7. 处理父资产变更
        parent_changed = False
        old_parent_id = asset.asset_id_parent
        if new_parent_id is not None and new_parent_id != old_parent_id:
            # building 不允许有父资产
            if asset.asset_type == "building":
                raise ValidationError("building cannot have parent")

            new_parent = asset_repo.get(new_parent_id, db=db)
            if new_parent is None:
                raise ValidationError("new parent asset not found")

            # 校验父子类型关系
            AssetRepository._validate_parent_type(asset, new_parent)

            # 房间移动到其他楼层后，原平面图坐标不再有效，随当前事务删除标记。
            if asset.asset_type == "room":
                from app.domain.floor_plan.service.FloorPlanService import FloorPlanService
                FloorPlanService.delete_room_region(asset_id, db)

            # 不允许将资产移动到自己的子节点下（防止循环）
            if new_parent.asset_path and asset_id in new_parent.asset_path.split("/"):
                raise ValidationError("cannot move asset under its own descendant")

            # 旧祖先减 count
            type_counts = {asset.asset_type: 1}
            sub_assets = asset_repo.select_tree(old_path, db) if old_path else []
            for sub in (sub_assets or []):
                type_counts[sub.asset_type] = type_counts.get(sub.asset_type, 0) + 1
            asset_repo.decrease_ancestor_counts(old_path, type_counts, db)

            # 更新自身及所有子资产的 asset_path
            new_self_path = AssetRepository._build_path(asset_id, new_parent)
            asset.asset_path = new_self_path
            asset.asset_id_parent = new_parent_id
            db.add(asset)

            for sub in (sub_assets or []):
                old_sub_path = sub.asset_path
                if old_sub_path and old_path:
                    sub.asset_path = new_self_path + old_sub_path[len(old_path):]
                db.add(sub)

            # 新祖先加 count
            asset_repo.increase_ancestor_counts(new_self_path, asset.asset_type, db)
            for sub in (sub_assets or []):
                asset_repo.increase_ancestor_counts(sub.asset_path, sub.asset_type, db)

            parent_changed = True
            # 从 payload 中移除 asset_id_parent，避免 update 方法重复处理
            payload.pop("asset_id_parent", None)

        # 8. 开启事务
        try:
            # 9. 更新主表（asset_id_parent 已在上面处理或不变）
            asset = asset_repo.update(asset_id, payload, db=db)

            # 10. 更新类型表
            asset_attr = type_repo.update(asset_id, payload, db=db)

            # 11. 前后 is_use 状态不一致，需要状态传播
            if prev_is_use != new_is_use:
                current_path = asset.asset_path if parent_changed else old_path
                if new_is_use is False:
                    asset_repo.update_descendants_is_use(current_path, False, db=db)
                else:
                    asset_repo.update_ancestors_is_use(current_path, True, db=db)
                    if is_use_all:
                        asset_repo.update_descendants_is_use(current_path, True, db=db)

            # 12. 提交事务 & refresh
            db.commit()
            if asset is not None:
                db.refresh(asset)
            if asset_attr is not None:
                db.refresh(asset_attr)
            from app.infra.RDF import asset_rdf_runtime
            asset_rdf_runtime.request_rebuild()

            # 13. 传感器类型时，关联查询 SensorModel 获取型号信息和测点
            sensor_model_info = None
            points = []
            sensor_points = []
            if asset.asset_type == "sensor" and asset_attr is not None and asset_attr.model_id:
                sensor_model_info = db.get(SensorModel, asset_attr.model_id)
                point_repo = ModelPointRepository()
                points = point_repo.get_by_model_id(asset_attr.model_id, db)
                from app.domain.asset.repository.SensorPointRepository import SensorPointRepository
                sensor_point_repo = SensorPointRepository()
                sensor_points = sensor_point_repo.get_by_sensor_id(asset.asset_id, db)

            # 14. 构造响应
            result = response_cls.from_models(asset, asset_attr, sensor_model_info=sensor_model_info, points=points, sensor_points=sensor_points)
            return result.model_dump()

        except Exception:
            db.rollback()
            raise

    def drop_asset_by_id(self, asset_id: str, db: Session) -> bool:
        """
        根据 id 删除整棵资产树（含权限清理）。
        :param asset_id: 根资产 ID
        :param db: 数据库会话
        :return: 删除是否成功
        """
        # 1. Repository 初始化
        asset_repo = AssetRepository()

        # 2. 查询根节点
        root_asset = asset_repo.get(asset_id, db)
        if root_asset is None:
            raise ValidationError("asset not exists")

        # 3. 查询所有后代节点（无后代时仅删除自身）
        sub_assets = asset_repo.select_tree(root_asset.asset_path, db)
        assets = (sub_assets or []) + [root_asset]

        # 4. 收集所有 asset_id
        asset_ids = [ item.asset_id for item in assets ]

        # 5. 统计删除数量
        delete_counter = defaultdict(int)
        for item in assets:
            delete_counter[ item.asset_type ] += 1

        # 6. 开启事务，执行删除
        try:
            # 资产扩展表删除前，先清理平面图数据库记录并保存待删文件名。
            # 这里会同时覆盖直接删除 Floor、Room 以及删除整栋 Building 的情况。
            from app.domain.floor_plan.service.FloorPlanService import FloorPlanService
            floor_ids = [item.asset_id for item in assets if item.asset_type == "floor"]
            room_ids = [item.asset_id for item in assets if item.asset_type == "room"]
            floor_plan_image_names = FloorPlanService.delete_for_assets(
                floor_ids,
                room_ids,
                db,
            )

            # 7. 更新祖先 count
            asset_repo.decrease_ancestor_counts(root_asset.asset_path, delete_counter, db)

            # 8. 批量删除扩展表
            for asset_type, type_info in (self.TYPE_MAP.items()):
                ids = [
                    item.asset_id
                    for item in assets
                    if item.asset_type == asset_type
                ]
                if not ids:
                    continue

                repo = type_info["repo"]()
                repo.bulk_delete("asset_id", ids, db)

            # 9. 批量删除主表
            asset_repo.bulk_delete("asset_id", asset_ids, db)

            # 10. 清理权限记录
            from app.domain.auth.service.RoleAssetService import RoleAssetService
            from app.domain.auth.service.UserAssetService import UserAssetService
            RoleAssetService.drop_asset_permission_by_asset_ids(asset_ids, db)
            UserAssetService.drop_user_assets_by_asset_ids(asset_ids, db)

            # 11. 提交事务
            db.commit()
            from app.infra.RDF import asset_rdf_runtime
            asset_rdf_runtime.request_rebuild()

            # 数据库已经提交后再删除图片，避免数据库回滚时原图已经丢失。
            FloorPlanService.delete_image_files(floor_plan_image_names)
            return True

        # 12. 回滚事务
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def query_assets_tree(db: Session, viewable: set | None = None) -> List[Dict[str, Any]]:
        """返回按层级构造的树形资产列表，可选按 viewable 集合剪枝"""
        stmt = select(Asset).order_by(Asset.asset_path)
        rows = db.execute(stmt).scalars().all()

        # 批量查询终端和传感器的扩展表，获取 is_online
        terminal_ids = [a.asset_id for a in rows if a.asset_type == "terminal"]
        sensor_ids = [a.asset_id for a in rows if a.asset_type == "sensor"]
        terminal_online: Dict[str, bool] = {}
        sensor_online: Dict[str, bool] = {}
        if terminal_ids:
            terminal_rows = db.execute(select(AssetTerminal).where(AssetTerminal.asset_id.in_(terminal_ids))).scalars().all()
            terminal_online = {t.asset_id: t.is_online for t in terminal_rows}
        if sensor_ids:
            sensor_rows = db.execute(select(AssetSensor).where(AssetSensor.asset_id.in_(sensor_ids))).scalars().all()
            sensor_online = {s.asset_id: s.is_online for s in sensor_rows}

        nodes: Dict[str, Dict[str, Any]] = {}
        roots: List[Dict[str, Any]] = []
        for a in rows:
            node = {"asset_id": a.asset_id, "name": a.name}
            if a.asset_type == "terminal":
                node["is_online"] = terminal_online.get(a.asset_id, False)
            elif a.asset_type == "sensor":
                node["is_online"] = sensor_online.get(a.asset_id, False)
            nodes[a.asset_id] = node
        for a in rows:
            if a.asset_id_parent and a.asset_id_parent in nodes:
                parent = nodes[a.asset_id_parent]
                parent.setdefault("sub_assets", []).append(nodes[a.asset_id])
            else:
                roots.append(nodes[a.asset_id])

        if viewable is not None:
            roots = AssetService._prune_tree(roots, viewable)
        return roots
    
    @staticmethod
    def query_assets_form(db: Session, page: int = 1, limit: int = 20, filters: Optional[AssetQueryFilterSchema] = None, asset_ids: Optional[set] = None) -> Dict[str, Any]:
        """分页/模糊查询资产表格信息，返回 { total, items }"""
        offset = max(0, (page - 1) * limit)
        stmt = select(Asset)
        count_stmt = select(func.count()).select_from(Asset)

        # 预过滤：限定可查看的资产范围
        if asset_ids is not None:
            if not asset_ids:
                return {"total": 0, "items": []}
            stmt = stmt.where(Asset.asset_id.in_(asset_ids))
            count_stmt = count_stmt.where(Asset.asset_id.in_(asset_ids))

        payload: Dict[str, Any] = {}
        if filters is not None:
            if hasattr(filters, "model_dump"):
                payload = filters.model_dump(exclude_none=True)
            elif isinstance(filters, dict):
                payload = filters

        is_online_filter: bool | None = None
        asset_type: str | None = None
        if payload:
            like_filters: Dict[str, Any] = {}
            strict_filters: Dict[str, Any] = {}
            if payload.get("name"):
                like_filters["name"] = payload.get("name")
            if "is_use" in payload:
                strict_filters["is_use"] = payload.get("is_use")
            if "is_online" in payload:
                is_online_filter = payload.pop("is_online")
            if "asset_type" in payload:
                strict_filters["asset_type"] = payload.get("asset_type")
                asset_type = payload.get("asset_type")

            for key, value in like_filters.items():
                if key in strict_filters or value is None:
                    continue
                column = getattr(Asset, key)
                stmt = stmt.where(column.like(f"%{value}%"))
                count_stmt = count_stmt.where(column.like(f"%{value}%"))

            for key, value in strict_filters.items():
                column = getattr(Asset, key)
                stmt = stmt.where(column == value)
                count_stmt = count_stmt.where(column == value)

        # is_online 过滤：需 LEFT JOIN 终端/传感器扩展表
        if is_online_filter is not None and asset_type in ("terminal", "sensor"):
            if asset_type == "terminal":
                stmt = stmt.join(AssetTerminal, Asset.asset_id == AssetTerminal.asset_id).where(AssetTerminal.is_online == is_online_filter)
                count_stmt = count_stmt.join(AssetTerminal, Asset.asset_id == AssetTerminal.asset_id).where(AssetTerminal.is_online == is_online_filter)
            elif asset_type == "sensor":
                stmt = stmt.join(AssetSensor, Asset.asset_id == AssetSensor.asset_id).where(AssetSensor.is_online == is_online_filter)
                count_stmt = count_stmt.join(AssetSensor, Asset.asset_id == AssetSensor.asset_id).where(AssetSensor.is_online == is_online_filter)

        total = db.execute(count_stmt).scalar() or 0
        rows = db.execute(stmt.offset(offset).limit(limit)).scalars().all()

        # 批量查询终端和传感器的扩展表，获取 is_online
        terminal_ids = [a.asset_id for a in rows if a.asset_type == "terminal"]
        sensor_ids = [a.asset_id for a in rows if a.asset_type == "sensor"]
        terminal_online: Dict[str, bool] = {}
        sensor_online: Dict[str, bool] = {}
        if terminal_ids:
            terminal_rows = db.execute(select(AssetTerminal).where(AssetTerminal.asset_id.in_(terminal_ids))).scalars().all()
            terminal_online = {t.asset_id: t.is_online for t in terminal_rows}
        if sensor_ids:
            sensor_rows = db.execute(select(AssetSensor).where(AssetSensor.asset_id.in_(sensor_ids))).scalars().all()
            sensor_online = {s.asset_id: s.is_online for s in sensor_rows}

        items: List[Dict[str, Any]] = []
        for a in rows:
            if a.asset_type == "terminal":
                online = terminal_online.get(a.asset_id, False)
            elif a.asset_type == "sensor":
                online = sensor_online.get(a.asset_id, False)
            else:
                online = None
            item = {
                "id": a.asset_id,
                "name": a.name,
                "type": a.asset_type,
                "floor_count": a.floor_count,
                "room_count": a.room_count,
                "terminal_count": a.terminal_count,
                "sensor_count": a.sensor_count,
                "is_use": a.is_use,
            }
            if online is not None:
                item["is_online"] = online
            items.append(item)
        return {"total": total, "items": items}

    @staticmethod
    def export_assets_excel(db: Session, export_dir: str) -> str:
        assets = db.execute(select(Asset)).scalars().all()
        buildings = [a for a in assets if a.asset_type == "building"]
        floors = [a for a in assets if a.asset_type == "floor"]
        rooms = [a for a in assets if a.asset_type == "room"]
        terminals = [a for a in assets if a.asset_type == "terminal"]
        sensors = [a for a in assets if a.asset_type == "sensor"]

        floors_by_parent: Dict[str, List[Asset]] = {}
        rooms_by_parent: Dict[str, List[Asset]] = {}
        terminals_by_parent: Dict[str, List[Asset]] = {}
        sensors_by_parent: Dict[str, List[Asset]] = {}

        for item in floors:
            floors_by_parent.setdefault(item.asset_id_parent or "", []).append(item)
        for item in rooms:
            rooms_by_parent.setdefault(item.asset_id_parent or "", []).append(item)
        for item in terminals:
            terminals_by_parent.setdefault(item.asset_id_parent or "", []).append(item)
        for item in sensors:
            sensors_by_parent.setdefault(item.asset_id_parent or "", []).append(item)

        room_attrs = {
            r.asset_id: r for r in db.execute(select(AssetRoom)).scalars().all()
        }
        terminal_attrs = {
            t.asset_id: t for t in db.execute(select(AssetTerminal)).scalars().all()
        }

        headers = [
            "楼宇名称",
            "楼层名称",
            "房间名称",
            "房间类型",
            "终端名称",
            "物联网卡激活人",
            "传感器名称",
        ]

        os.makedirs(export_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(export_dir, f"assets_{ts}.xlsx")
        excel = ExcelUtil(file_path)

        wrote_any_sheet = False
        used_names: Dict[str, int] = {}
        for building in buildings:
            name = building.name or building.asset_id
            base = name[:31]
            count = used_names.get(base, 0)
            used_names[base] = count + 1
            sheet_name = base if count == 0 else f"{base[:28]}_{count + 1}"

            if not wrote_any_sheet:
                excel.sheet.title = sheet_name
                excel.select_sheet(sheet_name)
                wrote_any_sheet = True
            else:
                excel.add_sheet(sheet_name)
                excel.select_sheet(sheet_name)

            excel.write_row(1, headers)
            row = 2

            for floor in floors_by_parent.get(building.asset_id, []):
                for room in rooms_by_parent.get(floor.asset_id, []):
                    room_attr = room_attrs.get(room.asset_id)
                    room_type = room_attr.room_purpose if room_attr else None

                    for terminal in terminals_by_parent.get(room.asset_id, []):
                        terminal_attr = terminal_attrs.get(terminal.asset_id)
                        iot_human = terminal_attr.iot_activate_human if terminal_attr else None
                        terminal_sensors = sensors_by_parent.get(terminal.asset_id, [])

                        if not terminal_sensors:
                            excel.write_row(row, [
                                building.name,
                                floor.name,
                                room.name,
                                room_type,
                                terminal.name,
                                iot_human,
                                None,
                            ])
                            row += 1
                            continue

                        for sensor in terminal_sensors:
                            excel.write_row(row, [
                                building.name,
                                floor.name,
                                room.name,
                                room_type,
                                terminal.name,
                                iot_human,
                                sensor.name,
                            ])
                            row += 1

        if not wrote_any_sheet:
            excel.write_row(1, headers)

        excel.save()
        excel.close()
        return file_path

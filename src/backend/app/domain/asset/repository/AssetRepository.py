from typing import Any, Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.common.validators import (
    ValidationError,
    validate_bool,
    validate_str,
    validate_update,
)
from app.core.utils.UUIDGenerator import uuid_generator
from app.infra.DB.BaseRepository import BaseRepository
from .models.Asset import Asset


class AssetRepository(BaseRepository[Asset]):

    model = Asset

    # ==========================================================
    # 辅助方法
    # ==========================================================

    @staticmethod
    def _build_path(asset_id: str, parent: Optional[Asset]) -> str:
        """
        生成资产路径
        :param asset_id: 当前资产 ID
        :param parent: 父资产对象
        :return: 资产路径
        """
        # 1. 根节点直接返回自身 ID
        if parent is None or not parent.asset_path:
            return asset_id

        # 2. 拼接父路径
        return f"{parent.asset_path}/{asset_id}"

    @staticmethod
    def _validate_parent_type(item: Asset, parent: Optional[Asset]) -> None:
        """
        校验父资产类型是否合法
        规则示例：创建 `floor` 时父资产必须是 `building`;创建 `room` 时父资产必须是 `floor`，以此类推；`building` 不允许有父资产。
        :param item: 当前资产
        :param parent: 父资产
        :return:
        """
        # 1. 定义父子关系规则
        parent_required = {
            "building": None,
            "floor": "building",
            "room": "floor",
            "terminal": "room",
            "sensor": "terminal",
        }
        required = parent_required.get(item.asset_type)

        # 2. building 不允许存在父节点
        if required is None:
            if item.asset_id_parent:
                raise ValidationError("building cannot have parent")
            return

        # 3. 非 building 必须存在父节点
        if parent is None:
            raise ValidationError("asset_id_parent not found")

        # 4. 校验父节点类型
        if parent.asset_type != required:
            raise ValidationError(f"invalid parent asset_type, expected {required}")


    # ==========================================================
    # 功能方法
    # ==========================================================

    def decrease_ancestor_counts(
            self,
            asset_path: str,
            counters: dict[str, int],
            db: Session,
    ) -> None:
        """
        减少祖先统计数量
        :param asset_path: 被删除的资产的资产路径
        :param counters: 每个类目要删除的数量
        :param db: 数据库会话
        :return:
        """
        # 1. count 字段映射
        field_map = {
            "floor": "floor_count",
            "room": "room_count",
            "terminal": "terminal_count",
            "sensor": "sensor_count",
        }

        # 2. 解析祖先 ID
        ancestor_ids = ((asset_path or "").split("/")[:-1])
        if not ancestor_ids:
            return

        # 3. 查询所有祖先
        parents = self.select(
            db=db,
            filters={
                "asset_id__in": ancestor_ids
            },
        )

        # 4. 更新 count
        for parent in parents:
            for asset_type, count in counters.items():

                field = field_map.get(asset_type)
                if field is None:
                    continue

                current = getattr(parent, field, 0)

                setattr(parent, field, max(0, current - count))

            db.add(parent)

    def increase_ancestor_counts(
            self,
            asset_path: str,
            asset_type: str,
            db: Session,
    ) -> None:
        """
        增加祖先统计数量
        :param asset_path: 添加的资产的资产路径
        :param asset_type: 添加的资产类型
        :param db: 数据库会话
        :return:
        """
        # 1. count 字段映射
        field_map = {
            "floor": "floor_count",
            "room": "room_count",
            "terminal": "terminal_count",
            "sensor": "sensor_count",
        }

        field = field_map.get(asset_type)
        if field is None:
            return

        # 2. 解析祖先 ID
        ancestor_ids = ((asset_path or "").split("/")[:-1])
        if not ancestor_ids:
            return

        # 3. 查询所有祖先
        parents = self.select(
            db=db,
            filters={
                "asset_id__in": ancestor_ids
            },
        )

        # 3. 更新 count
        for parent in parents:
            current = getattr(parent, field, 0)
            setattr(parent, field, current + 1)

            db.add(parent)


    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: Asset, db: Session) -> None:
        """ 创建前处理 """
        # 1. 校验基础字段（必须有 asset_type 和 name）
        validate_str(item.asset_type, "asset_type", max_len=20)
        validate_str(item.name, "name", max_len=100)
        if item.asset_id_parent is not None:
            validate_str(item.asset_id_parent, "asset_id_parent", max_len=100)

        # 2. 校验资产类型是否合法
        if item.asset_type not in {"building", "floor", "room", "terminal", "sensor"}:
            raise ValidationError("invalid asset_type")

        # 3. 校验资产名称是否重复
        stmt = select(Asset).where(Asset.name == item.name)
        exists = db.execute(stmt).scalars().first()
        if exists:
            raise ValidationError("name already exists")

        # 4. 查询父资产
        parent = None
        if item.asset_id_parent:
            parent = db.get(Asset, item.asset_id_parent)
            if parent is None:
                raise ValidationError("asset_id_parent not found")
            # 5. 校验父子关系是否合法
            self._validate_parent_type(item, parent)

        # 6. 生成资产 ID
        item.asset_id = uuid_generator.random()

        # 7. 生成资产路径
        item.asset_path = self._build_path(item.asset_id, parent)

        # 8. 初始化统计字段
        item.floor_count = 0
        item.room_count = 0
        item.terminal_count = 0
        item.sensor_count = 0

        # 9. 默认启用状态
        if item.is_use is None:
            item.is_use = False

    def _before_update(self, obj: Asset, values: Dict[str, Any], db: Session) -> None:
        """ 更新前校验 """
        # 1. 定义允许更新字段
        allowed_fields = {"name", "is_use", "asset_id_parent"}

        # 2. 过滤非法字段，无更新字段直接返回
        filtered_values = {
            k: v
            for k, v in values.items()
            if k in allowed_fields
        }
        if not filtered_values:
            return

        # 3. 定义字段校验规则，并校验
        rules = {
            "name": lambda v: validate_str(v, "name", max_len=100),
            "is_use": lambda v: validate_bool(v, "is_use"),
            "asset_id_parent": lambda v: validate_str(v, "asset_id_parent", max_len=100),
        }
        validate_update(filtered_values, rules)

        # 4. 回写过滤后的字段
        values.clear()
        values.update(filtered_values)

    # ==========================================================
    # 业务 repository
    # ==========================================================
    def select_tree(
            self,
            root_path: str,
            db: Session,
    ) -> list[Asset]:
        """
        查询整棵资产树
        :param root_path: 根资产路径
        :param db: 数据库会话
        :return: 查询到的资产列表
        """
        return self.select(
            db=db,
            filters={
                "asset_path__startswith": f"{root_path}/"
            },
            order_by=[
                "-asset_path"
            ],
        )

    @staticmethod
    def update_descendants_is_use(
            asset_path: str,
            is_use: bool,
            db: Session,
    ) -> None:
        """
        修改所有子资产的 is_use
        :param asset_path: 要修改的资产路径
        :param is_use: 新的 is_use 状态
        :param db: 数据库会话
        :return:
        """
        # 1. asset_path 校验
        if not asset_path:
            return

        # 2. 批量更新所有子资产（不包含自身）
        stmt = (
            update(Asset)
            .where(
                Asset.asset_path.like(f"{asset_path}/%")
            )
            .values(
                is_use=is_use
            )
        )
        db.execute(stmt)

    @staticmethod
    def update_ancestors_is_use(
            asset_path: str,
            is_use: bool,
            db: Session,
    ) -> None:
        """
        修改所有父资产的 is_use
        :param asset_path: 要修改的资产路径
        :param is_use: 新的 is_use 状态
        :param db: 数据库会话
        :return:
        """
        # 1. asset_path 校验
        if not asset_path:
            return

        # 2. 解析所有祖先 ID （不包含自身）
        ancestor_ids = ( asset_path.split("/")[:-1] )
        if not ancestor_ids:
            return

        # 3. 批量更新所有父资产
        stmt = (
            update(Asset)
            .where(
                Asset.asset_id.in_( ancestor_ids )
            )
            .values(
                is_use=is_use
            )
        )
        db.execute(stmt)



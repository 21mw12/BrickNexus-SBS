"""Permission-aware dashboard aggregation."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.asset.repository.models.Asset import Asset
from app.domain.asset.repository.models.AssetSensor import AssetSensor
from app.domain.asset.repository.models.AssetTerminal import AssetTerminal
from app.domain.channel.repository.models.Control import Control
from app.domain.channel.repository.models.Request import Request
from app.domain.rule.repository.models.Rule import Rule
from app.domain.user.repository.models.User import User


class DashboardService:
    """Build the single overview payload consumed by the dashboard page."""

    ASSET_TYPES = ("building", "floor", "room", "terminal", "sensor")

    PAGES = (
        {
            "key": "dashboard",
            "item": "看板",
            "description": "集中展示系统功能入口、业务规模以及当前用户可见的资产运行概况。",
            "usage": "登录后进入看板即可查看系统统计，并根据页面列表进入有权限访问的功能。",
        },
        {
            "key": "floorPlan",
            "item": "楼层平面图配置",
            "description": "维护楼层平面图以及房间在平面图中的位置标记。",
            "usage": "选择楼层后上传平面图，并在图片上配置该楼层的房间区域。",
        },
        {
            "key": "asset",
            "item": "资产中心",
            "description": "以建筑、楼层、房间、终端和传感器组织楼宇资产，并维护传感器型号与测点。",
            "usage": "进入资产中心查看授权资产，并根据实例权限进行新增、编辑、删除或设备操作。",
        },
        {
            "key": "asset:tree",
            "item": "资产树",
            "description": "按照建筑层级浏览当前用户有权查看的资产结构。",
            "usage": "通过树形结构逐级展开建筑、楼层、房间、终端和传感器。",
        },
        {
            "key": "asset:table",
            "item": "资产表",
            "description": "以表格方式筛选和查看当前用户有权访问的资产。",
            "usage": "使用资产类型、名称等条件筛选资产，并进入资产详情。",
        },
        {
            "key": "asset:model",
            "item": "传感器型号管理",
            "description": "维护传感器型号、全局测点定义以及型号与测点的绑定关系。",
            "usage": "先维护全局测点，再为传感器型号配置支持的测点。",
        },
        {
            "key": "data",
            "item": "数据监测",
            "description": "查看有权限终端的实时状态、测点数据和历史变化趋势。",
            "usage": "根据需要进入实时数据或历史数据页面查看测点数据。",
        },
        {
            "key": "data:realtime",
            "item": "实时数据",
            "description": "实时查看授权终端及其传感器测点的最新状态与测量值。",
            "usage": "选择有权查看的终端并订阅实时数据更新。",
        },
        {
            "key": "data:history",
            "item": "历史数据",
            "description": "按测点和时间范围查询历史测量数据。",
            "usage": "选择有权查看的测点和查询时间范围后生成历史数据结果。",
        },
        {
            "key": "channel",
            "item": "采控通道配置",
            "description": "通过 MQTT 或 HTTP 通道采集设备数据，并使用已配置的 Control 控制终端或传感器。",
            "usage": "先配置通信通道，再建立数据请求或控制配置。",
        },
        {
            "key": "channel:management",
            "item": "通道管理",
            "description": "集中维护 MQTT Broker 和 HTTP 服务的公共连接参数。",
            "usage": "创建 MQTT 或 HTTP 通道，验证参数后供请求和控制配置复用。",
        },
        {
            "key": "channel:requests",
            "item": "请求管理",
            "description": "配置 MQTT 或 HTTP 数据采集请求，并管理请求运行状态。",
            "usage": "选择已有通道，配置 Topic 或 HTTP 请求参数，测试后启用采集。",
        },
        {
            "key": "channel:controls",
            "item": "控制管理",
            "description": "配置绑定终端或传感器的 MQTT、HTTP 控制指令。",
            "usage": "选择被控资产和通道，保存控制参数并在启用后执行控制。",
        },
        {
            "key": "rule",
            "item": "规则管理",
            "description": "使用阈值、逻辑组合和历史差值判断异常，并执行日志、邮件或设备控制动作。",
            "usage": "创建并校验规则后将其启用，通过规则事件和行动任务检查触发证据与执行结果。",
        },
        {
            "key": "user",
            "item": "用户管理",
            "description": "管理系统账号、角色、页面权限和资产权限。",
            "usage": "进入账号管理或角色管理，为用户配置可访问页面及资产权限。",
        },
        {
            "key": "user:accounts",
            "item": "账号管理",
            "description": "维护用户账号及其角色和个人资产权限。",
            "usage": "新增或编辑账号，并为账号选择角色和补充个人资产权限。",
        },
        {
            "key": "user:roles",
            "item": "角色管理",
            "description": "维护角色及角色统一拥有的页面权限和资产权限。",
            "usage": "创建角色后配置页面权限、资产类型权限和资产实例权限。",
        },
        {
            "key": "logs",
            "item": "日志管理",
            "description": "集中查看规则操作和规则动作产生的业务日志，辅助追踪系统行为与异常。",
            "usage": "使用日志类型、等级、操作人、关键字和时间范围筛选需要检查的业务记录。",
        },
    )

    @classmethod
    def get_overview(
        cls,
        db: Session,
        permitted_page_codes: set[str],
        viewable_asset_ids: set[str] | None = None,
    ) -> dict:
        return {
            "page": [
                dict(definition)
                for definition in cls.PAGES
                if definition["key"] in permitted_page_codes
            ],
            "statistics": {
                "user_count": cls._count(db, User),
                "request_count": cls._count(db, Request),
                "control_count": cls._count(db, Control),
                "rule_count": cls._count(db, Rule),
                **cls._asset_counts(db, viewable_asset_ids),
            },
        }

    @staticmethod
    def _count(db: Session, model) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    @classmethod
    def _asset_counts(
        cls,
        db: Session,
        viewable_asset_ids: set[str] | None,
    ) -> dict[str, dict[str, int]]:
        result = {
            asset_type: {"enabled_total": 0}
            for asset_type in cls.ASSET_TYPES
        }
        result["terminal"]["online_count"] = 0
        result["sensor"]["online_count"] = 0

        # None means root and therefore no asset scope restriction.  An empty set
        # means an authenticated non-root user with no viewable assets.
        if viewable_asset_ids is not None and not viewable_asset_ids:
            return result

        conditions = [Asset.is_use.is_(True)]
        if viewable_asset_ids is not None:
            conditions.append(Asset.asset_id.in_(viewable_asset_ids))

        rows = db.execute(
            select(Asset.asset_type, func.count(Asset.asset_id))
            .where(*conditions)
            .group_by(Asset.asset_type)
        ).all()
        for asset_type, count in rows:
            if asset_type in result:
                result[asset_type]["enabled_total"] = int(count)

        result["terminal"]["online_count"] = cls._online_count(
            db, AssetTerminal, "terminal", viewable_asset_ids
        )
        result["sensor"]["online_count"] = cls._online_count(
            db, AssetSensor, "sensor", viewable_asset_ids
        )
        return result

    @staticmethod
    def _online_count(
        db: Session,
        detail_model,
        asset_type: str,
        viewable_asset_ids: set[str] | None,
    ) -> int:
        if viewable_asset_ids is not None and not viewable_asset_ids:
            return 0
        conditions = [
            Asset.asset_type == asset_type,
            Asset.is_use.is_(True),
            detail_model.is_online.is_(True),
        ]
        if viewable_asset_ids is not None:
            conditions.append(Asset.asset_id.in_(viewable_asset_ids))
        statement = (
            select(func.count(Asset.asset_id))
            .select_from(Asset)
            .join(detail_model, detail_model.asset_id == Asset.asset_id)
            .where(*conditions)
        )
        return int(db.scalar(statement) or 0)

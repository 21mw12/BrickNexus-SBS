from __future__ import annotations

from app.domain.rule.schema.RuleSchema import ACTION_TYPES, COMPARISONS, LOGICAL, OPERANDS


class RuleOptionsService:
    """规则编辑器使用的静态能力契约，不包含任何资产实例数据。"""

    VERSION = "1.1"

    PLACEHOLDERS = [
        {"value": "{{$.point_name}}", "label": "测点名称"},
        {"value": "{{$.time}}", "label": "测量时间（YYYY-MM-DD HH:MM:SS）"},
        {"value": "{{$.value}}", "label": "测点值"},
    ]

    COMPARISON_OPTIONS = [
        {"value": "GreaterThan", "label": "大于", "symbol": ">"},
        {"value": "GreaterThanOrEqual", "label": "大于等于", "symbol": ">="},
        {"value": "LessThan", "label": "小于", "symbol": "<"},
        {"value": "LessThanOrEqual", "label": "小于等于", "symbol": "<="},
        {"value": "Equal", "label": "等于", "symbol": "=="},
        {"value": "NotEqual", "label": "不等于", "symbol": "!="},
    ]

    LOGICAL_OPTIONS = [
        {"value": "AND", "label": "并且", "min_children": 2},
        {"value": "OR", "label": "或者", "min_children": 2},
        {"value": "NOT", "label": "取反", "min_children": 1, "max_children": 1},
    ]

    OPERAND_OPTIONS = [
        {
            "value": "PointValue", "label": "当前测点值",
            "fields": [{"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True}],
        },
        {
            "value": "ConstantValue", "label": "常量",
            "fields": [{"name": "value", "label": "数值", "type": "number", "required": True}],
        },
        {
            "value": "PreviousDifference", "label": "与上一样本的差值",
            "fields": [{"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True}],
        },
        {
            "value": "AbsolutePreviousDifference", "label": "与上一样本的绝对差值",
            "fields": [{"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True}],
        },
        {
            "value": "SampleLagDifference", "label": "样本间隔差值",
            "fields": [
                {"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True},
                {"name": "samples", "label": "间隔样本数", "type": "integer", "required": True, "minimum": 1},
            ],
        },
        {
            "value": "TimeLagDifference", "label": "时间间隔差值",
            "fields": [
                {"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True},
                {"name": "duration_seconds", "label": "时间间隔（秒）", "type": "number", "required": True, "exclusive_minimum": 0},
                {"name": "tolerance_seconds", "label": "允许误差（秒）", "type": "number", "required": True, "minimum": 0},
            ],
        },
        {
            "value": "WindowAverageDifference", "label": "窗口均值差值",
            "fields": [
                {"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True},
                {"name": "window_seconds", "label": "时间窗口（秒）", "type": "number", "required": True, "exclusive_minimum": 0},
            ],
        },
        {
            "value": "WindowRange", "label": "窗口极差",
            "fields": [
                {"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True},
                {"name": "window_seconds", "label": "时间窗口（秒）", "type": "number", "required": True, "exclusive_minimum": 0},
            ],
        },
        {
            "value": "RateOfChange", "label": "变化率",
            "fields": [
                {"name": "selector_id", "label": "监控选择器", "type": "selector_ref", "required": True},
                {"name": "time_unit_seconds", "label": "变化率时间单位（秒）", "type": "number", "required": True, "exclusive_minimum": 0},
            ],
            "reference_variants": [
                {
                    "value": "samples", "label": "按样本",
                    "fields": [{"name": "samples", "label": "间隔样本数", "type": "integer", "required": True, "minimum": 1}],
                },
                {
                    "value": "time", "label": "按时间",
                    "fields": [
                        {"name": "duration_seconds", "label": "时间间隔（秒）", "type": "number", "required": True, "exclusive_minimum": 0},
                        {"name": "tolerance_seconds", "label": "允许误差（秒）", "type": "number", "required": True, "minimum": 0},
                    ],
                },
            ],
        },
    ]

    @classmethod
    def get_options(cls) -> dict:
        return {
            "schema_version": cls.VERSION,
            "rule_fields": [
                {"name": "rule_name", "label": "规则名称", "type": "text", "required": True, "max_length": 100},
                {"name": "description", "label": "规则描述", "type": "textarea", "required": False, "default": "", "max_length": 1000},
            ],
            "selector_types": [
                {
                    "value": "PointIdSelector", "label": "指定实例测点",
                    "fields": [
                        {"name": "selector_id", "label": "选择器标识", "type": "text", "required": True, "default": "monitor", "max_length": 100},
                        {"name": "point_id", "label": "监控测点", "type": "asset_sensor_point", "required": True},
                    ],
                    "asset_source": {
                        "tree_endpoint": "GET /assets/tree",
                        "detail_endpoint": "GET /assets/find/{asset_id}",
                        "items_field": "sensor_points",
                        "value_field": "point_id",
                    },
                },
                {
                    "value": "SemanticPointSelector", "label": "按位置和测点定义匹配",
                    "fields": [
                        {"name": "selector_id", "label": "选择器标识", "type": "text", "required": True, "default": "monitor", "max_length": 100},
                        {"name": "point_definition_id", "label": "全局测点定义", "type": "point_definition", "required": True},
                        {"name": "location_id", "label": "所在位置", "type": "asset_location", "required": True},
                        {"name": "location_type", "label": "位置类型", "type": "select", "required": True,
                         "options": [
                             {"value": "building", "label": "建筑"},
                             {"value": "floor", "label": "楼层"},
                             {"value": "room", "label": "房间"},
                         ]},
                    ],
                    "point_definition_source": {
                        "list_endpoint": "GET /points/list?page={page}&limit={limit}",
                        "items_field": "items",
                        "value_field": "point_id",
                        "label_field": "point_name",
                    },
                    "location_source": {
                        "tree_endpoint": "GET /assets/tree",
                        "value_field": "asset_id",
                        "allowed_types": ["building", "floor", "room"],
                        "include_descendants": True,
                    },
                },
            ],
            "condition_node_types": [
                {"value": "Comparison", "label": "比较条件"},
                {"value": "Logical", "label": "逻辑条件"},
            ],
            "comparison_operators": cls.COMPARISON_OPTIONS,
            "logical_operators": cls.LOGICAL_OPTIONS,
            "operand_types": cls.OPERAND_OPTIONS,
            "trigger_policy": {"fields": [
                {"name": "trigger_count", "label": "触发连续次数", "type": "integer", "default": 1, "minimum": 1},
                {"name": "trigger_duration_seconds", "label": "触发持续时间（秒）", "type": "number", "default": 0, "minimum": 0},
                {"name": "recovery_count", "label": "恢复连续次数", "type": "integer", "default": 1, "minimum": 1},
                {"name": "recovery_duration_seconds", "label": "恢复持续时间（秒）", "type": "number", "default": 0, "minimum": 0},
                {"name": "repeat_policy", "label": "重复策略", "type": "select", "default": "OncePerIncident"},
                {"name": "repeat_interval_seconds", "label": "重复间隔（秒）", "type": "number", "required_when": {"repeat_policy": "Periodic"}, "exclusive_minimum": 0},
                {"name": "cooldown_seconds", "label": "冷却时间（秒）", "type": "number", "default": 0, "minimum": 0},
                {"name": "merge_window_seconds", "label": "合并窗口（秒）", "type": "number", "default": 0, "minimum": 0},
            ]},
            "repeat_policies": [
                {"value": "OncePerIncident", "label": "每次异常只触发一次"},
                {"value": "NewMatch", "label": "出现新匹配时触发"},
                {"value": "Periodic", "label": "异常期间周期触发", "required_fields": ["repeat_interval_seconds"]},
            ],
            "action_types": [
                {
                    "value": "LogAction", "label": "记录日志",
                    "generated_fields": ["action_id"],
                    "fields": [
                        {"name": "level", "label": "日志等级", "type": "select", "required": True,
                         "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                        {"name": "content", "label": "日志内容模板", "type": "textarea",
                         "required": True, "max_length": 10000},
                    ],
                    "placeholders": cls.PLACEHOLDERS,
                },
                {
                    "value": "EmailAction", "label": "发送邮件",
                    "generated_fields": ["action_id"],
                    "fields": [
                        {"name": "recipients", "label": "收件人", "type": "email_list",
                         "required": True, "min_items": 1, "max_items": 50},
                        {"name": "subject", "label": "邮件标题", "type": "text",
                         "required": True, "max_length": 200, "supports_placeholders": False},
                        {"name": "content", "label": "邮件正文模板", "type": "textarea",
                         "required": True, "max_length": 10000},
                    ],
                    "placeholders": cls.PLACEHOLDERS,
                },
                {
                    "value": "SensorControlAction", "label": "控制传感器",
                    "generated_fields": ["action_id"],
                    "fields": [
                        {"name": "control_id", "label": "控制配置", "type": "control_ref",
                         "required": True, "max_length": 100},
                    ],
                    "control_source": {
                        "list_endpoint": "POST /control/list?page={page}&limit={limit}",
                        "items_field": "items", "value_field": "control_id", "label_field": "name",
                    },
                },
            ],
        }

    @classmethod
    def assert_matches_schema(cls) -> None:
        assert {item["value"] for item in cls.COMPARISON_OPTIONS} == COMPARISONS
        assert {item["value"] for item in cls.LOGICAL_OPTIONS} == LOGICAL
        assert {item["value"] for item in cls.OPERAND_OPTIONS} == OPERANDS
        assert {item["value"] for item in cls.get_options()["action_types"]} == ACTION_TYPES

"""BrickNexus v2.0 formal initial schema.

This file is the immutable first production baseline. Future schema changes
must be added as new Alembic revisions instead of changing this snapshot.

A database created by the application before Alembic was enabled is adopted
only when its public table and column layout exactly matches this baseline.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260817_0001"
down_revision = None
branch_labels = None
depends_on = None


_EXPECTED_COLUMNS = {
    'assets': {'asset_id', 'asset_id_parent', 'asset_path', 'asset_type', 'name', 'floor_count', 'room_count', 'terminal_count', 'sensor_count', 'is_use'},
    'assets_building': {'asset_id', 'number', 'address'},
    'assets_floor': {'asset_id', 'level'},
    'assets_room': {'asset_id', 'number', 'room_purpose', 'max_current', 'manager_name'},
    'assets_sensor': {'asset_id', 'model_id', 'is_online', 'last_receive_time'},
    'assets_terminal': {'asset_id', 'request_id', 'number', 'model', 'location', 'iot_number', 'iot_activate_human', 'is_online', 'last_receive_time'},
    'channel_http': {'channel_http_id', 'base_url', 'default_headers', 'default_timeout', 'created_at'},
    'channel_mqtt': {'channel_mqtt_id', 'broker_host', 'broker_port', 'client_id', 'username', 'password', 'qos', 'connect_timeout', 'data_timeout', 'created_at'},
    'log': {'id', 'type', 'level', 'operator', 'content', 'time'},
    'measurement': {'point_id', 'time', 'value'},
    'model': {'model_id', 'sensor_type', 'model_name', 'remark'},
    'page': {'page_id', 'page_id_parent', 'name', 'path_code'},
    'point': {'point_id', 'point_name', 'point_unit', 'point_description'},
    'request': {'request_id', 'name', 'type', 'channel_id', 'interval_seconds', 'time_json_path', 'time_format', 'status', 'created_at', 'mqtt_topic', 'http_method', 'http_path', 'http_header', 'http_params', 'http_body'},
    'role': {'role_id', 'name', 'describe'},
    'role_asset': {'permission_id', 'role_id', 'asset_id', 'asset_type', 'perm_create', 'perm_retrieve', 'perm_update', 'perm_delete', 'perm_operate'},
    'role_page': {'role_id', 'page_id'},
    'rule': {'rule_id', 'rule_name', 'rule_file_name', 'status', 'error', 'created_at'},
    'user': {'user_id', 'role_id', 'account', 'nickname', 'password'},
    'user_asset': {'user_asset_id', 'user_id', 'asset_id', 'perm_retrieve', 'perm_update', 'perm_delete', 'perm_operate'},
    'control': {'control_id', 'name', 'type', 'channel_id', 'asset_type', 'asset_id', 'status', 'created_at', 'mqtt_topic', 'mqtt_retained', 'mqtt_payload', 'http_method', 'http_path', 'http_header', 'http_params', 'http_body'},
    'floor_plan': {'floor_id', 'image_name', 'image_width', 'image_height', 'image_type'},
    'floor_room_region': {'room_id', 'x', 'y', 'width', 'height'},
    'model_point': {'model_id', 'point_id'},
    'rule_event': {'event_id', 'rule_id', 'event_type', 'evidence', 'event_time'},
    'action_task': {'task_id', 'rule_id', 'event_id', 'action_id', 'action_type', 'action_params', 'is_executed', 'status', 'error', 'created_at', 'completed_at'},
    'sensor_point': {'point_id', 'sensor_id', 'source_model_id', 'source_point_id', 'point_name', 'point_unit', 'json_path'},
}


def _adopt_existing_current_schema(bind) -> bool:
    inspector = sa.inspect(bind)
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    if not actual_tables:
        return False

    expected_tables = set(_EXPECTED_COLUMNS)
    if actual_tables != expected_tables:
        missing = sorted(expected_tables - actual_tables)
        extra = sorted(actual_tables - expected_tables)
        raise RuntimeError(
            "existing database does not match the formal baseline; "
            f"missing tables={missing}, extra tables={extra}"
        )

    mismatches = []
    for table_name, expected_columns in _EXPECTED_COLUMNS.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        if actual_columns != expected_columns:
            mismatches.append(
                f"{table_name}(missing={sorted(expected_columns - actual_columns)}, "
                f"extra={sorted(actual_columns - expected_columns)})"
            )
    if mismatches:
        raise RuntimeError(
            "existing database columns do not match the formal baseline: "
            + "; ".join(mismatches)
        )
    return True


def upgrade() -> None:
    if _adopt_existing_current_schema(op.get_bind()):
        return

    op.create_table('assets',
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('asset_id_parent', sa.String(length=100), nullable=True, comment='父资产ID'),
    sa.Column('asset_path', sa.String(length=500), nullable=True, comment='资产路径'),
    sa.Column('asset_type', sa.String(length=20), nullable=False, comment='资产类型'),
    sa.Column('name', sa.String(length=100), nullable=False, comment='资产名称'),
    sa.Column('floor_count', sa.Integer(), nullable=False, comment='楼层数量'),
    sa.Column('room_count', sa.Integer(), nullable=False, comment='房间数量'),
    sa.Column('terminal_count', sa.Integer(), nullable=False, comment='终端数量'),
    sa.Column('sensor_count', sa.Integer(), nullable=False, comment='传感器数量'),
    sa.Column('is_use', sa.Boolean(), nullable=False, comment='是否使用'),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('assets_building',
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('number', sa.String(length=50), nullable=True, comment='建筑编号'),
    sa.Column('address', sa.String(length=200), nullable=True, comment='地址'),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('assets_floor',
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('level', sa.String(length=20), nullable=True, comment='楼层等级'),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('assets_room',
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('number', sa.String(length=20), nullable=True, comment='房间编号'),
    sa.Column('room_purpose', sa.String(length=100), nullable=True, comment='房间用途'),
    sa.Column('max_current', sa.String(length=20), nullable=True, comment='最大电流'),
    sa.Column('manager_name', sa.String(length=50), nullable=True, comment='管理员姓名'),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('assets_sensor',
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('model_id', sa.String(length=100), nullable=True, comment='传感器型号ID'),
    sa.Column('is_online', sa.Boolean(), nullable=False, comment='是否在线'),
    sa.Column('last_receive_time', sa.DateTime(timezone=True), nullable=True, comment='最后接收数据时间'),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('assets_terminal',
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('request_id', sa.String(length=100), nullable=True, comment='数据请求ID'),
    sa.Column('number', sa.String(length=50), nullable=True, comment='终端编号'),
    sa.Column('model', sa.String(length=50), nullable=True, comment='终端类型'),
    sa.Column('location', sa.String(length=100), nullable=True, comment='安装位置'),
    sa.Column('iot_number', sa.String(length=50), nullable=True, comment='物联网卡号'),
    sa.Column('iot_activate_human', sa.String(length=50), nullable=True, comment='物联网卡激活人'),
    sa.Column('is_online', sa.Boolean(), nullable=False, comment='是否在线'),
    sa.Column('last_receive_time', sa.DateTime(timezone=True), nullable=True, comment='最后接收数据时间'),
    sa.PrimaryKeyConstraint('asset_id')
    )
    op.create_table('channel_http',
    sa.Column('channel_http_id', sa.String(length=100), nullable=False),
    sa.Column('base_url', sa.String(length=200), nullable=False),
    sa.Column('default_headers', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
    sa.Column('default_timeout', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('default_timeout > 0', name='ck_channel_http_timeout'),
    sa.PrimaryKeyConstraint('channel_http_id')
    )
    op.create_index('ix_channel_http_base_url', 'channel_http', ['base_url'], unique=False)
    op.create_table('channel_mqtt',
    sa.Column('channel_mqtt_id', sa.String(length=100), nullable=False),
    sa.Column('broker_host', sa.String(length=30), nullable=False),
    sa.Column('broker_port', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.String(length=100), nullable=False),
    sa.Column('username', sa.String(length=20), nullable=True),
    sa.Column('password', sa.Text(), nullable=True),
    sa.Column('qos', sa.Integer(), nullable=False),
    sa.Column('connect_timeout', sa.Integer(), nullable=False),
    sa.Column('data_timeout', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('broker_port BETWEEN 1 AND 65535', name='ck_channel_mqtt_port'),
    sa.CheckConstraint('connect_timeout > 0', name='ck_channel_mqtt_connect_timeout'),
    sa.CheckConstraint('data_timeout > 0', name='ck_channel_mqtt_data_timeout'),
    sa.CheckConstraint('qos IN (0, 1, 2)', name='ck_channel_mqtt_qos'),
    sa.PrimaryKeyConstraint('channel_mqtt_id'),
    sa.UniqueConstraint('client_id', name='uq_channel_mqtt_client_id')
    )
    op.create_index('ix_channel_mqtt_broker', 'channel_mqtt', ['broker_host', 'broker_port'], unique=False)
    op.create_table('log',
    sa.Column('id', sa.String(length=100), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('level', sa.String(length=10), nullable=False),
    sa.Column('operator', sa.String(length=30), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('time', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_log_level', 'log', ['level'], unique=False)
    op.create_index('ix_log_operator', 'log', ['operator'], unique=False)
    op.create_index('ix_log_time', 'log', ['time'], unique=False)
    op.create_index('ix_log_type', 'log', ['type'], unique=False)
    op.create_table('measurement',
    sa.Column('point_id', sa.String(length=100), nullable=False, comment='传感器测点ID'),
    sa.Column('time', sa.DateTime(timezone=True), nullable=False, comment='测量时间'),
    sa.Column('value', sa.Float(), nullable=False, comment='测量值'),
    sa.PrimaryKeyConstraint('point_id', 'time')
    )
    op.create_index('ix_measurement_time', 'measurement', ['time'], unique=False)
    op.create_table('model',
    sa.Column('model_id', sa.String(length=100), nullable=False, comment='型号ID'),
    sa.Column('sensor_type', sa.String(length=50), nullable=True, comment='传感器类型'),
    sa.Column('model_name', sa.String(length=50), nullable=True, comment='传感器型号'),
    sa.Column('remark', sa.String(length=100), nullable=True, comment='备注'),
    sa.PrimaryKeyConstraint('model_id')
    )
    op.create_table('page',
    sa.Column('page_id', sa.String(length=100), nullable=False, comment='页面id'),
    sa.Column('page_id_parent', sa.String(length=100), nullable=True, comment='父页面id'),
    sa.Column('name', sa.String(length=50), nullable=False, comment='页面名称'),
    sa.Column('path_code', sa.String(length=50), nullable=False, comment='页面编码'),
    sa.PrimaryKeyConstraint('page_id')
    )
    op.create_table('point',
    sa.Column('point_id', sa.String(length=100), nullable=False, comment='测点ID'),
    sa.Column('point_name', sa.String(length=20), nullable=False, comment='测点名称'),
    sa.Column('point_unit', sa.String(length=10), nullable=False, comment='测点单位'),
    sa.Column('point_description', sa.String(length=200), nullable=True, comment='测点含义说明'),
    sa.PrimaryKeyConstraint('point_id'),
    sa.UniqueConstraint('point_name', 'point_unit', name='uq_point_name_unit')
    )
    op.create_table('request',
    sa.Column('request_id', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=20), nullable=False),
    sa.Column('type', sa.String(length=10), nullable=False),
    sa.Column('channel_id', sa.String(length=100), nullable=False),
    sa.Column('interval_seconds', sa.Integer(), nullable=False),
    sa.Column('time_json_path', sa.String(length=200), nullable=True),
    sa.Column('time_format', sa.String(length=50), nullable=True),
    sa.Column('status', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('mqtt_topic', sa.String(length=30), nullable=True),
    sa.Column('http_method', sa.String(length=10), nullable=True),
    sa.Column('http_path', sa.String(length=100), nullable=True),
    sa.Column('http_header', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(sa.JSON(none_as_null=True), 'sqlite'), nullable=True),
    sa.Column('http_params', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(sa.JSON(none_as_null=True), 'sqlite'), nullable=True),
    sa.Column('http_body', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(sa.JSON(none_as_null=True), 'sqlite'), nullable=True),
    sa.CheckConstraint("(type = 'mqtt' AND mqtt_topic IS NOT NULL AND http_method IS NULL AND http_path IS NULL AND http_header IS NULL AND http_params IS NULL AND http_body IS NULL) OR (type = 'http' AND mqtt_topic IS NULL AND http_method IN ('GET', 'POST') AND http_path IS NOT NULL)", name='ck_request_protocol_fields'),
    sa.CheckConstraint("type IN ('mqtt', 'http')", name='ck_request_type'),
    sa.CheckConstraint('interval_seconds > 0', name='ck_request_interval_positive'),
    sa.PrimaryKeyConstraint('request_id'),
    sa.UniqueConstraint('name', name='uq_request_name')
    )
    op.create_index('ix_request_channel_id', 'request', ['channel_id'], unique=False)
    op.create_index('ix_request_type_status', 'request', ['type', 'status'], unique=False)
    op.create_table('role',
    sa.Column('role_id', sa.String(length=100), nullable=False, comment='角色ID'),
    sa.Column('name', sa.String(length=30), nullable=False, comment='角色名称'),
    sa.Column('describe', sa.String(length=150), nullable=False, comment='角色描述'),
    sa.PrimaryKeyConstraint('role_id')
    )
    op.create_table('role_asset',
    sa.Column('permission_id', sa.String(length=100), nullable=False, comment='权限id'),
    sa.Column('role_id', sa.String(length=100), nullable=False, comment='角色id'),
    sa.Column('asset_id', sa.String(length=100), nullable=True, comment='资产id（实例权限时使用）'),
    sa.Column('asset_type', sa.String(length=20), nullable=True, comment='资产类型（类型权限时使用）'),
    sa.Column('perm_create', sa.Boolean(), nullable=False, comment='增加权限 C'),
    sa.Column('perm_retrieve', sa.Boolean(), nullable=False, comment='查看权限 R'),
    sa.Column('perm_update', sa.Boolean(), nullable=False, comment='修改权限 U'),
    sa.Column('perm_delete', sa.Boolean(), nullable=False, comment='删除权限 D'),
    sa.Column('perm_operate', sa.Boolean(), nullable=False, comment='操作权限 O'),
    sa.PrimaryKeyConstraint('permission_id')
    )
    op.create_table('role_page',
    sa.Column('role_id', sa.String(length=100), nullable=False, comment='角色id'),
    sa.Column('page_id', sa.String(length=100), nullable=False, comment='页面id'),
    sa.PrimaryKeyConstraint('role_id', 'page_id')
    )
    op.create_table('rule',
    sa.Column('rule_id', sa.String(length=100), nullable=False),
    sa.Column('rule_name', sa.String(length=100), nullable=False),
    sa.Column('rule_file_name', sa.String(length=100), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('rule_id'),
    sa.UniqueConstraint('rule_file_name')
    )
    op.create_index('ix_rule_status', 'rule', ['status'], unique=False)
    op.create_table('user',
    sa.Column('user_id', sa.String(length=100), nullable=False, comment='用户ID'),
    sa.Column('role_id', sa.String(length=100), nullable=False, comment='所属角色ID'),
    sa.Column('account', sa.String(length=30), nullable=False, comment='账号'),
    sa.Column('nickname', sa.String(length=30), nullable=False, comment='昵称'),
    sa.Column('password', sa.String(length=130), nullable=False, comment='密码'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('user_asset',
    sa.Column('user_asset_id', sa.String(length=100), nullable=False, comment='用户资产权限ID'),
    sa.Column('user_id', sa.String(length=100), nullable=False, comment='用户ID'),
    sa.Column('asset_id', sa.String(length=100), nullable=False, comment='资产ID'),
    sa.Column('perm_retrieve', sa.Boolean(), nullable=False, comment='查看权限 R'),
    sa.Column('perm_update', sa.Boolean(), nullable=False, comment='修改权限 U'),
    sa.Column('perm_delete', sa.Boolean(), nullable=False, comment='删除权限 D'),
    sa.Column('perm_operate', sa.Boolean(), nullable=False, comment='操作权限 O'),
    sa.PrimaryKeyConstraint('user_asset_id')
    )
    op.create_table('control',
    sa.Column('control_id', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=30), nullable=False),
    sa.Column('type', sa.String(length=10), nullable=False),
    sa.Column('channel_id', sa.String(length=100), nullable=False),
    sa.Column('asset_type', sa.String(length=10), nullable=False),
    sa.Column('asset_id', sa.String(length=100), nullable=False),
    sa.Column('status', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('mqtt_topic', sa.String(length=30), nullable=True),
    sa.Column('mqtt_retained', sa.Boolean(), nullable=True),
    sa.Column('mqtt_payload', sa.Text(), nullable=True),
    sa.Column('http_method', sa.String(length=10), nullable=True),
    sa.Column('http_path', sa.String(length=100), nullable=True),
    sa.Column('http_header', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(sa.JSON(none_as_null=True), 'sqlite'), nullable=True),
    sa.Column('http_params', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(sa.JSON(none_as_null=True), 'sqlite'), nullable=True),
    sa.Column('http_body', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(sa.JSON(none_as_null=True), 'sqlite'), nullable=True),
    sa.CheckConstraint("(type = 'mqtt' AND mqtt_topic IS NOT NULL AND mqtt_payload IS NOT NULL AND http_method IS NULL AND http_path IS NULL AND http_header IS NULL AND http_params IS NULL AND http_body IS NULL) OR (type = 'http' AND mqtt_topic IS NULL AND mqtt_retained IS NULL AND mqtt_payload IS NULL AND http_method IN ('GET', 'POST') AND http_path IS NOT NULL)", name='ck_control_protocol_fields'),
    sa.CheckConstraint("asset_type IN ('terminal', 'sensor')", name='ck_control_asset_type'),
    sa.CheckConstraint("type IN ('mqtt', 'http')", name='ck_control_type'),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.asset_id'], name='fk_control_asset_id_assets', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('control_id'),
    sa.UniqueConstraint('name', name='uq_control_name')
    )
    op.create_index('ix_control_asset_type_asset_id', 'control', ['asset_type', 'asset_id'], unique=False)
    op.create_index('ix_control_channel_id', 'control', ['channel_id'], unique=False)
    op.create_index('ix_control_type_status', 'control', ['type', 'status'], unique=False)
    op.create_table('floor_plan',
    sa.Column('floor_id', sa.String(length=100), nullable=False, comment='楼层ID'),
    sa.Column('image_name', sa.String(length=100), nullable=False, comment='图片名称'),
    sa.Column('image_width', sa.Integer(), nullable=False, comment='原图宽度'),
    sa.Column('image_height', sa.Integer(), nullable=False, comment='原图高度'),
    sa.Column('image_type', sa.String(length=50), nullable=False, comment='图片MIME类型'),
    sa.CheckConstraint('image_height > 0', name='ck_floor_plan_image_height_positive'),
    sa.CheckConstraint('image_width > 0', name='ck_floor_plan_image_width_positive'),
    sa.ForeignKeyConstraint(['floor_id'], ['assets_floor.asset_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('floor_id')
    )
    op.create_table('floor_room_region',
    sa.Column('room_id', sa.String(length=100), nullable=False, comment='房间ID'),
    sa.Column('x', sa.Integer(), nullable=False, comment='左上角X像素坐标'),
    sa.Column('y', sa.Integer(), nullable=False, comment='左上角Y像素坐标'),
    sa.Column('width', sa.Integer(), nullable=False, comment='矩形宽度'),
    sa.Column('height', sa.Integer(), nullable=False, comment='矩形高度'),
    sa.CheckConstraint('height > 0', name='ck_floor_room_region_height_positive'),
    sa.CheckConstraint('width > 0', name='ck_floor_room_region_width_positive'),
    sa.CheckConstraint('x >= 0', name='ck_floor_room_region_x_non_negative'),
    sa.CheckConstraint('y >= 0', name='ck_floor_room_region_y_non_negative'),
    sa.ForeignKeyConstraint(['room_id'], ['assets_room.asset_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('room_id')
    )
    op.create_table('model_point',
    sa.Column('model_id', sa.String(length=100), nullable=False, comment='型号ID'),
    sa.Column('point_id', sa.String(length=100), nullable=False, comment='测点ID'),
    sa.ForeignKeyConstraint(['model_id'], ['model.model_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['point_id'], ['point.point_id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('model_id', 'point_id')
    )
    op.create_table('rule_event',
    sa.Column('event_id', sa.String(length=100), nullable=False),
    sa.Column('rule_id', sa.String(length=100), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('evidence', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['rule_id'], ['rule.rule_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_rule_event_rule_time', 'rule_event', ['rule_id', 'event_time'], unique=False)
    op.create_index('ix_rule_event_type', 'rule_event', ['event_type'], unique=False)
    op.create_table('action_task',
    sa.Column('task_id', sa.String(length=100), nullable=False),
    sa.Column('rule_id', sa.String(length=100), nullable=False),
    sa.Column('event_id', sa.String(length=100), nullable=False),
    sa.Column('action_id', sa.String(length=100), nullable=False),
    sa.Column('action_type', sa.String(length=20), nullable=False),
    sa.Column('action_params', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('is_executed', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['rule_event.event_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['rule_id'], ['rule.rule_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('task_id')
    )
    op.create_index('ix_action_task_rule_action', 'action_task', ['rule_id', 'action_id'], unique=False)
    op.create_index('ix_action_task_status_created', 'action_task', ['status', 'created_at'], unique=False)
    op.create_table('sensor_point',
    sa.Column('point_id', sa.String(length=100), nullable=False, comment='测点ID'),
    sa.Column('sensor_id', sa.String(length=100), nullable=False, comment='传感器资产ID'),
    sa.Column('source_model_id', sa.String(length=100), nullable=False, comment='来源型号ID'),
    sa.Column('source_point_id', sa.String(length=100), nullable=False, comment='来源测点ID'),
    sa.Column('point_name', sa.String(length=20), nullable=False, comment='测点名称快照'),
    sa.Column('point_unit', sa.String(length=10), nullable=False, comment='测点单位快照'),
    sa.Column('json_path', sa.String(length=200), nullable=True, comment='JSON数据提取路径'),
    sa.ForeignKeyConstraint(['source_model_id', 'source_point_id'], ['model_point.model_id', 'model_point.point_id'], name='fk_sensor_point_source_model_point', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('point_id')
    )
    op.create_index('ix_sensor_point_source_model_point', 'sensor_point', ['source_model_id', 'source_point_id'], unique=False)
    op.create_index('ix_sensor_point_source_point_id', 'sensor_point', ['source_point_id'], unique=False)


def downgrade() -> None:
    for table_name in (
        'sensor_point',
        'action_task',
        'rule_event',
        'model_point',
        'floor_room_region',
        'floor_plan',
        'control',
        'user_asset',
        'user',
        'rule',
        'role_page',
        'role_asset',
        'role',
        'request',
        'point',
        'page',
        'model',
        'measurement',
        'log',
        'channel_mqtt',
        'channel_http',
        'assets_terminal',
        'assets_sensor',
        'assets_room',
        'assets_floor',
        'assets_building',
        'assets',
    ):
        op.drop_table(table_name)

import unittest

from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.asset.repository.AssetRepository import AssetRepository
from app.domain.asset.repository.models import *
from app.domain.asset.schema.AssetQueryFilterSchema import SensorQuerySchema

from app.infra.DB.SQLConnection import sql_manager

from app.domain.asset.schema.AssetAddSchema import (
    AssetAddSchema,
    BuildingAddSchema,
    FloorAddSchema,
    RoomAddSchema,
    TerminalAddSchema,
    SensorAddSchema,
)
from app.domain.asset.schema.AssetUpdateSchema import (
    AssetUpdateSchema,
    BuildingUpdateSchema,
    FloorUpdateSchema,
    RoomUpdateSchema,
    TerminalUpdateSchema,
    SensorUpdateSchema,
)
from app.domain.asset.service.AssetService import AssetService


class AssetTests(unittest.TestCase):

    @staticmethod
    def _new_building_asset() -> AssetAddSchema:
        return BuildingAddSchema(
            asset_id_parent=None,
            asset_type="building",
            name=f"Building-{uuid_generator.random()}",
            is_use=False,
            number=f"B-",
            address="Addr-Building",
        )

    @staticmethod
    def _new_floor_asset(parent_id: str = None) -> AssetAddSchema:
        return FloorAddSchema(
            asset_id_parent=parent_id,
            asset_type="floor",
            name=f"Floor-{uuid_generator.random()}",
            is_use=False,
            level="L1",
        )

    @staticmethod
    def _new_room_asset(parent_id: str = None) -> AssetAddSchema:
        return RoomAddSchema(
            asset_id_parent=parent_id,
            asset_type="room",
            name=f"Room-{uuid_generator.random()}",
            is_use=False,
            number="R-01",
            room_purpose="Office",
            max_current="10A",
            manager_name="Manager",
        )

    @staticmethod
    def _new_terminal_asset(parent_id: str = None) -> AssetAddSchema:
        return TerminalAddSchema(
            asset_id_parent=parent_id,
            asset_type="terminal",
            name=f"Terminal-{uuid_generator.random()}",
            is_use=False,
            number="T-01",
            model="Model-A",
            location="Room-1",
            iot_number="IOT-001",
            iot_activate_human="Admin",
        )

    @staticmethod
    def _new_sensor_asset(parent_id: str = None) -> AssetAddSchema:
        return SensorAddSchema(
            asset_id_parent=parent_id,
            asset_type="sensor",
            name=f"Sensor-{uuid_generator.random()}",
            is_use=False,
            model_id="S-100",
        )

    @staticmethod
    def build_complex_tree(db) -> dict:
        """
        构建一个相对复杂的资产树，只生成结构，不做其他操作。

        结构：
            Building "测试楼宇A"
            ├── Floor "1层"
            │   ├── Room "101室"
            │   │   ├── Terminal "网关-01"
            │   │   │   ├── Sensor "温湿度传感器-01"
            │   │   │   └── Sensor "电流传感器-01"
            │   │   └── Terminal "网关-02"
            │   │       └── Sensor "光照传感器-01"
            │   └── Room "102室"
            │       └── Terminal "网关-03"
            │           ├── Sensor "温度传感器-02"
            │           └── Sensor "电压传感器-01"
            └── Floor "2层"
                └── Room "201室"
                    └── Terminal "网关-04"
                        └── Sensor "温湿度传感器-03"

        :param db: 数据库会话
        :return: 包含所有资产 ID 的嵌套字典
        """
        asset_svc = AssetService()

        # ==========================================
        # 1. 创建楼宇
        # ==========================================
        building = asset_svc.save_new_asset(
            BuildingAddSchema(
                asset_type="building",
                name="测试楼宇A",
                is_use=True,
                number="B-001",
                address="测试地址",
            ),
            db=db,
        )

        # ==========================================
        # 2. 创建 1层
        # ==========================================
        floor_1 = asset_svc.save_new_asset(
            FloorAddSchema(
                asset_id_parent=building["asset_id"],
                asset_type="floor",
                name="1层",
                is_use=True,
                level="1",
            ),
            db=db,
        )

        # 2.1 101室
        room_101 = asset_svc.save_new_asset(
            RoomAddSchema(
                asset_id_parent=floor_1["asset_id"],
                asset_type="room",
                name="101室",
                is_use=True,
                number="101",
                room_purpose="办公室",
                max_current="16A",
                manager_name="张三",
            ),
            db=db,
        )

        # 2.1.1 网关-01（有温湿度 + 电流两个传感器）
        terminal_t1 = asset_svc.save_new_asset(
            TerminalAddSchema(
                asset_id_parent=room_101["asset_id"],
                asset_type="terminal",
                name="网关-01",
                is_use=True,
                number="T-001",
                model="GW-2000",
                location="101室配电箱",
                iot_number="SIM-001",
                iot_activate_human="管理员A",
            ),
            db=db,
        )

        sensor_t1_s1 = asset_svc.save_new_asset(
            SensorAddSchema(
                asset_id_parent=terminal_t1["asset_id"],
                asset_type="sensor",
                name="温湿度传感器-01",
                is_use=True,
                model_id="DHT22",
            ),
            db=db,
        )

        sensor_t1_s2 = asset_svc.save_new_asset(
            SensorAddSchema(
                asset_id_parent=terminal_t1["asset_id"],
                asset_type="sensor",
                name="电流传感器-01",
                is_use=True,
                model_id="CT-100",
            ),
            db=db,
        )

        # 2.1.2 网关-02（有光照一个传感器）
        terminal_t2 = asset_svc.save_new_asset(
            TerminalAddSchema(
                asset_id_parent=room_101["asset_id"],
                asset_type="terminal",
                name="网关-02",
                is_use=True,
                number="T-002",
                model="GW-2000",
                location="101室天花板",
                iot_number="SIM-002",
                iot_activate_human="管理员A",
            ),
            db=db,
        )

        sensor_t2_s1 = asset_svc.save_new_asset(
            SensorAddSchema(
                asset_id_parent=terminal_t2["asset_id"],
                asset_type="sensor",
                name="光照传感器-01",
                is_use=True,
                model_id="LUX-50",
            ),
            db=db,
        )

        # 2.2 102室
        room_102 = asset_svc.save_new_asset(
            RoomAddSchema(
                asset_id_parent=floor_1["asset_id"],
                asset_type="room",
                name="102室",
                is_use=True,
                number="102",
                room_purpose="会议室",
                max_current="32A",
                manager_name="李四",
            ),
            db=db,
        )

        # 2.2.1 网关-03（有温度 + 电压两个传感器）
        terminal_t3 = asset_svc.save_new_asset(
            TerminalAddSchema(
                asset_id_parent=room_102["asset_id"],
                asset_type="terminal",
                name="网关-03",
                is_use=True,
                number="T-003",
                model="GW-2000",
                location="102室配电箱",
                iot_number="SIM-003",
                iot_activate_human="管理员B",
            ),
            db=db,
        )

        sensor_t3_s1 = asset_svc.save_new_asset(
            SensorAddSchema(
                asset_id_parent=terminal_t3["asset_id"],
                asset_type="sensor",
                name="温度传感器-02",
                is_use=True,
                model_id="DS18B20",
            ),
            db=db,
        )

        sensor_t3_s2 = asset_svc.save_new_asset(
            SensorAddSchema(
                asset_id_parent=terminal_t3["asset_id"],
                asset_type="sensor",
                name="电压传感器-01",
                is_use=True,
                model_id="VT-200",
            ),
            db=db,
        )

        # ==========================================
        # 3. 创建 2层
        # ==========================================
        floor_2 = asset_svc.save_new_asset(
            FloorAddSchema(
                asset_id_parent=building["asset_id"],
                asset_type="floor",
                name="2层",
                is_use=True,
                level="2",
            ),
            db=db,
        )

        # 3.1 201室
        room_201 = asset_svc.save_new_asset(
            RoomAddSchema(
                asset_id_parent=floor_2["asset_id"],
                asset_type="room",
                name="201室",
                is_use=True,
                number="201",
                room_purpose="实验室",
                max_current="20A",
                manager_name="王五",
            ),
            db=db,
        )

        # 3.1.1 网关-04（有温湿度一个传感器）
        terminal_t4 = asset_svc.save_new_asset(
            TerminalAddSchema(
                asset_id_parent=room_201["asset_id"],
                asset_type="terminal",
                name="网关-04",
                is_use=True,
                number="T-004",
                model="GW-3000",
                location="201室配电箱",
                iot_number="SIM-004",
                iot_activate_human="管理员C",
            ),
            db=db,
        )

        sensor_t4_s1 = asset_svc.save_new_asset(
            SensorAddSchema(
                asset_id_parent=terminal_t4["asset_id"],
                asset_type="sensor",
                name="温湿度传感器-03",
                is_use=True,
                model_id="DHT22",
            ),
            db=db,
        )

        # ==========================================
        # 4. 返回结构化数据
        # ==========================================
        return {
            "building": building,
            "floors": {
                "1层": {
                    "asset": floor_1,
                    "rooms": {
                        "101室": {
                            "asset": room_101,
                            "terminals": {
                                "网关-01": {
                                    "asset": terminal_t1,
                                    "sensors": {
                                        "温湿度传感器-01": {"asset": sensor_t1_s1},
                                        "电流传感器-01": {"asset": sensor_t1_s2},
                                    },
                                },
                                "网关-02": {
                                    "asset": terminal_t2,
                                    "sensors": {
                                        "光照传感器-01": {"asset": sensor_t2_s1},
                                    },
                                },
                            },
                        },
                        "102室": {
                            "asset": room_102,
                            "terminals": {
                                "网关-03": {
                                    "asset": terminal_t3,
                                    "sensors": {
                                        "温度传感器-02": {"asset": sensor_t3_s1},
                                        "电压传感器-01": {"asset": sensor_t3_s2},
                                    },
                                },
                            },
                        },
                    },
                },
                "2层": {
                    "asset": floor_2,
                    "rooms": {
                        "201室": {
                            "asset": room_201,
                            "terminals": {
                                "网关-04": {
                                    "asset": terminal_t4,
                                    "sensors": {
                                        "温湿度传感器-03": {"asset": sensor_t4_s1},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

    def test_asset_count_change(self):
        """ 测试 count 的会随着资产的增删而正确改变 """
        try:
            with sql_manager.get_db("main") as db:
                # 1 构建资产树
                building_asset = AssetService().save_new_asset(self._new_building_asset(), db=db)
                floor1_asset = AssetService().save_new_asset(self._new_floor_asset(building_asset["asset_id"]), db=db)
                floor2_asset = AssetService().save_new_asset(self._new_floor_asset(building_asset["asset_id"]), db=db)
                room1_asset = AssetService().save_new_asset(self._new_room_asset(floor1_asset["asset_id"]), db=db)
                room2_asset = AssetService().save_new_asset(self._new_room_asset(floor1_asset["asset_id"]), db=db)
                room3_asset = AssetService().save_new_asset(self._new_room_asset(floor2_asset["asset_id"]), db=db)
                terminal1_asset = AssetService().save_new_asset(self._new_terminal_asset(room1_asset["asset_id"]), db=db)
                terminal2_asset = AssetService().save_new_asset(self._new_terminal_asset(room2_asset["asset_id"]), db=db)
                terminal3_asset = AssetService().save_new_asset(self._new_terminal_asset(room3_asset["asset_id"]), db=db)
                terminal4_asset = AssetService().save_new_asset(self._new_terminal_asset(room3_asset["asset_id"]), db=db)
                sensor1_asset = AssetService().save_new_asset(self._new_sensor_asset(terminal1_asset["asset_id"]), db=db)
                sensor2_asset = AssetService().save_new_asset(self._new_sensor_asset(terminal1_asset["asset_id"]), db=db)
                sensor3_asset = AssetService().save_new_asset(self._new_sensor_asset(terminal3_asset["asset_id"]), db=db)

                # 2. 验证增加资产 count 正确更新
                building_query = AssetService().query_asset_by_id(building_asset["asset_id"], db=db)
                self.assertEqual(2, building_query["floor_count"])
                self.assertEqual(3, building_query["room_count"])
                self.assertEqual(4, building_query["terminal_count"])
                self.assertEqual(3, building_query["sensor_count"])

                # 3. 验证删除资产 count 正确更新
                AssetService().drop_asset_by_id(room1_asset["asset_id"], db=db)
                building_query = AssetService().query_asset_by_id(building_asset["asset_id"], db=db)
                self.assertEqual(2, building_query["floor_count"])
                self.assertEqual(2, building_query["room_count"])
                self.assertEqual(3, building_query["terminal_count"])
                self.assertEqual(1, building_query["sensor_count"])

        finally:
            # 4. 删除资产树
            AssetService().drop_asset_by_id(building_asset["asset_id"], db=db)
            pass

    def test_asset_is_use_change(self):
        """ 测试 is_use 的会随着资产的修改而正确改变 """
        try:
            with sql_manager.get_db("main") as db:
                # 1. 构建资产树
                building_asset = AssetService().save_new_asset(self._new_building_asset(), db=db)
                floor1_asset = AssetService().save_new_asset(self._new_floor_asset(building_asset["asset_id"]), db=db)
                floor2_asset = AssetService().save_new_asset(self._new_floor_asset(building_asset["asset_id"]), db=db)
                room1_asset = AssetService().save_new_asset(self._new_room_asset(floor1_asset["asset_id"]), db=db)
                room2_asset = AssetService().save_new_asset(self._new_room_asset(floor1_asset["asset_id"]), db=db)
                room3_asset = AssetService().save_new_asset(self._new_room_asset(floor2_asset["asset_id"]), db=db)
                terminal1_asset = AssetService().save_new_asset(self._new_terminal_asset(room1_asset["asset_id"]), db=db)
                terminal2_asset = AssetService().save_new_asset(self._new_terminal_asset(room2_asset["asset_id"]), db=db)
                terminal3_asset = AssetService().save_new_asset(self._new_terminal_asset(room3_asset["asset_id"]), db=db)
                terminal4_asset = AssetService().save_new_asset(self._new_terminal_asset(room3_asset["asset_id"]), db=db)
                sensor1_asset = AssetService().save_new_asset(self._new_sensor_asset(terminal1_asset["asset_id"]), db=db)
                sensor2_asset = AssetService().save_new_asset(self._new_sensor_asset(terminal1_asset["asset_id"]), db=db)
                sensor3_asset = AssetService().save_new_asset(self._new_sensor_asset(terminal3_asset["asset_id"]), db=db)

                # 2. 修改资产 is_use 从 False 改为 True 其子资产正确更新
                building_update_schema = BuildingUpdateSchema(
                    asset_type="building",
                    name="测试修改楼宇",
                    number="B7",
                    is_use=True,
                    is_use_all=True,
                )
                AssetService().alter_asset_by_id(building_asset["asset_id"], building_update_schema, db=db)
                building_query = AssetService().query_asset_by_id(building_asset["asset_id"], db=db)
                self.assertEqual("测试修改楼宇", building_query["name"])
                self.assertEqual("B7", building_query["number"])
                self.assertEqual(True, building_query["is_use"])
                floor_query = AssetService().query_asset_by_id(floor2_asset["asset_id"], db=db)
                self.assertEqual(True, floor_query["is_use"])
                room_query = AssetService().query_asset_by_id(room2_asset["asset_id"], db=db)
                self.assertEqual(True, room_query["is_use"])
                terminal_query = AssetService().query_asset_by_id(terminal1_asset["asset_id"], db=db)
                self.assertEqual(True, terminal_query["is_use"])
                sensor_query = AssetService().query_asset_by_id(sensor3_asset["asset_id"], db=db)
                self.assertEqual(True, sensor_query["is_use"])

                # 2. 修改资产 is_use 从 True 改为 False 其子资产正确更新
                room_update_schema = RoomUpdateSchema(
                    asset_type="room",
                    name="测试修改房间",
                    is_use=False,
                )
                AssetService().alter_asset_by_id(room1_asset["asset_id"], room_update_schema, db=db)
                building_query = AssetService().query_asset_by_id(building_asset["asset_id"], db=db)
                self.assertEqual(True, building_query["is_use"])
                floor_query = AssetService().query_asset_by_id(floor1_asset["asset_id"], db=db)
                self.assertEqual(True, floor_query["is_use"])
                room_query = AssetService().query_asset_by_id(room1_asset["asset_id"], db=db)
                self.assertEqual("测试修改楼宇", building_query["name"])
                self.assertEqual(False, room_query["is_use"])
                terminal_query = AssetService().query_asset_by_id(terminal1_asset["asset_id"], db=db)
                self.assertEqual(False, terminal_query["is_use"])
                sensor_query = AssetService().query_asset_by_id(sensor1_asset["asset_id"], db=db)
                self.assertEqual(False, sensor_query["is_use"])


                # 2. 修改资产 is_use 从 False 改为 True 其父资产正确更新
                terminal_update_schema = TerminalUpdateSchema(
                    asset_type="terminal",
                    name="测试修改终端",
                    is_use=True,
                )
                AssetService().alter_asset_by_id(terminal1_asset["asset_id"], terminal_update_schema, db=db)
                building_query = AssetService().query_asset_by_id(building_asset["asset_id"], db=db)
                self.assertEqual(True, building_query["is_use"])
                floor_query = AssetService().query_asset_by_id(floor1_asset["asset_id"], db=db)
                self.assertEqual(True, floor_query["is_use"])
                room_query = AssetService().query_asset_by_id(room1_asset["asset_id"], db=db)
                self.assertEqual("测试修改楼宇", building_query["name"])
                self.assertEqual(True, room_query["is_use"])
                terminal_query = AssetService().query_asset_by_id(terminal1_asset["asset_id"], db=db)
                self.assertEqual(True, terminal_query["is_use"])
                sensor_query = AssetService().query_asset_by_id(sensor1_asset["asset_id"], db=db)
                self.assertEqual(False, sensor_query["is_use"])

        finally:
            # 4. 删除资产树
            AssetService().drop_asset_by_id(building_asset["asset_id"], db=db)
            pass

if __name__ == "__main__":
    with sql_manager.get_db("main") as db:
        tree = AssetTests.build_complex_tree(db)
        print(tree["building"]["name"])
    # unittest.main()

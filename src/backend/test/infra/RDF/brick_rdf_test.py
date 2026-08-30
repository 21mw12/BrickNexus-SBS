from app.infra.RDF.BrickRDFManager import BrickRDFManager
from rdflib.namespace import RDF, RDFS


def main():
    # 1. 初始化管理器（指定保存目录）
    brick_mgr = BrickRDFManager(save_dir="resources/rdf")

    # 2. 创建实体（设备和传感器）
    print("=== 创建实体 ===")

    # 创建 HVAC 设备
    chiller = brick_mgr.create_entity("Chiller_1", brick_mgr.BRICK.Chiller)
    brick_mgr.set_label(chiller, "冷水机组1号")

    ahu = brick_mgr.create_entity("AHU_1", brick_mgr.BRICK.AHU)
    brick_mgr.set_label(ahu, "空气处理机组1号")

    vav = brick_mgr.create_entity("VAV_1", brick_mgr.BRICK.VAV)
    brick_mgr.set_label(vav, "变风量箱1号")

    # 创建传感器
    temp_sensor = brick_mgr.create_entity("Temperature_Sensor_1", brick_mgr.BRICK.Temperature_Sensor)
    brick_mgr.set_label(temp_sensor, "温度传感器1号")

    # 3. 设置属性
    print("\n=== 设置属性 ===")
    brick_mgr.set_property(chiller, brick_mgr.BRICK.capacity, 500.0)
    brick_mgr.set_property(chiller, brick_mgr.BRICK.manufacturer, "特灵")
    brick_mgr.set_property(temp_sensor, brick_mgr.BRICK.unit, "°C")

    # 4. 建立关系
    print("\n=== 建立关系 ===")

    # 关系1：传感器监测设备
    brick_mgr.link(temp_sensor, brick_mgr.BRICK.isPointOf, chiller)

    # 关系2：空气流向（AHU -> VAV）
    brick_mgr.link(ahu, brick_mgr.BRICK.feeds, vav)

    # 关系3：VAV 服务于区域
    zone = brick_mgr.create_entity("Zone_1", brick_mgr.BRICK.Room)
    brick_mgr.set_label(zone, "会议室A")
    brick_mgr.link(vav, brick_mgr.BRICK.serves, zone)

    # 5. 确保自定义属性存在
    print("\n=== 定义自定义属性 ===")
    brick_mgr.ensure_property(
        brick_mgr.EX.maintenanceDate,
        "维护日期",
        brick_mgr.BRICK.Equipment,
        RDFS.Literal
    )

    # 设置自定义属性
    brick_mgr.set_property(chiller, brick_mgr.EX.maintenanceDate, "2026-04-23")

    # 6. 查询并显示所有数据
    print("\n=== 当前 RDF 图内容 ===")
    for s, p, o in brick_mgr.g:
        # 美化输出
        s_name = s.split('#')[-1] if '#' in str(s) else str(s)
        p_name = p.split('#')[-1] if '#' in str(p) else str(p)
        o_name = o.split('#')[-1] if hasattr(o, 'split') and '#' in str(o) else str(o)
        print(f"{s_name} -- {p_name} --> {o_name}")

    # 7. 解关联示例
    print("\n=== 解关联操作 ===")
    print("删除温度传感器与冷水机组的关联")
    brick_mgr.unlink(temp_sensor, brick_mgr.BRICK.isPointOf, chiller)

    # 验证解关联
    print("\n解关联后温度传感器的关系:")
    for s, p, o in brick_mgr.g.triples((temp_sensor, brick_mgr.BRICK.isPointOf, None)):
        print(f"温度传感器监测: {o}")
    else:
        print("温度传感器已没有任何监测对象")

    # 8. 删除实体示例
    print("\n=== 删除实体 ===")
    print("删除变风量箱 VAV_1")
    brick_mgr.delete_entity(vav)

    # 9. 保存到文件
    print("\n=== 保存数据 ===")
    brick_mgr.save("brick_data")
    print("数据已保存到 resources/rdf/brick_data.ttl")

    # 10. 重新加载验证
    print("\n=== 重新加载数据验证 ===")
    new_mgr = BrickRDFManager(save_dir="resources/rdf")
    new_mgr.load("brick_data")

    print("重新加载后的实体列表:")
    for s, p, o in new_mgr.g.triples((None, RDF.type, None)):
        entity_name = str(s).split('#')[-1] if '#' in str(s) else str(s)
        type_name = str(o).split('#')[-1] if '#' in str(o) else str(o)
        print(f"  - {entity_name} (类型: {type_name})")


if __name__ == "__main__":
    main()
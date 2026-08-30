from rdflib import Literal, URIRef

from app.infra.RDF.RDFManager import RDFManager

def main():
    # 1. 创建管理器实例
    rdf = RDFManager()

    # 2. 定义命名空间（简化 URI）
    ns = "http://example.org/"

    # 3. 添加三元组
    alice = URIRef(ns + "Alice")
    bob = URIRef(ns + "Bob")
    knows = URIRef(ns + "knows")
    name = URIRef(ns + "name")
    age = URIRef(ns + "age")

    rdf.add(alice, knows, bob)
    rdf.add(alice, name, Literal("Alice"))
    rdf.add(alice, age, Literal(30))

    # 4. 查询验证
    print("=== 添加后查询 ===")
    for s, p, o in rdf.g:
        print(f"{s} - {p} - {o}")

    # 5. 更新操作
    print("\n=== 更新年龄 ===")
    rdf.update(alice, age, Literal(31))
    for s, p, o in rdf.g.triples((alice, age, None)):
        print(f"Alice 年龄更新为: {o}")

    # 6. 保存到文件
    rdf.save_file("example")
    print("\n已保存到 example.ttl")

    # 7. 重新加载验证
    new_rdf = RDFManager()
    new_rdf.load_file("example")
    print("\n=== 从文件重新加载 ===")
    for s, p, o in new_rdf.g:
        print(f"{s} - {p} - {o}")

    # 8. 删除实体
    print("\n=== 删除 Bob 实体 ===")
    rdf.delete_entity(bob)
    for s, p, o in rdf.g:
        print(f"{s} - {p} - {o}")


if __name__ == "__main__":
    main()

import unittest
from app.core.utils.UUIDGenerator import uuid_generator

from app.infra.DB.SQLConnection import sql_manager
from app.domain.user.schema.PageSchema import PageAddSchema
from app.domain.user.service.PageService import PageService


class AssetTests(unittest.TestCase):

    @staticmethod
    def _new_page(page_code: str, page_id_parent: str = None) -> PageAddSchema:
        return PageAddSchema(
            page_id_parent=page_id_parent,
            name=f"Page-{uuid_generator.random()}",
            path_code=page_code,
        )

    def test_page(self):
        """ 测试页面的添加与删除正常 """
        try:
            with sql_manager.get_db("main") as db:
                # 1. 构建页面
                page1 = PageService().save_new_page(self._new_page("home"), db=db)
                page2 = PageService().save_new_page(self._new_page("user"), db=db)
                page2_1 = PageService().save_new_page(self._new_page("user:list", page2["page_id"]), db=db)
                page2_2 = PageService().save_new_page(self._new_page("user:form", page2["page_id"]), db=db)

                # 2. 删除页面
                page_tree = PageService().query_pages_tree(db=db)
                print(page_tree)

                # 2. 删除页面
                PageService().drop_page_by_id(page2["page_id"], db=db)

        finally:
            # 4. 删除剩余页面
            PageService().drop_page_by_id(page1["page_id"], db=db)
            pass


if __name__ == "__main__":
    unittest.main()
import unittest
from app.domain.user.schema.AssetPermissionSchema import (
    AssetPermissionSchema,
    AssetTypePermissionItem,
    AssetIdPermissionNode,
)

from app.infra.DB.SQLConnection import sql_manager
from app.domain.user.schema.RoleSchema import RoleAddSchema, RoleUpdateSchema
from app.domain.user.service.RoleService import RoleService
from app.domain.auth.service.RolePageService import RolePageService


class AssetTests(unittest.TestCase):

    @staticmethod
    def _new_role() -> RoleAddSchema:
        return RoleAddSchema(
            name="test_role",
            describe="测试角色",
            page_ids=[
                "abaf331c-4aad-4250-920b-6a82e3a3a8a0",
                "abfdb8bf-8cf3-412e-b698-c9e158da1a29"
            ],
            asset_permission=AssetPermissionSchema(
                part_asset_type=[
                    AssetTypePermissionItem(type="building", permission="CD"),
                    AssetTypePermissionItem(type="floor", permission="C"),
                ],
                part_asset_id=[
                    AssetIdPermissionNode(
                        asset_id="3ff6bf9c-dfea-44fd-ade7-45871c86fb4a",
                        permission="RU",
                        sub_assets=[
                            AssetIdPermissionNode(
                                asset_id="9f2222f6-c0e3-42c1-a701-80eaf566ee84",
                                permission="RU",
                                sub_assets=[
                                    AssetIdPermissionNode(
                                        asset_id="1e4ab4d7-bab0-4020-8ab1-9da00ba155c3",
                                        permission="RU",
                                        sub_assets=[
                                            AssetIdPermissionNode(
                                                asset_id="8b4a0227-2a5d-4631-9082-6c7ca3eebc72",
                                                permission="RU",
                                                sub_assets=[
                                                    AssetIdPermissionNode(
                                                        asset_id="ff443656-9076-496a-be40-da12ad8fc11e",
                                                        permission="RUO",
                                                    )
                                                ],
                                            )
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ]
            )
        )

    @staticmethod
    def _update_role() -> RoleUpdateSchema:
        return RoleUpdateSchema(
            name="test_role",
            describe="测试角色",
            page_ids=[
                "abaf331c-4aad-4250-920b-6a82e3a3a8a0",
                "abfdb8bf-8cf3-412e-b698-c9e158da1a29",
                "2c236d39-4392-4a70-8e3b-7354a134c959"
            ],
            asset_permission=AssetPermissionSchema(
                part_asset_type=[
                    AssetTypePermissionItem(type="building", permission="D"),
                    AssetTypePermissionItem(type="floor", permission="CD"),
                ],
                part_asset_id=[
                    AssetIdPermissionNode(
                        asset_id="3ff6bf9c-dfea-44fd-ade7-45871c86fb4a",
                        permission="R",
                        sub_assets=[
                            AssetIdPermissionNode(
                                asset_id="9f2222f6-c0e3-42c1-a701-80eaf566ee84",
                                permission="U",
                                sub_assets=[
                                    AssetIdPermissionNode(
                                        asset_id="1e4ab4d7-bab0-4020-8ab1-9da00ba155c3",
                                        permission="RU",
                                        sub_assets=[
                                            AssetIdPermissionNode(
                                                asset_id="8b4a0227-2a5d-4631-9082-6c7ca3eebc72",
                                                permission="U",
                                                sub_assets=[
                                                    AssetIdPermissionNode(
                                                        asset_id="ff443656-9076-496a-be40-da12ad8fc11e",
                                                        permission="RO",
                                                    )
                                                ],
                                            )
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ]
            )
        )

    def test_page(self):
        """ 测试页面的添加与删除正常 """
        try:
            with sql_manager.get_db("main") as db:
                # 1. 构建新角色
                role = RoleService().save_new_role(self._new_role(), db=db)

                # 2. 查询角色
                result = RoleService().query_role_by_id(role["role_id"], db=db)
                print(result)

                # 3. 修改角色
                result = RoleService().alter_role_by_id(role["role_id"], self._update_role(), db=db)
                print(result)


        finally:
            # 4. 删除角色
            RoleService().drop_role_by_id(role["role_id"], db=db)
            pass

if __name__ == "__main__":
    unittest.main()
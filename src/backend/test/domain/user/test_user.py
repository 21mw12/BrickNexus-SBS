import unittest

from app.core.utils.UUIDGenerator import uuid_generator
from app.domain.user.schema.AssetPermissionSchema import AssetPermissionSchema
from app.domain.user.schema.RoleSchema import RoleAddSchema
from app.domain.user.schema.UserSchema import UserAddSchema, UserUpdateSchema
from app.domain.user.service.RoleService import RoleService
from app.domain.user.service.UserService import UserService
from app.infra.DB.SQLConnection import sql_manager


class UserTests(unittest.TestCase):

    @staticmethod
    def _new_role() -> RoleAddSchema:
        return RoleAddSchema(
            name=f"user_role_{uuid_generator.random()[:8]}",
            describe="测试用户角色",
            page_ids=[],
            asset_permission=AssetPermissionSchema(
                part_asset_type=[],
                part_asset_id=[],
            ),
        )

    @staticmethod
    def _new_user(role_id: str) -> UserAddSchema:
        suffix = uuid_generator.random()[:8]
        return UserAddSchema(
            account=f"test_user_{suffix}",
            password="123456",
            nickname=f"测试用户_{suffix}",
            role_id=role_id,
        )

    @staticmethod
    def _update_user(role_id: str, account_suffix: str) -> UserUpdateSchema:
        return UserUpdateSchema(
            account=f"test_user_update_{account_suffix}",
            password="123456",
            nickname=f"测试用户修改_{account_suffix}",
            role_id=role_id,
        )

    def test_user_crud(self):
        """测试账号的增删改查正常"""
        role = None
        user = None

        try:
            with sql_manager.get_db("main") as db:
                # 1. 创建临时角色
                role = RoleService().save_new_role(self._new_role(), db=db)

                # 2. 新增用户
                user = UserService().save_new_user(self._new_user(role["role_id"]), db=db)
                print(user)

                # 3. 查询用户列表
                user_list = UserService().query_users_form(db=db, page=1, limit=1000)
                matched_user = next((item for item in user_list if item["user_id"] == user["user_id"]), None)
                self.assertIsNotNone(matched_user)
                self.assertEqual(matched_user["account"], user["account"])
                self.assertEqual(matched_user["nickname"], user["nickname"])

                # 4. 修改用户
                updated_user = UserService().alter_user_by_id(
                    user["user_id"],
                    self._update_user(role["role_id"], uuid_generator.random()[:8]),
                    db=db,
                )
                print(updated_user)

                # 5. 再次查询用户列表，确认修改结果
                user_list = UserService().query_users_form(db=db, page=1, limit=1000)
                matched_user = next((item for item in user_list if item["user_id"] == user["user_id"]), None)
                self.assertIsNotNone(matched_user)
                self.assertEqual(matched_user["account"], updated_user["account"])
                self.assertEqual(matched_user["nickname"], updated_user["nickname"])

                # 6. 重置密码
                self.assertTrue(UserService().reset_user_pwd_by_id(user["user_id"], db=db))

                # 7. 删除用户
                self.assertTrue(UserService().drop_user_by_id(user["user_id"], db=db))
                user = None

        finally:
            with sql_manager.get_db("main") as cleanup_db:
                # 8. 删除残留用户
                if user is not None:
                    try:
                        UserService().drop_user_by_id(user["user_id"], db=cleanup_db)
                    except Exception:
                        pass

                # 9. 删除角色
                if role is not None:
                    try:
                        RoleService().drop_role_by_id(role["role_id"], db=cleanup_db)
                    except Exception:
                        pass


if __name__ == "__main__":
    unittest.main()
from typing import List
from pydantic import BaseModel, ConfigDict

from app.domain.user.repository.models import Role
from app.domain.user.schema.AssetPermissionSchema import (
    AssetPermissionInputSchema,
    AssetPermissionSchema,
)


# ==========================================================
# 基类
# ==========================================================
class RoleBaseSchema(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str
    describe: str | None = None

    page_ids: list | None = None

    def to_role_model(self):
        """ 转换为 Role 对象 """
        return Role(
            name=self.name,
            describe=self.describe,
        )

# ==========================================================
# 用于新增 Role 的 schema 类
# ==========================================================
class RoleAddSchema(RoleBaseSchema):
    asset_permission: AssetPermissionInputSchema | None = None


# ==========================================================
# 用于修改 Role 的 schema 类
# ==========================================================
class RoleUpdateSchema(RoleBaseSchema):
    asset_permission: AssetPermissionInputSchema | None = None


# ==========================================================
# 用于返回给前端 Role 对象的 schema 类
# ==========================================================
class RoleResponseSchema(RoleBaseSchema):

    role_id: str

    page_codes: list | None = None
    asset_permission: AssetPermissionSchema | None = None

    @classmethod
    def from_models(
            cls,
            role: Role,
            page_ids: List[str],
            page_codes: List[str],
            asset_permission: AssetPermissionSchema
    ):
        return cls(
            role_id=role.role_id,
            name=role.name,
            describe=role.describe,
            page_ids=page_ids,
            page_codes=page_codes,
            asset_permission=asset_permission
        )


# ==========================================================
# 用于查询 Role 对象列表做属性过滤的 schema 类
# ==========================================================
class RoleQueryFilterSchema(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str | None = None
    describe: str | None = None

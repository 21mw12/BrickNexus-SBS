from typing import List, Optional
from pydantic import BaseModel, ConfigDict

from app.domain.user.repository.models import User


# ==========================================================
# 用于用户登录的 schema 类
# ==========================================================
class UserLoginSchema(BaseModel):

    model_config = ConfigDict(extra="forbid")

    account: str
    password: str


# ==========================================================
# 用于新增 User 的 schema 类
# ==========================================================
class UserAddSchema(BaseModel):

    model_config = ConfigDict(extra="forbid")

    account: str
    password: str
    nickname: str
    role_id: str


# ==========================================================
# 用户资产权限项（编辑用户时使用）
# ==========================================================
class UserAssetPermItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    perm_retrieve: bool = False
    perm_update: bool = False
    perm_delete: bool = False
    perm_operate: bool = False


# ==========================================================
# 用于修改 User 的 schema 类
# ==========================================================
class UserUpdateSchema(BaseModel):

    model_config = ConfigDict(extra="forbid")

    account: str
    password: str
    nickname: str
    role_id: str
    asset_permissions: Optional[List[UserAssetPermItem]] = None


# ==========================================================
# 用于查询 User 的筛选 schema 类
# ==========================================================
class UserQueryFilterSchema(BaseModel):

    model_config = ConfigDict(extra="forbid")

    account: str | None = None
    role_id: str | None = None

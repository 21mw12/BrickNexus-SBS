from pydantic import BaseModel, ConfigDict


class UserAssetInputSchema(BaseModel):
    """ 管理员为用户授予/修改资产实例权限的入参 """
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    perm_retrieve: bool = False
    perm_update: bool = False
    perm_delete: bool = False
    perm_operate: bool = False


class UserAssetResponseItem(BaseModel):
    """ 用户资产权限响应项 """
    model_config = ConfigDict(extra="forbid")

    user_asset_id: str
    user_id: str
    asset_id: str
    perm_retrieve: bool = False
    perm_update: bool = False
    perm_delete: bool = False
    perm_operate: bool = False

from pydantic import BaseModel, ConfigDict


class AssetTypePermissionItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    type: str
    permission: str


# ==========================================================
# 入参：平铺列表
# ==========================================================
class AssetIdPermissionNode(BaseModel):
    """ 入参节点，仅 asset_id + permission，无子节点 """

    model_config = ConfigDict(
        extra="forbid"
    )

    asset_id: str
    permission: str


class AssetPermissionInputSchema(BaseModel):
    """ 入参：资产类型权限 + 资产实例权限（平铺列表） """

    model_config = ConfigDict(
        extra="forbid"
    )

    part_asset_type: list[AssetTypePermissionItem] | None = None
    part_asset_id: list[AssetIdPermissionNode] | None = None


# ==========================================================
# 出参：树形结构（前端展示用）
# ==========================================================
class AssetIdPermissionTreeNode(BaseModel):
    """ 出参节点，含 name + sub_assets 构成树形 """

    model_config = ConfigDict(
        extra="forbid"
    )

    asset_id: str
    name: str | None = None
    permission: str
    sub_assets: list["AssetIdPermissionTreeNode"] | None = None


class AssetPermissionSchema(BaseModel):
    """ 出参：资产类型权限 + 资产实例权限树 """

    model_config = ConfigDict(
        extra="forbid"
    )

    part_asset_type: list[AssetTypePermissionItem] | None = None
    part_asset_id: list[AssetIdPermissionTreeNode] | None = None


AssetIdPermissionTreeNode.model_rebuild()

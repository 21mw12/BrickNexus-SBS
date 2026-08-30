from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean

from app.infra.DB.SQLConnection import Base


class RoleAsset(Base):
    __tablename__ = "role_asset"

    permission_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="权限id")
    role_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="角色id")
    asset_id: Mapped[str] = mapped_column(String(100), nullable=True, comment="资产id（实例权限时使用）")
    asset_type: Mapped[str] = mapped_column(String(20), nullable=True, comment="资产类型（类型权限时使用）")

    perm_create: Mapped[bool] = mapped_column(Boolean, default=False, comment="增加权限 C")
    perm_retrieve: Mapped[bool] = mapped_column(Boolean, default=False, comment="查看权限 R")
    perm_update: Mapped[bool] = mapped_column(Boolean, default=False, comment="修改权限 U")
    perm_delete: Mapped[bool] = mapped_column(Boolean, default=False, comment="删除权限 D")
    perm_operate: Mapped[bool] = mapped_column(Boolean, default=False, comment="操作权限 O")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"permission_id:      {self.permission_id}")
        print(f"role_id:            {self.role_id}")
        print(f"asset_id:           {self.asset_id}")
        print(f"asset_type:         {self.asset_type}")
        print(f"perm_create:        {self.perm_create}")
        print(f"perm_retrieve:      {self.perm_retrieve}")
        print(f"perm_update:        {self.perm_update}")
        print(f"perm_delete:        {self.perm_delete}")
        print(f"perm_operate:       {self.perm_operate}")
        print("=" * 60)

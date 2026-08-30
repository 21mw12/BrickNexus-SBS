from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean

from app.infra.DB.SQLConnection import Base


class UserAsset(Base):
    __tablename__ = "user_asset"

    user_asset_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="用户资产权限ID")
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="用户ID")
    asset_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="资产ID")

    perm_retrieve: Mapped[bool] = mapped_column(Boolean, default=False, comment="查看权限 R")
    perm_update: Mapped[bool] = mapped_column(Boolean, default=False, comment="修改权限 U")
    perm_delete: Mapped[bool] = mapped_column(Boolean, default=False, comment="删除权限 D")
    perm_operate: Mapped[bool] = mapped_column(Boolean, default=False, comment="操作权限 O")

    def print_info(self):
        """ 打印基本信息 """
        print("=" * 60)
        print(f"user_asset_id:      {self.user_asset_id}")
        print(f"user_id:            {self.user_id}")
        print(f"asset_id:           {self.asset_id}")
        print(f"perm_retrieve:      {self.perm_retrieve}")
        print(f"perm_update:        {self.perm_update}")
        print(f"perm_delete:        {self.perm_delete}")
        print(f"perm_operate:       {self.perm_operate}")
        print("=" * 60)

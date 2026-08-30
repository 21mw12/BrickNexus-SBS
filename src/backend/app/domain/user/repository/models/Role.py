from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer

from app.infra.DB.SQLConnection import Base

class Role(Base):
    __tablename__ = "role"

    role_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="角色ID")
    name: Mapped[str] = mapped_column(String(30), nullable=False, comment="角色名称")
    describe: Mapped[str] = mapped_column(String(150), nullable=False, comment="角色描述")

    def print_info(self):
        print("=" * 60)
        print(f"role_id:            {self.role_id}")
        print(f"name:               {self.name}")
        print(f"describe:           {self.describe}")
        print("=" * 60)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base


class RolePage(Base):
    __tablename__ = "role_page"

    role_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="角色id")
    page_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="页面id")

    def print_info(self):
        print("=" * 60)
        print(f"role_id:            {self.role_id}")
        print(f"page_id:            {self.page_id}")
        print("=" * 60)

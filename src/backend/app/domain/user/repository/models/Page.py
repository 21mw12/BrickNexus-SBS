from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base


class Page(Base):
    __tablename__ = "page"

    page_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="页面id")
    page_id_parent: Mapped[str] = mapped_column(String(100), nullable=True, comment="父页面id")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="页面名称")
    path_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="页面编码")

    def print_info(self):
        print("=" * 60)
        print(f"page_id:            {self.page_id}")
        print(f"page_id_parent:     {self.page_id_parent}")
        print(f"name:               {self.name}")
        print(f"path_code:          {self.path_code}")
        print("=" * 60)

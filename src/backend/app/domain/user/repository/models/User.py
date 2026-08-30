from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.infra.DB.SQLConnection import Base

class User(Base):
    __tablename__ = "user"

    user_id: Mapped[str] = mapped_column(String(100), primary_key=True, comment="用户ID")
    role_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="所属角色ID")
    account: Mapped[str] = mapped_column(String(30), nullable=False, comment="账号")
    nickname: Mapped[str] = mapped_column(String(30), nullable=False, comment="昵称")
    password: Mapped[str] = mapped_column(String(130), nullable=False, comment="密码")

    def print_info(self):
        print("=" * 60)
        print(f"user_id:            {self.user_id}")
        print(f"role_id:            {self.role_id}")
        print(f"account:            {self.account}")
        print(f"nickname:           {self.nickname}")
        print(f"password:           {self.password}")
        print("=" * 60)
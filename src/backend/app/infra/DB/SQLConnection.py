#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/23
# @function : SQL连接管理
# @version  : v2.0
"""
get_db使用方法
with sql_manager.get_db("main") as db:
        sensor = SensorData(
            temperature=data["temperature"],
            humidity=data["humidity"]
        )
        db.add(sensor)

get_db_dep使用方法
def create_sensor(data: dict, db: Session = Depends(sql_manager.get_db_dep("main"))):
    sensor = SensorData(
        temperature=data["temperature"],
        humidity=data["humidity"]
    )
    try:
        db.add(sensor)
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()
"""

from urllib.parse import quote
from contextlib import contextmanager
from typing import Dict, Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config.ConfigLoader import config

# 全局 Base（必须全局唯一）
Base = declarative_base()

class SQLConnection:
    def __init__(self, is_echo: bool = False):
        """
        :param is_echo: SQL调试，是否把 SQLAlchemy 实际发送给数据库的 SQL 语句，原样打印出来。
        """
        self.db_config = config.db
        self.is_echo = is_echo

        # 多库 engine / session 管理
        self.engines: Dict[str, any] = {}
        self.sessions: Dict[str, sessionmaker] = {}

        self._init_engines()

    def _init_engines(self):
        """ 初始化所有数据库连接 """
        for key, db_name in self.db_config.db_names.items():
            url = self._build_url(db_name)

            engine = create_engine(
                url,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
                echo=self.is_echo
            )

            self.engines[key] = engine
            self.sessions[key] = sessionmaker(
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
                bind=engine
            )

    def _build_url(self, db_name: str) -> str:
        """ 构建连接 URL """
        db = self.db_config

        if db.type == "mysql":
            return (
                f"mysql+pymysql://{db.username}:{quote(db.password)}@"
                f"{db.host}:{db.port}/{db_name}"
            )

        elif db.type in ["pgsql", "postgresql"]:
            return (
                f"postgresql+psycopg2://{db.username}:{quote(db.password)}@"
                f"{db.host}:{db.port}/{db_name}"
            )

        raise ValueError(f"Unsupported db type: {db.type}")

    # 获取 session（核心）
    @contextmanager
    def get_db(self, db_key: str = "main") -> Generator[Session, None, None]:
        """ 获取 session，自动 commit / rollback。用 with 管理声明周期 """
        if db_key not in self.sessions:
            raise ValueError(f"Unknown database key: {db_key}")

        db = self.sessions[db_key]()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_db_dep(self, db_key: str = "main"):
        """ 获取 session，手动 commit / rollback。用 Depends 管理声明周期 """
        def _get_db():
            db = self.sessions[db_key]()
            try:
                yield db
            finally:
                db.close()

        return _get_db

    def create_tables(self, db_key: str = "main"):
        """ 对注册的类建立对应的表 """
        engine = self.engines.get(db_key)
        if not engine:
            raise ValueError(f"Unknown database key: {db_key}")

        Base.metadata.create_all(bind=engine)

sql_manager = SQLConnection()

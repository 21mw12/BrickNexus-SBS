#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/24
# @function : 路径解析与配置定位
# @version  : v1.0

import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

def get_project_root() -> Path:
    """ 向上查找直到发现 config.yaml 文件 """
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "config.yaml").exists():
            return parent

    raise RuntimeError("Project root not found: config.yaml is required.")


# 从后端项目目录加载开发配置。系统环境变量优先，方便 Docker/生产部署覆盖。
load_dotenv(get_project_root() / ".env", override=False)

def resolve_path(path_value: str, root: Path) -> Path:
    """ 将路径解析为绝对路径（相对路径基于 project_root） """
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()

class Settings:
    """ 全局配置对象（推荐唯一入口） """
    def __init__(self):
        # 项目根目录
        self.project_root: Path = get_project_root()

        # 核心路径
        self.config_path: Path = self._resolve_env_path(
            "SMARTBUILDING_CONFIG_PATH",
            "config.yaml"
        )

        self.log_dir: Path = self._resolve_env_path(
            "SMARTBUILDING_LOG_DIR",
            "logs"
        )

        self.rdf_dir: Path = self._resolve_env_path(
            "SMARTBUILDING_RDF_DIR",
            "resources/rdf"
        )

        # 自动创建目录
        self._ensure_dirs()

    def _resolve_env_path(self, env_name: str, default: str) -> Path:
        value = os.getenv(env_name, default)
        return resolve_path(value, self.project_root)

    def _ensure_dirs(self):
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.rdf_dir.mkdir(parents=True, exist_ok=True)

@lru_cache()
def get_env_settings() -> Settings:
    """ 全局唯一 Settings 实例 """
    return Settings()

#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/23
# @function : 通用 RDF 操作
# @version  : v2.0
from pathlib import Path

from rdflib import Graph, URIRef
from app.common.EnvLoader import get_env_settings, resolve_path

env_settings = get_env_settings()

class RDFManager:

    def __init__(self, save_dir: str = None):
        self.g = Graph()
        self.save_path = (
            resolve_path(save_dir, env_settings.project_root)
            if save_dir is not None
            else env_settings.rdf_dir
        )
        self.save_path.mkdir(parents=True, exist_ok=True)

    # =========================
    # 基础三元组操作
    # =========================
    def add(self, s, p, o):
        self.g.add((s, p, o))

    def remove(self, s=None, p=None, o=None):
        self.g.remove((s, p, o))

    def update(self, s, p, o):
        self.g.remove((s, p, None))
        if o is not None:
            self.g.add((s, p, o))

    def delete_entity(self, uri: URIRef):
        """删除实体（双向）"""
        self.g.remove((uri, None, None))
        self.g.remove((None, None, uri))

    # =========================
    # IO 操作
    # =========================
    def load_file(self, filename: str = "rdf"):
        self.g.parse(str(Path(self.save_path) / f"{filename}.ttl"), format="turtle")

    def save_file(self, filename: str = "rdf"):
        self.g.serialize(str(Path(self.save_path) / f"{filename}.ttl"), format="turtle")

#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/04/23
# @function : brick RDF 操作
# @version  : v1.0

import os
from pathlib import Path
from rdflib import Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

from app.infra.RDF.RDFManager import RDFManager   # 你自己路径


class BrickRDFManager(RDFManager):
    """
    Brick 语义管理层
    """

    def __init__(self, save_dir: str = None):
        super().__init__(save_dir or "resources/rdf")

        # =========================
        # 命名空间
        # =========================
        self.BRICK = Namespace("https://brickschema.org/schema/Brick#")
        self.BF = Namespace("https://brickschema.org/schema/BrickFrame#")
        self.EX = Namespace("https://seee.sues.edu.cn/#")

        self.g.bind("brick", self.BRICK)
        self.g.bind("bf", self.BF)
        self.g.bind("ex", self.EX)

    # =========================
    # 文件操作
    # =========================
    def load(self, filename: str = "brick"):
        file_path = Path(self.save_path) / f"{filename}.ttl"
        if file_path.exists():
            super().load_file(filename)

    def save(self, filename: str = "brick"):
        super().save_file(filename)

    # =========================
    # 语义操作
    # =========================
    def create_entity(self, entity_id: str, entity_type) -> URIRef:
        uri = self.EX[entity_id]
        self.add(uri, RDF.type, entity_type)
        return uri

    def set_label(self, uri: URIRef, label: str):
        self.add(uri, RDFS.label, Literal(label))

    def set_property(self, uri: URIRef, prop: URIRef, value):
        self.update(uri, prop, Literal(value))

    def link(self, src: URIRef, relation: URIRef, dst: URIRef):
        self.add(src, relation, dst)

    def unlink(self, src: URIRef, relation: URIRef, dst: URIRef):
        self.remove(src, relation, dst)

    def ensure_property(self, prop, label, domain, range_):
        """确保属性存在"""
        if (prop, RDF.type, RDF.Property) not in self.g:
            self.add(prop, RDF.type, RDF.Property)
            self.add(prop, RDFS.label, Literal(label))
            self.add(prop, RDFS.domain, domain)
            self.add(prop, RDFS.range, range_)

brickRDF_manager = BrickRDFManager()

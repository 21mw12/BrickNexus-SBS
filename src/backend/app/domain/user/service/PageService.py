from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session

from app.common.validators import ValidationError
from app.domain.user.repository import PageRepository
from app.domain.auth.repository import RolePageRepository
from app.domain.user.schema import PageAddSchema


class PageService:
    """页面相关业务逻辑封装"""

    # ==========================================================
    # 功能性Service
    # ==========================================================

    @staticmethod
    def query_pages_tree(db: Session, page_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询所有页面信息（树结构）
        :param db: 数据库会话
        :param page_id: 指定根页面 ID
        :return: 所有页面信息（树结构）
        """
        # 1. 查询全部页面
        page_repo = PageRepository()
        pages = page_repo.select(db)

        # 2. 构造节点映射
        nodes: Dict[str, Dict[str, Any]] = {}
        roots: List[Dict[str, Any]] = []
        for page in pages:
            nodes[page.page_id] = {
                "page_id": page.page_id,
                "page_id_parent": page.page_id_parent,
                "name": page.name,
                "path_code": page.path_code,
            }

        # 3. 组装树结构
        for page in pages:
            node = nodes[page.page_id]
            if page.page_id_parent and page.page_id_parent in nodes:
                parent = nodes[page.page_id_parent]
                parent.setdefault("sub_pages", []).append(node)
            else:
                roots.append(node)

        # 4. 按指定根节点返回
        if page_id:
            root = nodes.get(page_id)
            return [root] if root else []

        return roots

    @staticmethod
    def save_new_page(page_data: PageAddSchema, db: Session) -> Dict[str, Any]:
        """
        创建页面信息
        :param page_data: 用于新建页面 Schema 对象
        :param db: 数据库会话
        :return: 新建的角色对象的字典
        """
        # 1. schema 转 dict
        if hasattr(page_data, "model_dump"):
            payload = page_data.model_dump(exclude_none=True)
        else:
            payload = page_data
        if not isinstance(payload, dict):
            raise ValidationError("invalid payload")

        # 2. Repository
        page_repo = PageRepository()

        # 3. 开启事务
        try:
            # 4. 构造角色对象，并创建
            page = page_data.to_page_model()
            page = page_repo.create(page, db=db)
            if page is None:
                raise ValidationError("create page failed")

            # 5. 提交事务 & refresh
            db.commit()
            db.refresh(page)

            # 6. 构造响应
            return {
                "page_id": page.page_id,
                "page_id_parent": page.page_id_parent,
                "name": page.name,
                "path_code": page.path_code,
            }

        except Exception:
            # 7. 回滚事务
            db.rollback()

            raise

    @staticmethod
    def drop_page_by_id(page_id: str, db: Session) -> bool:
        """
        根据 id 删除页面信息
        :param page_id: 页面 ID
        :param db: 数据库会话
        :return: 删除是否成功
        """
        # 1. Repository
        page_repo = PageRepository()
        role_page_repo = RolePageRepository()

        # 2. 查询页面
        page = page_repo.get(page_id, db)
        if page is None:
            raise ValidationError("page not exists")

        # 3. 收集待删除页面（父页面需包含所有子页面）
        page_ids = [page.page_id]
        if page.page_id_parent is None:
            queue = [page.page_id]
            while queue:
                current_id = queue.pop(0)
                children = page_repo.select(
                    db,
                    filters={"page_id_parent": current_id},
                )
                for child in children:
                    if child.page_id in page_ids:
                        continue
                    page_ids.append(child.page_id)
                    queue.append(child.page_id)

        # 4. 开启事务，删除关联与页面
        try:
            # 5. 删除角色-页面关联
            role_page_repo.bulk_delete("page_id", page_ids, db)

            # 6. 删除页面
            page_repo.bulk_delete("page_id", page_ids, db)

            # 7. 提交事务
            db.commit()
            return True

        except Exception:
            # 8. 回滚事务
            db.rollback()
            raise






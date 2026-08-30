#!/usr/bin/python
# _*_coding:utf-8_*_
# @author   : mw
# @time     : 2026/05/19
# @function : 泛型 SQLAlchemy Repository 基类
# @version  : v2.0

from typing import (
    Any,
    Dict,
    Generic,
    Optional,
    Type,
    TypeVar,
    Callable,
    Union,
    List,
)

from sqlalchemy import (
    select,
    func,
    and_, delete,
)

from sqlalchemy.orm import (
    Session,
    selectinload,
)

from sqlalchemy.sql import Select
from sqlalchemy.inspection import inspect

T = TypeVar("T")


# 支持的查询操作符
OPERATORS = {
    "eq": lambda c, v: c == v,
    "ne": lambda c, v: c != v,
    "gt": lambda c, v: c > v,
    "gte": lambda c, v: c >= v,
    "lt": lambda c, v: c < v,
    "lte": lambda c, v: c <= v,
    "in": lambda c, v: c.in_(v),
    "notin": lambda c, v: ~c.in_(v),
    "like": lambda c, v: c.contains(v),
    "startswith": lambda c, v: c.startswith(v),
    "ilike": lambda c, v: c.ilike(f"%{v}%"),
    "isnull": lambda c, v: c.is_(None) if v else c.is_not(None),
}


class BaseRepository(Generic[T]):

    model: Type[T]

    # ==========================================================
    # 主键辅助方法
    # ==========================================================

    @classmethod
    def _get_pk_columns(cls) -> List[str]:
        """
        获取主键字段名列表（支持复合主键）
        :return: 主键字段名列表
        """
        # 1. 获取模型主键字段名
        mapper = inspect(cls.model)
        return [column.key for column in mapper.primary_key]

    @classmethod
    def _get_pk_attrs(cls, obj: T) -> Dict[str, Any]:
        """
        获取对象主键字段和值
        :param obj: 模型实例
        :return: 主键字段和值的映射
        """
        # 1. 获取主键字段名
        pk_columns = cls._get_pk_columns()

        # 2. 组装字段和值
        return {
            col: getattr(obj, col)
            for col in pk_columns
        }

    # ==========================================================
    # Query Builder
    # ==========================================================

    @classmethod
    def _apply_filters(cls, stmt: Select, filters: Optional[Dict[str, Any]]) -> Select:
        """
        应用过滤条件
        :param stmt: 原查询语句
        :param filters: 过滤条件字典
        :return: 应用过滤后的查询语句
        """
        # 1. 过滤为空时直接返回
        if not filters:
            return stmt
        
        # 2. 解析过滤条件并累计
        conditions = []
        for key, value in filters.items():
            # 支持: age__gt | name__like

            if "__" in key:
                field, op = key.split("__", 1)
            else:
                field, op = key, "eq"

            if not hasattr(cls.model, field):
                raise ValueError(
                    f"invalid filter field: {field}"
                )

            if op not in OPERATORS:
                raise ValueError(
                    f"invalid operator: {op}"
                )

            column = getattr(cls.model, field)
            condition = OPERATORS[op](column, value)
            conditions.append(condition)
        
        # 3. 合并条件并返回
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        return stmt

    @classmethod
    def _apply_order_by(cls, stmt: Select, order_by: Optional[Union[str, List[str]]]) -> Select:
        """
        应用排序条件
        :param stmt: 原查询语句
        :param order_by: 排序字段或列表（支持 -field 表示倒序）
        :return: 应用排序后的查询语句
        """
        # 1. 排序为空时直接返回
        if not order_by:
            return stmt

        # 2. 统一为列表处理
        if isinstance(order_by, str):
            order_by = [order_by]

        # 3. 解析字段并生成排序
        orders = []
        for item in order_by:
            desc = item.startswith("-")
            field = item[1:] if desc else item

            if not hasattr(cls.model, field):
                raise ValueError(
                    f"invalid order field: {field}"
                )

            column = getattr(cls.model, field)
            orders.append(
                column.desc() if desc else column.asc()
            )

        # 4. 应用排序并返回
        return stmt.order_by(*orders)

    @staticmethod
    def _apply_pagination(stmt: Select, page: Optional[int], page_size: Optional[int]) -> Select:
        """
        应用分页条件
        :param stmt: 原查询语句
        :param page: 页码（从 1 开始）
        :param page_size: 每页条数
        :return: 应用分页后的查询语句
        """
        # 1. 缺少分页参数时直接返回
        if page is None or page_size is None:
            return stmt

        # 2. 规范化分页参数
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        # 3. 应用 offset/limit
        return stmt.offset( (page - 1) * page_size ).limit(page_size)

    @classmethod
    def _apply_loads(cls, stmt: Select, loads: Optional[List[str]]) -> Select:
        """
        应用关系加载策略
        :param stmt: 原查询语句
        :param loads: 需要预加载的关系名列表
        :return: 应用加载后的查询语句
        """
        # 1. 未指定加载关系时直接返回
        if not loads:
            return stmt

        # 2. 逐个关系应用 selectinload
        for relation in loads:

            if not hasattr(cls.model, relation):
                raise ValueError(
                    f"invalid relation: {relation}"
                )

            stmt = stmt.options(
                selectinload(
                    getattr(cls.model, relation)
                )
            )

        # 3. 返回更新后的语句
        return stmt

    @classmethod
    def _apply_joins(cls, stmt: Select, joins: Optional[List[str]]) -> Select:
        """
        应用关联查询
        :param stmt: 原查询语句
        :param joins: 需要 join 的关系名列表
        :return: 应用关联后的查询语句
        """
        # 1. 未指定关联时直接返回
        if not joins:
            return stmt

        # 2. 逐个关系应用 join
        for relation in joins:

            if not hasattr(cls.model, relation):
                raise ValueError(
                    f"invalid join relation: {relation}"
                )

            stmt = stmt.join(
                getattr(cls.model, relation)
            )

        # 3. 返回更新后的语句
        return stmt

    # ==========================================================
    # Hook
    # ==========================================================

    def _before_create(self, item: T, db: Session ) -> None:
        """
        创建前钩子
        :param item: 待创建对象
        :param db: 数据库会话
        :return: 无
        """
        return

    def _after_create(self, item: T, db: Session) -> None:
        """
        创建后钩子
        :param item: 已创建对象
        :param db: 数据库会话
        :return: 无
        """
        return

    def _before_update(self, obj: T, values: Dict[str, Any], db: Session) -> None:
        """
        更新前钩子
        :param obj: 目标对象
        :param values: 待更新字段和值
        :param db: 数据库会话
        :return: 无
        """
        return

    def _after_update(self, obj: T, values: Dict[str, Any], db: Session) -> None:
        """
        更新后钩子
        :param obj: 目标对象
        :param values: 已更新字段和值
        :param db: 数据库会话
        :return: 无
        """
        return

    def _before_delete(self, obj: T, db: Session) -> None:
        """
        删除前钩子
        :param obj: 目标对象
        :param db: 数据库会话
        :return: 无
        """
        return

    def _after_delete(self, obj: T, db: Session) -> None:
        """
        删除后钩子
        :param obj: 已删除对象
        :param db: 数据库会话
        :return: 无
        """
        return

    def _before_select(self, db: Session) -> None:
        """
        查询前钩子
        :param db: 数据库会话
        :return: 无
        """
        return

    def _after_select(self, results: Union[List[T], T], db: Session) -> Union[List[T], T]:
        """
        查询后钩子
        :param results: 查询结果
        :param db: 数据库会话
        :return: 处理后的查询结果
        """
        return results

    def _before_get(self, ident: Any, db: Session) -> None:
        """
        获取前钩子
        :param ident: 主键值
        :param db: 数据库会话
        :return: 无
        """
        return

    def _after_get(self, obj: Optional[T], db: Session) -> Optional[T]:
        """
        获取后钩子
        :param obj: 查询结果对象
        :param db: 数据库会话
        :return: 处理后的对象
        """
        return obj

    # ==========================================================
    # Create
    # ==========================================================

    def create(
        self,
        item: T,
        db: Session,
        *,
        refresh: bool = True,
        callback_success: Optional[Callable[[T], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> Optional[T]:
        """
        创建记录
        :param item: 待创建对象
        :param db: 数据库会话
        :param refresh: 是否刷新对象
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 创建后的对象
        """
        try:
            # 1. 创建前钩子与写入
            self._before_create(item, db)
            db.add(item)
            db.flush()

            # 2. 可选刷新并执行后置钩子
            if refresh:
                db.refresh(item)
            self._after_create(item, db)

            # 3. 成功回调并返回
            if callback_success:
                callback_success(item)
            return item

        except Exception as e:
            # 4. 错误回调并抛出
            if callback_error:
                callback_error(e)
            raise

    def bulk_create(
        self,
        items: List[T],
        db: Session,
        *,
        chunk_size: int = 1000,
        use_insert: bool = False,
        return_objects: bool = True,
        callback_success: Optional[Callable[[List[T]], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> List[T]:
        """
        批量保存对象
        :param items: 对象列表
        :param db: 数据库会话
        :param chunk_size: 分块大小
        :param use_insert: 是否使用 insert 模式（最高性能）
        :param return_objects: 是否返回对象
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 保存后的对象列表
        """
        try:
            # 1. 空列表直接返回
            if not items:
                return []

            # 2. before hook
            for item in items:
                self._before_create(item, db)

            # insert 模式（最快）
            if use_insert:
                mapper = inspect(self.model)
                columns = {
                    column.key
                    for column in mapper.columns
                }

                payloads = []

                for item in items:
                    data = {
                        key: getattr(item, key)
                        for key in columns
                        if hasattr(item, key)
                    }
                    payloads.append(data)

                # 分块插入
                for i in range(0, len(payloads), chunk_size):
                    chunk = payloads[i:i + chunk_size]

                    db.execute(
                        self.model.__table__.insert(),
                        chunk,
                    )

            # bulk_save_objects 模式
            else:
                for i in range(0, len(items), chunk_size):
                    chunk = items[i:i + chunk_size]
                    db.bulk_save_objects(
                        chunk,
                        return_defaults=False,
                    )

            db.flush()

            # 3. after hook
            for item in items:
                self._after_create(item, db)

            # 4. callback
            if callback_success:
                callback_success(items)

            return items if return_objects else []

        except Exception as e:
            if callback_error:
                callback_error(e)

            raise

    # ==========================================================
    # Select
    # ==========================================================

    def select(
        self,
        db: Session,
        *,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Union[str, List[str]]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        joins: Optional[List[str]] = None,
        loads: Optional[List[str]] = None,
        count_only: bool = False,
        callback_success: Optional[Callable[[Union[List[T], int]], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> Union[List[T], int]:
        """
        查询列表或统计数量
        :param db: 数据库会话
        :param filters: 过滤条件
        :param order_by: 排序字段或列表
        :param page: 页码
        :param page_size: 每页条数
        :param joins: 关联关系列表
        :param loads: 预加载关系列表
        :param count_only: 是否仅统计数量
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 对象列表或统计数量
        """
        try:
            # 1. 构建基础查询
            stmt = (
                select(func.count()).select_from(self.model)
                if count_only
                else select(self.model)
            )

            # 2. 应用 joins 与 filters
            stmt = self._apply_joins(stmt, joins)
            stmt = self._apply_filters(stmt, filters)

            # 3. 应用排序、分页与预加载
            if not count_only:
                stmt = self._apply_order_by(
                    stmt,
                    order_by,
                )
                stmt = self._apply_pagination(
                    stmt,
                    page,
                    page_size,
                )
                stmt = self._apply_loads(
                    stmt,
                    loads,
                )

            # 4. 执行查询并后置处理
            self._before_select(db)
            result = db.execute(stmt)
            if count_only:
                ret = result.scalar() or 0
            else:
                ret = result.scalars().unique().all()
            ret = self._after_select(ret, db)

            # 5. 成功回调并返回
            if callback_success:
                callback_success(ret)
            return ret

        except Exception as e:
            # 6. 错误回调并抛出
            if callback_error:
                callback_error(e)
            raise

    # ==========================================================
    # Select One
    # ==========================================================

    def select_one(
        self,
        db: Session,
        *,
        filters: Optional[Dict[str, Any]] = None,
        joins: Optional[List[str]] = None,
        loads: Optional[List[str]] = None,
        callback_success: Optional[Callable[[Optional[T]], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> Optional[T]:
        """
        查询单个对象
        :param db: 数据库会话
        :param filters: 过滤条件
        :param joins: 关联关系列表
        :param loads: 预加载关系列表
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 查询到的对象或 None
        """
        try:
            # 1. 构建查询
            stmt = select(self.model)
            stmt = self._apply_joins(stmt, joins)
            stmt = self._apply_filters(stmt, filters)
            stmt = self._apply_loads(stmt, loads)

            # 2. 执行并取首个结果
            result = db.execute(stmt)
            obj = result.scalars().unique().first()

            # 3. 后置处理并回调
            obj = self._after_get(obj, db)
            if callback_success:
                callback_success(obj)
            return obj

        except Exception as e:
            # 4. 错误回调并抛出
            if callback_error:
                callback_error(e)
            raise

    # ==========================================================
    # Exists
    # ==========================================================

    def exists(
        self,
        db: Session,
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        判断记录是否存在
        :param db: 数据库会话
        :param filters: 过滤条件
        :return: 是否存在
        """
        # 1. 构建计数查询
        stmt = select(
            func.count()
        ).select_from(self.model)

        # 2. 应用过滤并执行
        stmt = self._apply_filters(stmt, filters)
        result = db.execute(stmt)

        # 3. 返回是否存在
        return (result.scalar() or 0) > 0

    # ==========================================================
    # Get
    # ==========================================================

    def get(
        self,
        ident: Any,
        db: Session,
        *,
        callback_success: Optional[Callable[[Optional[T]], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> Optional[T]:
        """
        根据主键获取对象
        :param ident: 主键值
        :param db: 数据库会话
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 查询到的对象或 None
        """
        try:
            # 1. 获取前钩子
            self._before_get(ident, db)

            # 2. 执行查询并后置处理
            obj = db.get(self.model, ident)
            obj = self._after_get(obj, db)

            # 3. 成功回调并返回
            if callback_success:
                callback_success(obj)
            return obj

        except Exception as e:
            # 4. 错误回调并抛出
            if callback_error:
                callback_error(e)
            raise

    # ==========================================================
    # Update
    # ==========================================================

    def update(
        self,
        ident: Any,
        values: Dict[str, Any],
        db: Session,
        *,
        refresh: bool = False,
        callback_success: Optional[Callable[[T], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> Optional[T]:
        """
        更新记录
        :param ident: 主键值
        :param values: 待更新字段和值
        :param db: 数据库会话
        :param refresh: 是否刷新对象
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 更新后的对象或 None
        """
        try:
            # 1. 获取目标对象
            obj = db.get(self.model, ident)
            if obj is None:
                return None

            # 2. 过滤空更新与主键字段
            if not values:
                return obj
            pk_columns = self._get_pk_columns()
            filtered_values = {
                k: v
                for k, v in values.items()
                if k not in pk_columns
            }
            if not filtered_values:
                return obj

            # 3. 更新前钩子与字段赋值
            self._before_update(obj, filtered_values, db)
            for key, value in filtered_values.items():
                if not hasattr(obj, key):
                    raise ValueError(f"invalid update field: {key}")
                setattr(obj, key, value)

            # 4. 持久化并可选刷新
            db.add(obj)
            db.flush()
            if refresh:
                db.refresh(obj)

            # 5. 更新后钩子与回调
            self._after_update(obj, filtered_values, db)
            if callback_success:
                callback_success(obj)
            return obj

        except Exception as e:
            # 6. 错误回调并抛出
            if callback_error:
                callback_error(e)
            raise

    # ==========================================================
    # Delete
    # ==========================================================

    def delete(
        self,
        ident: Any,
        db: Session,
        *,
        callback_success: Optional[Callable[[T], None]] = None,
        callback_error: Optional[Callable[[Exception], None]] = None,
    ) -> bool:
        """
        删除记录
        :param ident: 主键值
        :param db: 数据库会话
        :param callback_success: 成功回调
        :param callback_error: 失败回调
        :return: 是否删除成功
        """
        try:
            # 1. 获取目标对象
            obj = db.get(self.model, ident)
            if obj is None:
                return False

            # 2. 删除前钩子与删除操作
            self._before_delete(obj, db)
            db.delete(obj)
            db.flush()

            # 3. 删除后钩子与回调
            self._after_delete(obj, db)
            if callback_success:
                callback_success(obj)
            return True

        except Exception as e:
            # 4. 错误回调并抛出
            if callback_error:
                callback_error(e)
            raise

    # ==========================================================
    # Bulk Delete
    # ==========================================================
    def bulk_delete(
            self,
            field: str,
            ids: list,
            db: Session,
    ) -> int:
        """
        批量删除
        :param field: 删除字段
        :param ids: ID 列表
        :param db: 数据库会话
        :return: 影响行数
        """
        # 1. 空列表直接返回
        if not ids:
            return 0

        # 2. 获取字段
        column = getattr(self.model, field)

        # 3. 执行批量删除
        stmt = delete(self.model).where(column.in_(ids))
        result = db.execute(stmt)

        # 4. 返回影响行数
        return result.rowcount or 0
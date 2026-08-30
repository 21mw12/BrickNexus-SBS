from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.user.schema.RoleSchema import RoleAddSchema, RoleUpdateSchema, RoleQueryFilterSchema
from app.domain.user.schema.UserSchema import UserLoginSchema, UserAddSchema, UserUpdateSchema, UserQueryFilterSchema
from app.domain.user.schema.PageSchema import PageAddSchema
from app.domain.user.service.PageService import PageService
from app.domain.user.service.RoleService import RoleService
from app.domain.user.service.UserService import UserService
from app.infra.DB.SQLConnection import sql_manager


router = APIRouter(prefix="/user", tags=["user"])


# ==========================================================
# 登录相关API
# ==========================================================

@router.post("/login")
def login_user(
    login_data: UserLoginSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
):
    try:
        result = UserService.login_user(login_data, db=db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


@router.post("/logout")
def logout_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    try:
        token = authorization or ""
        ok = UserService.logout_user(token)
        if not ok:
            return Response.error_params("token not exists")
        return Response.success({"ok": True})
    except ValidationError as e:
        return Response.error_params(str(e))
    except Exception as e:
        return Response.error_system(str(e))


# ==========================================================
# 个人页面（当前登录用户信息）
# ==========================================================
@router.get("/account/me")
def get_my_profile(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
):
    try:
        result = UserService.get_my_profile(authorization or "", db)
        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


# ==========================================================
# 账号相关API
# ==========================================================

@router.post("/account/form")
def query_users_form(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: UserQueryFilterSchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:accounts"),
):
    try:
        result = UserService.query_users_form(db=db, page=page, limit=limit, filters=filters)

        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.post("/account/add")
def add_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_data: UserAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:accounts"),
):
    try:
        result = UserService.save_new_user(user_data, db=db)

        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.post("/account/edit/{user_id}")
def edit_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    user_data: UserUpdateSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:accounts"),
):
    try:
        result = UserService.alter_user_by_id(user_id, user_data, db=db)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_forbidden(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


@router.get("/account/find/{user_id}")
def find_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:accounts"),
):
    try:
        result = UserService.find_user_by_id(user_id, db=db)
        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.get("/account/drop/{user_id}")
def drop_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:accounts"),
):
    try:
        ok = UserService.drop_user_by_id(user_id, db=db)
        return Response.success({"ok": ok})
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.get("/account/resetPwd/{user_id}")
def reset_user_pwd(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:accounts"),
):
    try:
        ok = UserService.reset_user_pwd_by_id(user_id, db=db)

        return Response.success({"ok": ok})
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))

# ==========================================================
# 角色相关API
# ==========================================================

@router.post("/role/form")
def query_roles_form(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: RoleQueryFilterSchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        result = RoleService.query_roles_form(db=db, page=page, limit=limit, filters=filters)

        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.get("/role/find/{user_id}")
def find_role_by_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        result = RoleService.query_role_by_id(user_id, db=db)

        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.post("/role/add")
def add_role(
    authorization: str | None = Header(default=None, alias="Authorization"),
    role_data: RoleAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        result = RoleService.save_new_role(role_data, db=db)

        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.post("/role/edit/{user_id}")
def edit_role(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    role_data: RoleUpdateSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        result = RoleService.alter_role_by_id(user_id, role_data, db=db)

        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.get("/role/drop/{user_id}")
def drop_role(
    authorization: str | None = Header(default=None, alias="Authorization"),
    user_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        ok = RoleService.drop_role_by_id(user_id, db=db)
        
        return Response.success({"ok": ok})
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))

# ==========================================================
# 页面相关API
# ==========================================================

@router.get("/page/tree")
def query_pages_tree(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        result = PageService.query_pages_tree(db=db)
        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.post("/page/add")
def add_page(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page_data: PageAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        result = PageService.save_new_page(page_data, db=db)
        return Response.success(result)
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))


@router.get("/page/drop/{page_id}")
def drop_page(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("user", "user:roles"),
):
    try:
        ok = PageService.drop_page_by_id(page_id, db=db)
        return Response.success({"ok": ok})
    except ValidationError as e:
        return Response.error_forbidden(str(e))
    except Exception as e:
        return Response.error_system(str(e))
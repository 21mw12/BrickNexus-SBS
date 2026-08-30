from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.orm import Session

from app.infra.DB.SQLConnection import sql_manager
from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.channel.schema.ChannelSchema import (
    HttpChannelAddSchema,
    HttpChannelEditSchema,
    HttpChannelQuerySchema,
    MqttChannelAddSchema,
    MqttChannelEditSchema,
    MqttChannelQuerySchema,
)
from app.domain.channel.service.ChannelService import ChannelService


router = APIRouter(prefix="/channel", tags=["channel"])


# ==========================================================
# MQTT 通道分页查询
# ==========================================================
@router.post("/mqtt/list")
def mqtt_list(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: MqttChannelQuerySchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.list_mqtt(db, page, limit, filters)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 查询单个 MQTT 通道
# ==========================================================
@router.get("/mqtt/find/{channel_mqtt_id}")
def mqtt_find(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_mqtt_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.find_mqtt(db, channel_mqtt_id)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 新增 MQTT 通道
# ==========================================================
@router.post("/mqtt/add")
def mqtt_add(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_data: MqttChannelAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.add_mqtt(db, channel_data)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 修改 MQTT 通道
# ==========================================================
@router.post("/mqtt/edit/{channel_mqtt_id}")
def mqtt_edit(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_mqtt_id: str = Path(...),
    channel_data: MqttChannelEditSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.edit_mqtt(db, channel_mqtt_id, channel_data)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 删除 MQTT 通道
# ==========================================================
@router.get("/mqtt/drop/{channel_mqtt_id}")
def mqtt_drop(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_mqtt_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        ok = ChannelService.drop_mqtt(db, channel_mqtt_id)
        db.commit()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# HTTP 通道分页查询
# ==========================================================
@router.post("/http/list")
def http_list(
    authorization: str | None = Header(default=None, alias="Authorization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    filters: HttpChannelQuerySchema | None = Body(None),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.list_http(db, page, limit, filters)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 查询单个 HTTP 通道
# ==========================================================
@router.get("/http/find/{channel_http_id}")
def http_find(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_http_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.find_http(db, channel_http_id)
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 新增 HTTP 通道
# ==========================================================
@router.post("/http/add")
def http_add(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_data: HttpChannelAddSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.add_http(db, channel_data)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 修改 HTTP 通道
# ==========================================================
@router.post("/http/edit/{channel_http_id}")
def http_edit(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_http_id: str = Path(...),
    channel_data: HttpChannelEditSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = ChannelService.edit_http(db, channel_http_id, channel_data)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 删除 HTTP 通道
# ==========================================================
@router.get("/http/drop/{channel_http_id}")
def http_drop(
    authorization: str | None = Header(default=None, alias="Authorization"),
    channel_http_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        ok = ChannelService.drop_http(db, channel_http_id)
        db.commit()
        return Response.success({"ok": ok})
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 通道配置选项
# ==========================================================
@router.get("/options")
def channel_options(
    authorization: str | None = Header(default=None, alias="Authorization"),
    _auth: None = require_page(
        "channel", "channel:requests", "channel:controls"
    ),
):
    try:
        return Response.success(ChannelService.options())
    except ValidationError as e:
        return Response.error_params(str(e))
    except Exception as e:
        return Response.error_system(str(e))

from fastapi import APIRouter, Body, Depends, Header, Path
from sqlalchemy.orm import Session

from app.infra.DB.SQLConnection import sql_manager
from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.AuthDecorator import require_page
from app.domain.channel.schema.TerminalRequestSchema import TerminalTreeEditSchema
from app.domain.channel.service.TerminalRequestService import TerminalRequestService

router = APIRouter(prefix="/terminal_request", tags=["terminal_request"])


# ==========================================================
# 查询终端测点树
# ==========================================================

@router.get("/tree/{terminal_id}")
def get_terminal_sensor_tree(
    authorization: str | None = Header(default=None, alias="Authorization"),
    terminal_id: str = Path(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = TerminalRequestService.get_tree(terminal_id, db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))


# ==========================================================
# 编辑终端测点树
# ==========================================================

@router.post("/edit/{terminal_id}")
def edit_terminal_sensor_tree(
    authorization: str | None = Header(default=None, alias="Authorization"),
    terminal_id: str = Path(...),
    data: TerminalTreeEditSchema = Body(...),
    db: Session = Depends(sql_manager.get_db_dep("main")),
    _auth: None = require_page("channel", "channel:requests"),
):
    try:
        result = TerminalRequestService.update_tree(terminal_id, data, db)
        db.commit()
        return Response.success(result)
    except ValidationError as e:
        db.rollback()
        return Response.error_params(str(e))
    except Exception as e:
        db.rollback()
        return Response.error_system(str(e))

"""Dashboard overview API."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.common.Response import Response
from app.common.validators import ValidationError
from app.domain.common.PermissionChecker import (
    check_page_permission,
    get_viewable_asset_ids,
)
from app.domain.dashboard.service import DashboardService
from app.infra.DB.SQLConnection import sql_manager


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
def get_dashboard_overview(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(sql_manager.get_db_dep("main")),
):
    """Return permitted page descriptions and dashboard statistics."""

    try:
        token = authorization or ""
        viewable_asset_ids = get_viewable_asset_ids(token, db)
        permitted_page_codes = {
            page["key"]
            for page in DashboardService.PAGES
            if check_page_permission(token, [page["key"]])
        }
        result = DashboardService.get_overview(
            db,
            permitted_page_codes,
            viewable_asset_ids,
        )
        return Response.success(result)
    except ValidationError as exc:
        return Response.error_forbidden(str(exc))
    except Exception as exc:
        return Response.error_system(str(exc))

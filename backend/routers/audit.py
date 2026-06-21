from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from database import get_db
from schemas import (
    AuditLogResponse,
    AuditLogListResponse,
)
from services import audit_service

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    operation_type: Optional[str] = Query(None, description="操作类型: publish/consume/ack/reject"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    keyword: Optional[str] = Query(None, description="关键字搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
):
    items, total = audit_service.list_audit_logs(
        db=db,
        operation_type=operation_type,
        start_time=start_time,
        end_time=end_time,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/logs/{log_id}", response_model=AuditLogResponse)
def get_audit_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
):
    log = audit_service.get_audit_log(db=db, log_id=log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return log


@router.get("/stats")
def get_audit_stats(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db),
):
    stats = audit_service.get_operation_stats(
        db=db,
        start_time=start_time,
        end_time=end_time,
    )
    return stats

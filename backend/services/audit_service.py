import json
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime

from models import MessageAuditLog


def _generate_message_id(payload: str) -> str:
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _truncate_summary(text: str, max_length: int = 200) -> str:
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _safe_json_dumps(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if data is None:
        return None
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return str(data)


def _safe_json_loads(text: Optional[str]) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def create_audit_log(
    db: Session,
    operation_type: str,
    operator: str = "system",
    target_exchange: Optional[str] = None,
    routing_key: Optional[str] = None,
    queue_name: Optional[str] = None,
    message_id: Optional[str] = None,
    message_body: Optional[str] = None,
    headers: Optional[Dict[str, Any]] = None,
    properties: Optional[Dict[str, Any]] = None,
    delivery_tag: Optional[int] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> MessageAuditLog:
    summary = _truncate_summary(message_body or "", 200)
    if not message_id and message_body:
        message_id = _generate_message_id(message_body)

    log = MessageAuditLog(
        operation_type=operation_type,
        operator=operator,
        target_exchange=target_exchange,
        routing_key=routing_key,
        queue_name=queue_name,
        message_id=message_id,
        message_summary=summary,
        message_body=message_body,
        headers=_safe_json_dumps(headers),
        properties=_safe_json_dumps(properties),
        delivery_tag=delivery_tag,
        status=status,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_audit_log(
    db: Session,
    log_id: int,
) -> Optional[MessageAuditLog]:
    log = db.query(MessageAuditLog).filter(MessageAuditLog.id == log_id).first()
    if log and log.headers:
        log.headers = _safe_json_loads(log.headers)
    if log and log.properties:
        log.properties = _safe_json_loads(log.properties)
    return log


def list_audit_logs(
    db: Session,
    operation_type: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[MessageAuditLog], int]:
    query = db.query(MessageAuditLog)

    filters = []
    if operation_type:
        filters.append(MessageAuditLog.operation_type == operation_type)
    if start_time:
        filters.append(MessageAuditLog.created_at >= start_time)
    if end_time:
        filters.append(MessageAuditLog.created_at <= end_time)
    if keyword:
        keyword_like = f"%{keyword}%"
        filters.append(
            or_(
                MessageAuditLog.message_id.like(keyword_like),
                MessageAuditLog.message_summary.like(keyword_like),
                MessageAuditLog.target_exchange.like(keyword_like),
                MessageAuditLog.routing_key.like(keyword_like),
                MessageAuditLog.queue_name.like(keyword_like),
                MessageAuditLog.operator.like(keyword_like),
            )
        )

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()

    items = (
        query.order_by(MessageAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    for item in items:
        if item.headers:
            item.headers = _safe_json_loads(item.headers)
        if item.properties:
            item.properties = _safe_json_loads(item.properties)

    return items, total


def get_operation_stats(
    db: Session,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Dict[str, int]:
    query = db.query(MessageAuditLog.operation_type, MessageAuditLog.id)

    filters = []
    if start_time:
        filters.append(MessageAuditLog.created_at >= start_time)
    if end_time:
        filters.append(MessageAuditLog.created_at <= end_time)
    if filters:
        query = query.filter(and_(*filters))

    results = query.all()

    stats = {
        "publish": 0,
        "consume": 0,
        "ack": 0,
        "reject": 0,
        "total": len(results),
    }
    for op_type, _ in results:
        if op_type in stats:
            stats[op_type] += 1

    return stats

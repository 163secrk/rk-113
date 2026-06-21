from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from schemas import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertRecordResponse,
    AlertListResponse,
    AlertEvaluateRequest,
)
from services import alert_service
from services import config_service
from services.rabbitmq_service import monitor

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/rules", response_model=list[AlertRuleResponse])
def list_rules(enabled_only: bool = False, db: Session = Depends(get_db)):
    return alert_service.list_alert_rules(db, enabled_only=enabled_only)


@router.post("/rules", response_model=AlertRuleResponse)
def create_rule(rule_in: AlertRuleCreate, db: Session = Depends(get_db)):
    if rule_in.condition_type not in alert_service.VALID_CONDITION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid condition_type. Must be one of: {', '.join(alert_service.VALID_CONDITION_TYPES)}",
        )
    if rule_in.level not in alert_service.VALID_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(alert_service.VALID_LEVELS)}",
        )
    if rule_in.threshold < 0:
        raise HTTPException(status_code=400, detail="Threshold must be non-negative")
    if not rule_in.name.strip():
        raise HTTPException(status_code=400, detail="Rule name is required")
    if not rule_in.queue_name.strip():
        raise HTTPException(status_code=400, detail="Queue name is required")
    return alert_service.create_alert_rule(db, rule_in)


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = alert_service.get_alert_rule(db, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
def update_rule(rule_id: int, update_in: AlertRuleUpdate, db: Session = Depends(get_db)):
    if update_in.condition_type is not None and update_in.condition_type not in alert_service.VALID_CONDITION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid condition_type. Must be one of: {', '.join(alert_service.VALID_CONDITION_TYPES)}",
        )
    if update_in.level is not None and update_in.level not in alert_service.VALID_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid level. Must be one of: {', '.join(alert_service.VALID_LEVELS)}",
        )
    if update_in.threshold is not None and update_in.threshold < 0:
        raise HTTPException(status_code=400, detail="Threshold must be non-negative")
    rule = alert_service.update_alert_rule(db, rule_id, update_in)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    if not alert_service.delete_alert_rule(db, rule_id):
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"success": True, "message": "Alert rule deleted successfully"}


@router.get("/records", response_model=AlertListResponse)
def list_records(
    status: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items = alert_service.list_alert_records(db, status=status, level=level, limit=limit)
    total = alert_service.count_alert_records(db, status=status, level=level)
    return {"items": items, "total": total}


@router.post("/records/{record_id}/acknowledge", response_model=AlertRecordResponse)
def acknowledge_record(record_id: int, db: Session = Depends(get_db)):
    record = alert_service.acknowledge_alert(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Alert record not found")
    return record


@router.post("/records/{record_id}/close", response_model=AlertRecordResponse)
def close_record(record_id: int, db: Session = Depends(get_db)):
    record = alert_service.close_alert(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Alert record not found")
    return record


@router.post("/evaluate", response_model=list[AlertRecordResponse])
def evaluate_alerts_now(db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    queues = monitor.list_queues() or []
    triggered = alert_service.evaluate_alerts(db, queues)
    return triggered


@router.get("/condition-types")
def get_condition_types():
    return [
        {"value": ct, "label": alert_service.CONDITION_LABELS.get(ct, ct)}
        for ct in alert_service.VALID_CONDITION_TYPES
    ]


@router.get("/levels")
def get_levels():
    return [
        {"value": lv, "label": alert_service.LEVEL_LABELS.get(lv, lv)}
        for lv in alert_service.VALID_LEVELS
    ]

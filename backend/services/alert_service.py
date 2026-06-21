from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import models
import schemas


VALID_CONDITION_TYPES = [
    "ready_gt",
    "unacked_gt",
    "consumers_eq_0",
    "rate_gt",
]

VALID_LEVELS = ["warning", "critical"]

CONDITION_LABELS = {
    "ready_gt": "Ready消息数 > N",
    "unacked_gt": "Unacked消息数 > N",
    "consumers_eq_0": "消费者数量 = 0",
    "rate_gt": "消息速率 > N条/秒",
}

LEVEL_LABELS = {
    "warning": "警告",
    "critical": "严重",
}


def _check_condition(condition_type: str, threshold: float, queue_data: Dict[str, Any]) -> Optional[float]:
    if condition_type == "ready_gt":
        value = float(queue_data.get("ready", 0))
        if value > threshold:
            return value
    elif condition_type == "unacked_gt":
        value = float(queue_data.get("unacked", 0))
        if value > threshold:
            return value
    elif condition_type == "consumers_eq_0":
        value = float(queue_data.get("consumers", 0))
        if value == 0:
            return value
    elif condition_type == "rate_gt":
        message_stats = queue_data.get("message_stats", {})
        publish_details = message_stats.get("publish_details", {}) if isinstance(message_stats, dict) else {}
        rate = float(publish_details.get("rate", 0.0)) if isinstance(publish_details, dict) else 0.0
        if rate > threshold:
            return rate
    return None


def _build_alert_message(rule: models.AlertRule, current_value: float) -> str:
    condition_desc = CONDITION_LABELS.get(rule.condition_type, rule.condition_type)
    return f"队列 [{rule.queue_name}] 触发告警规则 [{rule.name}]：{condition_desc}，阈值={rule.threshold}，当前值={current_value}"


def create_alert_rule(db: Session, rule_in: schemas.AlertRuleCreate) -> models.AlertRule:
    rule = models.AlertRule(
        name=rule_in.name,
        queue_name=rule_in.queue_name,
        condition_type=rule_in.condition_type,
        threshold=rule_in.threshold,
        level=rule_in.level,
        enabled=rule_in.enabled,
        description=rule_in.description,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def get_alert_rule(db: Session, rule_id: int) -> Optional[models.AlertRule]:
    return db.query(models.AlertRule).filter(models.AlertRule.id == rule_id).first()


def list_alert_rules(db: Session, enabled_only: bool = False) -> List[models.AlertRule]:
    query = db.query(models.AlertRule)
    if enabled_only:
        query = query.filter(models.AlertRule.enabled == True)
    return query.order_by(desc(models.AlertRule.created_at)).all()


def update_alert_rule(db: Session, rule_id: int, update_in: schemas.AlertRuleUpdate) -> Optional[models.AlertRule]:
    rule = get_alert_rule(db, rule_id)
    if not rule:
        return None
    update_data = update_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_alert_rule(db: Session, rule_id: int) -> bool:
    rule = get_alert_rule(db, rule_id)
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def create_alert_record(
    db: Session,
    rule: models.AlertRule,
    current_value: float,
) -> models.AlertRecord:
    existing = (
        db.query(models.AlertRecord)
        .filter(
            models.AlertRecord.rule_id == rule.id,
            models.AlertRecord.status == "active",
            models.AlertRecord.queue_name == rule.queue_name,
            models.AlertRecord.condition_type == rule.condition_type,
        )
        .first()
    )
    if existing:
        existing.current_value = current_value
        existing.created_at = datetime.now()
        db.commit()
        db.refresh(existing)
        return existing

    record = models.AlertRecord(
        rule_id=rule.id,
        rule_name=rule.name,
        queue_name=rule.queue_name,
        condition_type=rule.condition_type,
        threshold=rule.threshold,
        current_value=current_value,
        level=rule.level,
        status="active",
        message=_build_alert_message(rule, current_value),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_alert_records(
    db: Session,
    status: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 200,
) -> List[models.AlertRecord]:
    query = db.query(models.AlertRecord)
    if status:
        query = query.filter(models.AlertRecord.status == status)
    if level:
        query = query.filter(models.AlertRecord.level == level)
    return query.order_by(desc(models.AlertRecord.created_at)).limit(limit).all()


def count_alert_records(
    db: Session,
    status: Optional[str] = None,
    level: Optional[str] = None,
) -> int:
    query = db.query(models.AlertRecord)
    if status:
        query = query.filter(models.AlertRecord.status == status)
    if level:
        query = query.filter(models.AlertRecord.level == level)
    return query.count()


def get_alert_record(db: Session, record_id: int) -> Optional[models.AlertRecord]:
    return db.query(models.AlertRecord).filter(models.AlertRecord.id == record_id).first()


def acknowledge_alert(db: Session, record_id: int, operator: str = "web-user") -> Optional[models.AlertRecord]:
    record = get_alert_record(db, record_id)
    if not record:
        return None
    record.status = "acknowledged"
    record.acknowledged_by = operator
    record.acknowledged_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def resolve_alert(db: Session, record_id: int) -> Optional[models.AlertRecord]:
    record = get_alert_record(db, record_id)
    if not record:
        return None
    record.status = "resolved"
    record.resolved_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def close_alert(db: Session, record_id: int, operator: str = "web-user") -> Optional[models.AlertRecord]:
    record = get_alert_record(db, record_id)
    if not record:
        return None
    record.status = "closed"
    record.acknowledged_by = operator
    record.acknowledged_at = datetime.now()
    record.resolved_at = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def evaluate_alerts(db: Session, queues: List[Dict[str, Any]]) -> List[models.AlertRecord]:
    rules = list_alert_rules(db, enabled_only=True)
    if not rules or not queues:
        return []

    queue_map = {q.get("name"): q for q in queues if isinstance(q, dict)}
    triggered: List[models.AlertRecord] = []

    for rule in rules:
        queue_data = queue_map.get(rule.queue_name)
        if queue_data is None:
            continue

        current_value = _check_condition(rule.condition_type, rule.threshold, queue_data)
        if current_value is not None:
            record = create_alert_record(db, rule, current_value)
            triggered.append(record)
        else:
            actives = (
                db.query(models.AlertRecord)
                .filter(
                    models.AlertRecord.rule_id == rule.id,
                    models.AlertRecord.queue_name == rule.queue_name,
                    models.AlertRecord.condition_type == rule.condition_type,
                    models.AlertRecord.status == "active",
                )
                .all()
            )
            for rec in actives:
                rec.status = "resolved"
                rec.resolved_at = datetime.now()
            if actives:
                db.commit()

    return triggered


def resolve_all_auto(db: Session, queues: List[Dict[str, Any]]) -> int:
    rules = list_alert_rules(db, enabled_only=True)
    if not rules or not queues:
        return 0

    queue_map = {q.get("name"): q for q in queues if isinstance(q, dict)}
    resolved_count = 0

    for rule in rules:
        queue_data = queue_map.get(rule.queue_name)
        if queue_data is None:
            continue

        current_value = _check_condition(rule.condition_type, rule.threshold, queue_data)
        if current_value is None:
            actives = (
                db.query(models.AlertRecord)
                .filter(
                    models.AlertRecord.rule_id == rule.id,
                    models.AlertRecord.queue_name == rule.queue_name,
                    models.AlertRecord.condition_type == rule.condition_type,
                    models.AlertRecord.status == "active",
                )
                .all()
            )
            for rec in actives:
                rec.status = "resolved"
                rec.resolved_at = datetime.now()
                resolved_count += 1
            if actives:
                db.commit()

    return resolved_count

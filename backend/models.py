from sqlalchemy import Column, Integer, String, Text, DateTime, Index, Boolean, Float
from sqlalchemy.sql import func
from database import Base


class OpsConfig(Base):
    __tablename__ = "ops_config"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class MessageAuditLog(Base):
    __tablename__ = "message_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    operation_type = Column(String(20), nullable=False, index=True)
    operator = Column(String(100), nullable=False, default="system")
    target_exchange = Column(String(255), nullable=True, index=True)
    routing_key = Column(String(255), nullable=True, index=True)
    queue_name = Column(String(255), nullable=True, index=True)
    message_id = Column(String(255), nullable=True, index=True)
    message_summary = Column(String(500), nullable=True)
    message_body = Column(Text, nullable=True)
    headers = Column(Text, nullable=True)
    properties = Column(Text, nullable=True)
    delivery_tag = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_audit_operation_type", "operation_type"),
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_exchange", "target_exchange"),
        Index("idx_audit_queue", "queue_name"),
    )


class AlertRule(Base):
    __tablename__ = "alert_rule"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(200), nullable=False)
    queue_name = Column(String(255), nullable=False, index=True)
    condition_type = Column(String(50), nullable=False)
    threshold = Column(Float, nullable=False)
    level = Column(String(20), nullable=False, default="warning")
    enabled = Column(Boolean, nullable=False, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_alert_rule_queue", "queue_name"),
        Index("idx_alert_rule_enabled", "enabled"),
    )


class AlertRecord(Base):
    __tablename__ = "alert_record"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    rule_id = Column(Integer, nullable=False, index=True)
    rule_name = Column(String(200), nullable=False)
    queue_name = Column(String(255), nullable=False, index=True)
    condition_type = Column(String(50), nullable=False)
    threshold = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    level = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_alert_record_queue", "queue_name"),
        Index("idx_alert_record_status", "status"),
        Index("idx_alert_record_created", "created_at"),
    )

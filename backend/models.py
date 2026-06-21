from sqlalchemy import Column, Integer, String, Text, DateTime, Index
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

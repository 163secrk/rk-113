from sqlalchemy.orm import Session
from models import OpsConfig
from schemas import OpsConfigCreate, OpsConfigUpdate
from typing import List, Optional


DEFAULT_CONFIGS = [
    {"config_key": "rabbitmq_host", "config_value": "localhost", "description": "RabbitMQ 主机地址"},
    {"config_key": "rabbitmq_port", "config_value": "5672", "description": "RabbitMQ AMQP 端口"},
    {"config_key": "rabbitmq_username", "config_value": "admin", "description": "RabbitMQ 用户名"},
    {"config_key": "rabbitmq_password", "config_value": "admin123", "description": "RabbitMQ 密码"},
    {"config_key": "rabbitmq_vhost", "config_value": "/", "description": "RabbitMQ 虚拟主机"},
]


def init_default_configs(db: Session) -> None:
    for cfg in DEFAULT_CONFIGS:
        existing = db.query(OpsConfig).filter(OpsConfig.config_key == cfg["config_key"]).first()
        if not existing:
            db.add(OpsConfig(**cfg))
    db.commit()


def get_all_configs(db: Session) -> List[OpsConfig]:
    return db.query(OpsConfig).order_by(OpsConfig.id).all()


def get_config_by_key(db: Session, key: str) -> Optional[OpsConfig]:
    return db.query(OpsConfig).filter(OpsConfig.config_key == key).first()


def get_config_by_id(db: Session, config_id: int) -> Optional[OpsConfig]:
    return db.query(OpsConfig).filter(OpsConfig.id == config_id).first()


def create_config(db: Session, data: OpsConfigCreate) -> OpsConfig:
    cfg = OpsConfig(**data.model_dump())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def update_config(db: Session, config_id: int, data: OpsConfigUpdate) -> Optional[OpsConfig]:
    cfg = get_config_by_id(db, config_id)
    if not cfg:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg


def delete_config(db: Session, config_id: int) -> bool:
    cfg = get_config_by_id(db, config_id)
    if not cfg:
        return False
    db.delete(cfg)
    db.commit()
    return True


def get_rabbitmq_config(db: Session) -> dict:
    keys = ["rabbitmq_host", "rabbitmq_port", "rabbitmq_username", "rabbitmq_password", "rabbitmq_vhost"]
    result = {}
    for k in keys:
        cfg = get_config_by_key(db, k)
        if cfg:
            result[k] = cfg.config_value
    result.setdefault("rabbitmq_host", "localhost")
    result.setdefault("rabbitmq_port", "5672")
    result.setdefault("rabbitmq_username", "admin")
    result.setdefault("rabbitmq_password", "admin123")
    result.setdefault("rabbitmq_vhost", "/")
    return result

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import time
from database import get_db
from schemas import RabbitMQOverview, ConnectionStatus, HealthResponse
from services.rabbitmq_service import monitor
from services import config_service

router = APIRouter(prefix="/api", tags=["monitor"])


@router.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "timestamp": int(time.time() * 1000)}


@router.get("/rabbitmq/connection/status", response_model=ConnectionStatus)
def connection_status(db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    return monitor.get_connection_status()


@router.get("/rabbitmq/overview", response_model=RabbitMQOverview)
def rabbitmq_overview(db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    return monitor.get_overview()

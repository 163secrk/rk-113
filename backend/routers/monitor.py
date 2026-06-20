from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time
from database import get_db
from schemas import (
    RabbitMQOverview,
    ConnectionStatus,
    HealthResponse,
    QueueListItem,
    QueueDetail,
    CreateQueueRequest,
    OperationResponse,
)
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


@router.get("/rabbitmq/queues", response_model=list[QueueListItem])
def list_queues(db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    queues = monitor.list_queues()
    if queues is None:
        raise HTTPException(status_code=500, detail="Failed to fetch queues from RabbitMQ")
    return queues


@router.get("/rabbitmq/queues/{queue_name}", response_model=QueueDetail)
def get_queue(queue_name: str, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    detail = monitor.get_queue_detail(queue_name)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Queue '{queue_name}' not found")
    return detail


@router.post("/rabbitmq/queues", response_model=OperationResponse)
def create_queue(request: CreateQueueRequest, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    if not request.name:
        raise HTTPException(status_code=400, detail="Queue name is required")
    success = monitor.create_queue(
        queue_name=request.name,
        durable=request.durable if request.durable is not None else True,
        auto_delete=request.auto_delete if request.auto_delete is not None else False,
        exclusive=request.exclusive if request.exclusive is not None else False,
        arguments=request.arguments,
    )
    if success:
        return {"success": True, "message": f"Queue '{request.name}' created successfully"}
    raise HTTPException(status_code=500, detail=f"Failed to create queue '{request.name}'")


@router.post("/rabbitmq/queues/{queue_name}/purge", response_model=OperationResponse)
def purge_queue(queue_name: str, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    success = monitor.purge_queue(queue_name)
    if success:
        return {"success": True, "message": f"Queue '{queue_name}' purged successfully"}
    raise HTTPException(status_code=500, detail=f"Failed to purge queue '{queue_name}'")


@router.delete("/rabbitmq/queues/{queue_name}", response_model=OperationResponse)
def delete_queue(queue_name: str, if_unused: bool = False, if_empty: bool = False, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    success = monitor.delete_queue(queue_name, if_unused=if_unused, if_empty=if_empty)
    if success:
        return {"success": True, "message": f"Queue '{queue_name}' deleted successfully"}
    raise HTTPException(status_code=500, detail=f"Failed to delete queue '{queue_name}'")

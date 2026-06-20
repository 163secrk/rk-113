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
    ExchangeListItem,
    ExchangeDetail,
    CreateExchangeRequest,
    CreateBindingRequest,
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


@router.get("/rabbitmq/exchanges", response_model=list[ExchangeListItem])
def list_exchanges(db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    exchanges = monitor.list_exchanges()
    if exchanges is None:
        raise HTTPException(status_code=500, detail="Failed to fetch exchanges from RabbitMQ")
    return exchanges


@router.get("/rabbitmq/exchanges/{exchange_name}", response_model=ExchangeDetail)
def get_exchange(exchange_name: str, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    detail = monitor.get_exchange_detail(exchange_name)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Exchange '{exchange_name}' not found")
    return detail


@router.post("/rabbitmq/exchanges", response_model=OperationResponse)
def create_exchange(request: CreateExchangeRequest, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    if not request.name:
        raise HTTPException(status_code=400, detail="Exchange name is required")
    if not request.type:
        raise HTTPException(status_code=400, detail="Exchange type is required")
    valid_types = ["direct", "topic", "fanout", "headers"]
    if request.type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid exchange type. Must be one of: {', '.join(valid_types)}")
    success = monitor.create_exchange(
        exchange_name=request.name,
        exchange_type=request.type,
        durable=request.durable if request.durable is not None else True,
        auto_delete=request.auto_delete if request.auto_delete is not None else False,
        internal=request.internal if request.internal is not None else False,
        arguments=request.arguments,
    )
    if success:
        return {"success": True, "message": f"Exchange '{request.name}' created successfully"}
    raise HTTPException(status_code=500, detail=f"Failed to create exchange '{request.name}'")


@router.delete("/rabbitmq/exchanges/{exchange_name}", response_model=OperationResponse)
def delete_exchange(exchange_name: str, if_unused: bool = False, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    success = monitor.delete_exchange(exchange_name, if_unused=if_unused)
    if success:
        return {"success": True, "message": f"Exchange '{exchange_name}' deleted successfully"}
    raise HTTPException(status_code=500, detail=f"Failed to delete exchange '{exchange_name}'")


@router.post("/rabbitmq/exchanges/{exchange_name}/bindings", response_model=OperationResponse)
def create_binding(exchange_name: str, request: CreateBindingRequest, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    if not request.destination:
        raise HTTPException(status_code=400, detail="Destination is required")
    success = monitor.create_binding(
        exchange_name=exchange_name,
        destination=request.destination,
        destination_type=request.destination_type if request.destination_type else "queue",
        routing_key=request.routing_key if request.routing_key else "",
        arguments=request.arguments,
    )
    if success:
        return {"success": True, "message": "Binding created successfully"}
    raise HTTPException(status_code=500, detail="Failed to create binding")


@router.delete("/rabbitmq/exchanges/{exchange_name}/bindings", response_model=OperationResponse)
def delete_binding(
    exchange_name: str,
    destination: str,
    destination_type: str = "queue",
    properties_key: str = "",
    db: Session = Depends(get_db),
):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    success = monitor.delete_binding(
        exchange_name=exchange_name,
        destination=destination,
        destination_type=destination_type,
        properties_key=properties_key,
    )
    if success:
        return {"success": True, "message": "Binding deleted successfully"}
    raise HTTPException(status_code=500, detail="Failed to delete binding")

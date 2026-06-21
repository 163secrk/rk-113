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
    PublishMessageRequest,
    PublishMessageResponse,
    QueueMessageListResponse,
    MessageOperationRequest,
    MessageOperationResponse,
    RepublishRequest,
    CheckQueueExistsResponse,
    DeadLetterInfo,
)
from services.rabbitmq_service import monitor
from services import config_service
from services import audit_service

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


@router.post("/rabbitmq/messages/publish", response_model=PublishMessageResponse)
def publish_message(request: PublishMessageRequest, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)

    if not request.target_type:
        raise HTTPException(status_code=400, detail="target_type is required")
    if request.target_type not in ("exchange", "queue"):
        raise HTTPException(status_code=400, detail="target_type must be 'exchange' or 'queue'")
    if not request.target_name:
        raise HTTPException(status_code=400, detail="target_name is required")
    if request.payload is None:
        raise HTTPException(status_code=400, detail="payload is required")

    count = monitor.publish_message(
        target_type=request.target_type,
        target_name=request.target_name,
        routing_key=request.routing_key or "",
        payload=request.payload,
        headers=request.headers,
        content_encoding=request.content_encoding,
        delivery_mode=request.delivery_mode if request.delivery_mode is not None else 2,
        priority=request.priority if request.priority is not None else 0,
        content_type=request.content_type or "application/json",
    )

    exchange_name = request.target_name if request.target_type == "exchange" else ""
    queue_name = request.target_name if request.target_type == "queue" else None
    routing_key = request.routing_key if request.target_type == "exchange" else request.target_name

    properties = {
        "content_type": request.content_type,
        "content_encoding": request.content_encoding,
        "delivery_mode": request.delivery_mode,
        "priority": request.priority,
    }

    if count is not None:
        audit_service.create_audit_log(
            db=db,
            operation_type="publish",
            operator="web-user",
            target_exchange=exchange_name or None,
            routing_key=routing_key,
            queue_name=queue_name,
            message_body=request.payload,
            headers=request.headers,
            properties=properties,
            status="success",
        )
        return {
            "success": True,
            "message": f"Message published to {request.target_type} '{request.target_name}' successfully",
            "published_count": count,
        }
    else:
        audit_service.create_audit_log(
            db=db,
            operation_type="publish",
            operator="web-user",
            target_exchange=exchange_name or None,
            routing_key=routing_key,
            queue_name=queue_name,
            message_body=request.payload,
            headers=request.headers,
            properties=properties,
            status="failed",
            error_message=f"Failed to publish message to {request.target_type} '{request.target_name}'",
        )
    raise HTTPException(status_code=500, detail=f"Failed to publish message to {request.target_type} '{request.target_name}'")


@router.get("/rabbitmq/queues/{queue_name}/messages", response_model=QueueMessageListResponse)
def get_queue_messages(
    queue_name: str,
    limit: int = 50,
    requeue: bool = True,
    db: Session = Depends(get_db),
):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)

    if not queue_name:
        raise HTTPException(status_code=400, detail="queue_name is required")
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")
    if limit > 500:
        limit = 500

    result = monitor.get_queue_messages(
        queue_name=queue_name,
        limit=limit,
        requeue=requeue,
    )

    if result is not None:
        if not requeue:
            messages = result.get("messages", [])
            for msg in messages:
                audit_service.create_audit_log(
                    db=db,
                    operation_type="consume",
                    operator="web-user",
                    target_exchange=msg.get("exchange"),
                    routing_key=msg.get("routing_key"),
                    queue_name=queue_name,
                    message_id=msg.get("properties", {}).get("message_id"),
                    message_body=msg.get("payload"),
                    headers=msg.get("headers"),
                    properties=msg.get("properties"),
                    delivery_tag=msg.get("delivery_tag"),
                    status="success",
                )
        return result
    raise HTTPException(status_code=500, detail=f"Failed to get messages from queue '{queue_name}'")


@router.post("/rabbitmq/queues/{queue_name}/messages/ack", response_model=MessageOperationResponse)
def ack_message(queue_name: str, request: MessageOperationRequest, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)

    if not queue_name:
        raise HTTPException(status_code=400, detail="queue_name is required")
    if request.delivery_tag is None:
        raise HTTPException(status_code=400, detail="delivery_tag is required")

    success = monitor.ack_message(
        queue_name=queue_name,
        delivery_tag=request.delivery_tag,
    )

    if success:
        audit_service.create_audit_log(
            db=db,
            operation_type="ack",
            operator="web-user",
            queue_name=queue_name,
            delivery_tag=request.delivery_tag,
            status="success",
        )
        return {"success": True, "message": f"Message with delivery_tag {request.delivery_tag} acknowledged successfully"}
    else:
        audit_service.create_audit_log(
            db=db,
            operation_type="ack",
            operator="web-user",
            queue_name=queue_name,
            delivery_tag=request.delivery_tag,
            status="failed",
            error_message=f"Failed to ack message with delivery_tag {request.delivery_tag}",
        )
    raise HTTPException(status_code=500, detail=f"Failed to ack message with delivery_tag {request.delivery_tag}")


@router.post("/rabbitmq/queues/{queue_name}/messages/reject", response_model=MessageOperationResponse)
def reject_message(queue_name: str, request: MessageOperationRequest, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)

    if not queue_name:
        raise HTTPException(status_code=400, detail="queue_name is required")
    if request.delivery_tag is None:
        raise HTTPException(status_code=400, detail="delivery_tag is required")

    success = monitor.reject_message(
        queue_name=queue_name,
        delivery_tag=request.delivery_tag,
        requeue=request.requeue if request.requeue is not None else False,
    )

    requeue_val = request.requeue if request.requeue is not None else False
    action = "requeued" if requeue_val else "discarded"

    if success:
        audit_service.create_audit_log(
            db=db,
            operation_type="reject",
            operator="web-user",
            queue_name=queue_name,
            delivery_tag=request.delivery_tag,
            status="success",
            error_message=f"reject action: {action}",
        )
        return {"success": True, "message": f"Message with delivery_tag {request.delivery_tag} rejected ({action}) successfully"}
    else:
        audit_service.create_audit_log(
            db=db,
            operation_type="reject",
            operator="web-user",
            queue_name=queue_name,
            delivery_tag=request.delivery_tag,
            status="failed",
            error_message=f"Failed to reject message with delivery_tag {request.delivery_tag}",
        )
    raise HTTPException(status_code=500, detail=f"Failed to reject message with delivery_tag {request.delivery_tag}")


@router.get("/rabbitmq/queues/{queue_name}/exists", response_model=CheckQueueExistsResponse)
def check_queue_exists(queue_name: str, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)
    exists = monitor.check_queue_exists(queue_name)
    return {"exists": exists, "queue_name": queue_name}


@router.post("/rabbitmq/queues/{queue_name}/messages/republish", response_model=OperationResponse)
def republish_dead_letter(
    queue_name: str,
    request: RepublishRequest,
    db: Session = Depends(get_db),
):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)

    if not queue_name:
        raise HTTPException(status_code=400, detail="queue_name is required")
    if request.delivery_tag is None:
        raise HTTPException(status_code=400, detail="delivery_tag is required")

    result = monitor.republish_dead_letter_message(
        queue_name=queue_name,
        delivery_tag=request.delivery_tag,
        original_queue=request.original_queue,
        original_routing_key=request.original_routing_key,
    )

    if result is not None:
        return {"success": result.get("success", False), "message": result.get("message", "")}
    raise HTTPException(status_code=500, detail="Failed to republish dead letter message")


@router.post("/rabbitmq/queues/{queue_name}/messages/republish-all")
def republish_all_dead_letters(queue_name: str, db: Session = Depends(get_db)):
    cfg = config_service.get_rabbitmq_config(db)
    monitor.set_config(cfg)

    if not queue_name:
        raise HTTPException(status_code=400, detail="queue_name is required")

    result = monitor.republish_all_dead_letters(queue_name)

    if result is not None:
        return result
    raise HTTPException(status_code=500, detail="Failed to republish all dead letters")

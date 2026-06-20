from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class OpsConfigBase(BaseModel):
    config_key: str
    config_value: str
    description: Optional[str] = None


class OpsConfigCreate(OpsConfigBase):
    pass


class OpsConfigUpdate(BaseModel):
    config_value: Optional[str] = None
    description: Optional[str] = None


class OpsConfigResponse(OpsConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectionStatus(BaseModel):
    status: str
    host: str
    port: int
    error: Optional[str] = None


class MessageRate(BaseModel):
    publish: float
    deliver: float
    ack: float


class ConnectionInfo(BaseModel):
    status: str
    host: str
    port: int
    uptime: Optional[float] = None


class RabbitMQOverview(BaseModel):
    connection: ConnectionInfo
    channels: int
    queues: int
    messageRate: MessageRate
    timestamp: int


class HealthResponse(BaseModel):
    status: str
    timestamp: int


class QueueListItem(BaseModel):
    name: str
    ready: int
    unacked: int
    total: int
    consumers: int
    status: str
    vhost: str
    durable: bool
    auto_delete: bool
    exclusive: bool
    node: str


class QueueBinding(BaseModel):
    exchange: str
    routing_key: str
    destination: str
    destination_type: str
    arguments: Dict[str, Any]


class QueueConsumer(BaseModel):
    consumer_tag: str
    channel_details: Dict[str, Any]
    ack_required: bool
    exclusive: bool
    arguments: Dict[str, Any]


class QueueDetail(BaseModel):
    name: str
    vhost: str
    durable: bool
    auto_delete: bool
    exclusive: bool
    arguments: Dict[str, Any]
    ready: int
    unacked: int
    total: int
    consumers: int
    status: str
    node: Optional[str] = None
    state: Optional[str] = None
    bindings: List[QueueBinding]
    consumer_list: List[QueueConsumer]
    message_stats: Optional[Dict[str, Any]] = None
    memory: int
    policy: Optional[str] = None


class CreateQueueRequest(BaseModel):
    name: str
    durable: Optional[bool] = True
    auto_delete: Optional[bool] = False
    exclusive: Optional[bool] = False
    arguments: Optional[Dict[str, Any]] = None


class OperationResponse(BaseModel):
    success: bool
    message: str

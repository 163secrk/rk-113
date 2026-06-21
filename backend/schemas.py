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


class ExchangeListItem(BaseModel):
    name: str
    vhost: str
    type: str
    durable: bool
    auto_delete: bool
    internal: bool


class ExchangeBinding(BaseModel):
    source: str
    destination: str
    destination_type: str
    routing_key: str
    arguments: Dict[str, Any]
    properties_key: Optional[str] = None


class ExchangeDetail(BaseModel):
    name: str
    vhost: str
    type: str
    durable: bool
    auto_delete: bool
    internal: bool
    arguments: Dict[str, Any]
    bindings: List[ExchangeBinding]


class CreateExchangeRequest(BaseModel):
    name: str
    type: str = "direct"
    durable: Optional[bool] = True
    auto_delete: Optional[bool] = False
    internal: Optional[bool] = False
    arguments: Optional[Dict[str, Any]] = None


class CreateBindingRequest(BaseModel):
    destination: str
    destination_type: Optional[str] = "queue"
    routing_key: Optional[str] = ""
    arguments: Optional[Dict[str, Any]] = None


class PublishMessageRequest(BaseModel):
    target_type: str
    target_name: str
    routing_key: Optional[str] = ""
    payload: str
    headers: Optional[Dict[str, str]] = None
    content_encoding: Optional[str] = None
    delivery_mode: Optional[int] = 2
    priority: Optional[int] = 0
    content_type: Optional[str] = "application/json"


class PublishMessageResponse(BaseModel):
    success: bool
    message: str
    published_count: Optional[int] = None


class MessageProperties(BaseModel):
    content_type: Optional[str] = None
    content_encoding: Optional[str] = None
    delivery_mode: Optional[int] = None
    priority: Optional[int] = None
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    expiration: Optional[str] = None
    message_id: Optional[str] = None
    timestamp: Optional[int] = None
    type: Optional[str] = None
    user_id: Optional[str] = None
    app_id: Optional[str] = None
    cluster_id: Optional[str] = None


class MessageOperationRequest(BaseModel):
    delivery_tag: int
    requeue: Optional[bool] = False


class MessageOperationResponse(BaseModel):
    success: bool
    message: str


class DeadLetterInfo(BaseModel):
    reason: Optional[str] = None
    original_queue: Optional[str] = None
    original_routing_key: Optional[str] = None
    original_exchange: Optional[str] = None
    count: Optional[int] = None
    time: Optional[str] = None


class MessageItem(BaseModel):
    id: str
    index: int
    payload: str
    payload_bytes: int
    headers: Dict[str, Any]
    properties: MessageProperties
    exchange: str
    routing_key: str
    redelivered: bool
    delivery_tag: int
    vhost: str
    dead_letter: Optional[DeadLetterInfo] = None


class QueueMessageListResponse(BaseModel):
    success: bool
    messages: List[MessageItem]
    total: int
    queue: str


class RepublishRequest(BaseModel):
    delivery_tag: int
    original_queue: Optional[str] = None
    original_routing_key: Optional[str] = None


class CheckQueueExistsResponse(BaseModel):
    exists: bool
    queue_name: str


class AuditLogBase(BaseModel):
    operation_type: str
    operator: str = "system"
    target_exchange: Optional[str] = None
    routing_key: Optional[str] = None
    queue_name: Optional[str] = None
    message_id: Optional[str] = None
    message_summary: Optional[str] = None
    message_body: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None
    delivery_tag: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogResponse(AuditLogBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogQueryParams(BaseModel):
    operation_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 50


class ConnectionListItem(BaseModel):
    name: str
    client_ip: str
    client_port: int
    username: str
    vhost: str
    connected_at: int
    channels: int
    server_ip: str
    server_port: int
    protocol: Optional[str] = None
    type: Optional[str] = None


class UserListItem(BaseModel):
    name: str
    tags: List[str] = []


class UserPermission(BaseModel):
    vhost: str
    configure: str
    write: str
    read: str


class UserTopicPermission(BaseModel):
    vhost: str
    exchange: str
    write: str
    read: str


class UserDetail(BaseModel):
    name: str
    tags: List[str] = []
    permissions: List[UserPermission] = []
    topic_permissions: List[UserTopicPermission] = []

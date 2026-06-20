from pydantic import BaseModel
from typing import Optional
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

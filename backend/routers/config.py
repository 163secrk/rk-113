from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from schemas import OpsConfigCreate, OpsConfigUpdate, OpsConfigResponse
from services import config_service

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=List[OpsConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    return config_service.get_all_configs(db)


@router.get("/{config_id}", response_model=OpsConfigResponse)
def get_config(config_id: int, db: Session = Depends(get_db)):
    cfg = config_service.get_config_by_id(db, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return cfg


@router.post("", response_model=OpsConfigResponse, status_code=201)
def create_config(data: OpsConfigCreate, db: Session = Depends(get_db)):
    existing = config_service.get_config_by_key(db, data.config_key)
    if existing:
        raise HTTPException(status_code=400, detail="Config key already exists")
    return config_service.create_config(db, data)


@router.put("/{config_id}", response_model=OpsConfigResponse)
def update_config(config_id: int, data: OpsConfigUpdate, db: Session = Depends(get_db)):
    cfg = config_service.update_config(db, config_id, data)
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    if cfg.config_key.startswith("rabbitmq_"):
        from services.rabbitmq_service import monitor
        monitor.set_config(config_service.get_rabbitmq_config(db))
    return cfg


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    ok = config_service.delete_config(db, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Config not found")

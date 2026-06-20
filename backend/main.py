from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import engine, Base, SessionLocal
from routers import monitor, config
from services import config_service as cs
from services.rabbitmq_service import monitor as rmq_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        cs.init_default_configs(db)
        rmq_cfg = cs.get_rabbitmq_config(db)
        rmq_monitor.set_config(rmq_cfg)
        rmq_monitor.start()
    finally:
        db.close()
    yield
    rmq_monitor.stop()


app = FastAPI(
    title="RabbitMQ Ops Platform API",
    description="RabbitMQ 运维管理平台后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(monitor.router)
app.include_router(config.router)


@app.get("/")
def root():
    return {"name": "RabbitMQ Ops Platform API", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8113, reload=True)

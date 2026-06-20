import pika
import time
import threading
from typing import Optional, Dict, Any
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import base64
import json
import socket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RabbitMQMonitor:
    def __init__(self):
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None
        self._lock = threading.Lock()
        self._connected = False
        self._connect_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._config: Dict[str, str] = {}
        self._cached_overview: Dict[str, Any] = {
            "connection": {
                "status": "connecting",
                "host": "localhost",
                "port": 5672,
                "uptime": None,
            },
            "channels": 0,
            "queues": 0,
            "messageRate": {"publish": 0.0, "deliver": 0.0, "ack": 0.0},
            "timestamp": int(time.time() * 1000),
        }
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _get_mgmt_url(self) -> str:
        host = self._config.get("rabbitmq_host", "localhost")
        mgmt_port = self._config.get("rabbitmq_mgmt_port", "15672")
        return f"http://{host}:{mgmt_port}"

    def _mgmt_request(self, path: str, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        try:
            host = self._config.get("rabbitmq_host", "localhost")
            mgmt_port = self._config.get("rabbitmq_mgmt_port", "15672")
            username = self._config.get("rabbitmq_username", "admin")
            password = self._config.get("rabbitmq_password", "admin123")
            url = f"http://{host}:{mgmt_port}{path}"
            auth = base64.b64encode(f"{username}:{password}".encode()).decode()
            req = Request(url, headers={"Authorization": f"Basic {auth}"})
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode()
                return json.loads(data)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, socket.timeout, OSError) as e:
            logger.debug(f"Management API request failed for {path}: {e}")
            return None

    def set_config(self, config: Dict[str, str]) -> None:
        with self._lock:
            old_host = self._config.get("rabbitmq_host")
            old_port = self._config.get("rabbitmq_port")
            self._config = config
            new_host = self._config.get("rabbitmq_host")
            new_port = self._config.get("rabbitmq_port")
            if old_host != new_host or old_port != new_port:
                self._disconnect_locked()
                self._cached_overview["connection"]["host"] = new_host or "localhost"
                self._cached_overview["connection"]["port"] = int(new_port or 5672)

    def _disconnect_locked(self) -> None:
        try:
            if self._channel and self._channel.is_open:
                self._channel.close()
        except Exception:
            pass
        try:
            if self._connection and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
        self._connection = None
        self._channel = None
        self._connected = False

    def _connect_once(self) -> bool:
        self._disconnect_locked()
        try:
            host = self._config.get("rabbitmq_host", "localhost")
            port = int(self._config.get("rabbitmq_port", "5672"))
            username = self._config.get("rabbitmq_username", "admin")
            password = self._config.get("rabbitmq_password", "admin123")
            vhost = self._config.get("rabbitmq_vhost", "/")

            credentials = pika.PlainCredentials(username, password)
            parameters = pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=vhost,
                credentials=credentials,
                connection_attempts=1,
                retry_delay=0,
                socket_timeout=2,
                blocked_connection_timeout=2,
            )
            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            self._connected = True
            self._connect_time = self._connect_time or time.time()
            self._last_error = None
            logger.info(f"Connected to RabbitMQ at {host}:{port}{vhost}")
            return True
        except Exception as e:
            self._last_error = str(e)
            self._connected = False
            logger.debug(f"Failed to connect RabbitMQ AMQP: {e}")
            return False

    def _ensure_connection(self) -> bool:
        if self._connected and self._connection and self._connection.is_open:
            try:
                if self._channel and self._channel.is_open:
                    return True
                self._channel = self._connection.channel()
                return True
            except Exception:
                pass
        return self._connect_once()

    def _heartbeat(self) -> None:
        if not self._connected:
            return
        try:
            if self._connection and self._connection.is_open:
                self._connection.process_data_events(time_limit=0.1)
        except Exception:
            self._connected = False

    def _fetch_metrics(self) -> Dict[str, Any]:
        channels = 0
        queues = 0
        publish_rate = 0.0
        deliver_rate = 0.0
        ack_rate = 0.0

        overview = self._mgmt_request("/api/overview", timeout=1.5)
        if overview:
            object_totals = overview.get("object_totals", {})
            channels = object_totals.get("channels", 0)
            queues = object_totals.get("queues", 0)

            message_stats = overview.get("message_stats", {})
            publish_rate = float(message_stats.get("publish_details", {}).get("rate", 0.0))
            deliver_rate = float(message_stats.get("deliver_details", {}).get("rate", 0.0))
            ack_rate = float(message_stats.get("ack_details", {}).get("rate", 0.0))
            return {
                "channels": channels,
                "queues": queues,
                "publish_rate": round(publish_rate, 2),
                "deliver_rate": round(deliver_rate, 2),
                "ack_rate": round(ack_rate, 2),
                "source": "management",
            }

        amqp_ok = self._ensure_connection()
        if amqp_ok:
            channels = 1
            vhost = self._config.get("rabbitmq_vhost", "/")
            vhost_encoded = "%2F" if vhost == "/" else vhost
            queues_data = self._mgmt_request(f"/api/queues/{vhost_encoded}", timeout=1.5)
            if queues_data:
                queues = len(queues_data)

        return {
            "channels": channels,
            "queues": queues,
            "publish_rate": round(publish_rate, 2),
            "deliver_rate": round(deliver_rate, 2),
            "ack_rate": round(ack_rate, 2),
            "source": "amqp" if amqp_ok else "none",
        }

    def _worker_loop(self) -> None:
        logger.info("RabbitMQ monitor worker started")
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    amqp_ok = self._ensure_connection()
                    mgmt_ok = self._mgmt_request("/api/overview", timeout=1.0) is not None

                    if amqp_ok or mgmt_ok:
                        status = "connected"
                    else:
                        status = "disconnected"

                    if status == "connected" and not self._connect_time:
                        self._connect_time = time.time()
                    if status == "disconnected":
                        self._connect_time = None

                    metrics = self._fetch_metrics()

                    host = self._config.get("rabbitmq_host", "localhost")
                    port = int(self._config.get("rabbitmq_port", "5672"))
                    uptime = round(time.time() - self._connect_time, 2) if (self._connect_time and status == "connected") else None

                    self._cached_overview = {
                        "connection": {
                            "status": status,
                            "host": host,
                            "port": port,
                            "uptime": uptime,
                        },
                        "channels": metrics.get("channels", 0),
                        "queues": metrics.get("queues", 0),
                        "messageRate": {
                            "publish": metrics.get("publish_rate", 0.0),
                            "deliver": metrics.get("deliver_rate", 0.0),
                            "ack": metrics.get("ack_rate", 0.0),
                        },
                        "timestamp": int(time.time() * 1000),
                    }

                    if amqp_ok:
                        self._heartbeat()

            except Exception as e:
                logger.error(f"Worker loop error: {e}")

            self._stop_event.wait(3.0)

        logger.info("RabbitMQ monitor worker stopped")

    def start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            self._disconnect_locked()

    def get_overview(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._cached_overview)

    def get_connection_status(self) -> Dict[str, Any]:
        with self._lock:
            conn = self._cached_overview.get("connection", {})
            return {
                "status": conn.get("status", "disconnected"),
                "host": conn.get("host", "localhost"),
                "port": conn.get("port", 5672),
                "error": self._last_error if conn.get("status") == "disconnected" else None,
            }


monitor = RabbitMQMonitor()

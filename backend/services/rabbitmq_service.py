import pika
import time
import threading
from typing import Optional, Dict, Any
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import quote
import base64
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

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
                "host": "127.0.0.1",
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

    @staticmethod
    def _normalize_host(host: str) -> str:
        if host.strip().lower() == "localhost":
            return "127.0.0.1"
        return host

    def _get_host(self) -> str:
        host = self._config.get("rabbitmq_host", "127.0.0.1")
        return self._normalize_host(host)

    def _get_mgmt_url(self) -> str:
        host = self._get_host()
        mgmt_port = self._config.get("rabbitmq_mgmt_port", "15672")
        return f"http://{host}:{mgmt_port}"

    def _mgmt_request(self, path: str, timeout: float = 5.0, retries: int = 2) -> Optional[Dict[str, Any]]:
        last_error = None
        for attempt in range(retries + 1):
            try:
                host = self._get_host()
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
                last_error = e
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.debug(f"Management API request failed for {path} after {retries + 1} attempts: {e}")
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
            self._cached_overview["connection"]["host"] = self._normalize_host(new_host or "127.0.0.1")
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
            host = self._get_host()
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

                    host = self._get_host()
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

    def _get_vhost_encoded(self) -> str:
        vhost = self._config.get("rabbitmq_vhost", "/")
        return "%2F" if vhost == "/" else vhost

    def list_queues(self) -> Optional[list[Dict[str, Any]]]:
        vhost = self._get_vhost_encoded()
        data = self._mgmt_request(f"/api/queues/{vhost}", timeout=8.0, retries=1)
        if data is None:
            return None
        result = []
        for q in data:
            messages_ready = q.get("messages_ready", 0)
            messages_unacknowledged = q.get("messages_unacknowledged", 0)
            messages_total = q.get("messages", 0)
            consumers = q.get("consumers", 0)
            status = "running" if consumers > 0 or messages_unacknowledged > 0 else "idle"
            result.append({
                "name": q.get("name", ""),
                "ready": messages_ready,
                "unacked": messages_unacknowledged,
                "total": messages_total,
                "consumers": consumers,
                "status": status,
                "vhost": q.get("vhost", "/"),
                "durable": q.get("durable", False),
                "auto_delete": q.get("auto_delete", False),
                "exclusive": q.get("exclusive", False),
                "node": q.get("node", ""),
            })
        return result

    def get_queue_detail(self, queue_name: str) -> Optional[Dict[str, Any]]:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        base_path = f"/api/queues/{vhost}/{queue_encoded}"

        def _fetch(path: str) -> Optional[Dict[str, Any]]:
            return self._mgmt_request(path, timeout=6.0, retries=1)

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_path = {
                executor.submit(_fetch, base_path): "queue",
                executor.submit(_fetch, f"{base_path}/bindings"): "bindings",
            }
            results: Dict[str, Any] = {}
            try:
                for future in as_completed(future_to_path, timeout=15.0):
                    path_key = future_to_path[future]
                    try:
                        results[path_key] = future.result()
                    except Exception as e:
                        logger.debug(f"Failed to fetch {path_key}: {e}")
                        results[path_key] = None
            except TimeoutError:
                logger.debug(f"Timeout fetching queue detail for {queue_name}, returning partial data")
                for path_key, future in future_to_path.items():
                    if path_key not in results:
                        if future.done():
                            try:
                                results[path_key] = future.result()
                            except Exception:
                                results[path_key] = None
                        else:
                            results[path_key] = None
                            future.cancel()

        data = results.get("queue")
        if data is None:
            return None

        bindings = results.get("bindings")
        bindings_list = []
        if bindings:
            for b in bindings:
                if b.get("source"):
                    bindings_list.append({
                        "exchange": b.get("source", ""),
                        "routing_key": b.get("routing_key", ""),
                        "destination": b.get("destination", ""),
                        "destination_type": b.get("destination_type", ""),
                        "arguments": b.get("arguments", {}),
                    })

        consumers_list = []
        consumer_details = data.get("consumer_details", [])
        if consumer_details:
            for c in consumer_details:
                consumers_list.append({
                    "consumer_tag": c.get("consumer_tag", ""),
                    "channel_details": c.get("channel_details", {}),
                    "ack_required": c.get("ack_required", False),
                    "exclusive": c.get("exclusive", False),
                    "arguments": c.get("arguments", {}),
                })

        messages_ready = data.get("messages_ready", 0)
        messages_unacknowledged = data.get("messages_unacknowledged", 0)
        messages_total = data.get("messages", 0)
        consumers = data.get("consumers", 0)
        status = "running" if consumers > 0 or messages_unacknowledged > 0 else "idle"

        return {
            "name": data.get("name", ""),
            "vhost": data.get("vhost", "/"),
            "durable": data.get("durable", False),
            "auto_delete": data.get("auto_delete", False),
            "exclusive": data.get("exclusive", False),
            "arguments": data.get("arguments", {}),
            "ready": messages_ready,
            "unacked": messages_unacknowledged,
            "total": messages_total,
            "consumers": consumers,
            "status": status,
            "node": data.get("node", ""),
            "state": data.get("state", ""),
            "bindings": bindings_list,
            "consumer_list": consumers_list,
            "message_stats": data.get("message_stats", {}),
            "memory": data.get("memory", 0),
            "policy": data.get("policy", ""),
        }

    def create_queue(
        self,
        queue_name: str,
        durable: bool = True,
        auto_delete: bool = False,
        exclusive: bool = False,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> bool:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        url = f"/api/queues/{vhost}/{queue_encoded}"
        body = {
            "durable": durable,
            "auto_delete": auto_delete,
            "exclusive": exclusive,
            "arguments": arguments or {},
        }
        return self._mgmt_request_put(url, body, timeout=6.0, retries=1)

    def purge_queue(self, queue_name: str) -> bool:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        url = f"/api/queues/{vhost}/{queue_encoded}/contents"
        return self._mgmt_request_delete(url, timeout=6.0, retries=1)

    def delete_queue(self, queue_name: str, if_unused: bool = False, if_empty: bool = False) -> bool:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        params = []
        if if_unused:
            params.append("if-unused=true")
        if if_empty:
            params.append("if-empty=true")
        url = f"/api/queues/{vhost}/{queue_encoded}"
        if params:
            url += "?" + "&".join(params)
        return self._mgmt_request_delete(url, timeout=6.0, retries=1)

    def _mgmt_request_put(self, path: str, body: Dict[str, Any], timeout: float = 5.0, retries: int = 1) -> bool:
        last_error = None
        for attempt in range(retries + 1):
            try:
                host = self._get_host()
                mgmt_port = self._config.get("rabbitmq_mgmt_port", "15672")
                username = self._config.get("rabbitmq_username", "admin")
                password = self._config.get("rabbitmq_password", "admin123")
                url = f"http://{host}:{mgmt_port}{path}"
                auth = base64.b64encode(f"{username}:{password}".encode()).decode()
                data = json.dumps(body).encode()
                req = Request(
                    url,
                    data=data,
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json",
                    },
                    method="PUT",
                )
                with urlopen(req, timeout=timeout) as resp:
                    return 200 <= resp.status < 300
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.debug(f"Management API PUT failed for {path} after {retries + 1} attempts: {e}")
                return False

    def _mgmt_request_delete(self, path: str, timeout: float = 5.0, retries: int = 1) -> bool:
        last_error = None
        for attempt in range(retries + 1):
            try:
                host = self._get_host()
                mgmt_port = self._config.get("rabbitmq_mgmt_port", "15672")
                username = self._config.get("rabbitmq_username", "admin")
                password = self._config.get("rabbitmq_password", "admin123")
                url = f"http://{host}:{mgmt_port}{path}"
                auth = base64.b64encode(f"{username}:{password}".encode()).decode()
                req = Request(
                    url,
                    headers={
                        "Authorization": f"Basic {auth}",
                    },
                    method="DELETE",
                )
                with urlopen(req, timeout=timeout) as resp:
                    return 200 <= resp.status < 300
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.debug(f"Management API DELETE failed for {path} after {retries + 1} attempts: {e}")
                return False


    def list_exchanges(self) -> Optional[list[Dict[str, Any]]]:
        vhost = self._get_vhost_encoded()
        data = self._mgmt_request(f"/api/exchanges/{vhost}", timeout=8.0, retries=1)
        if data is None:
            return None
        result = []
        for e in data:
            result.append({
                "name": e.get("name", ""),
                "vhost": e.get("vhost", "/"),
                "type": e.get("type", "direct"),
                "durable": e.get("durable", False),
                "auto_delete": e.get("auto_delete", False),
                "internal": e.get("internal", False),
            })
        return result

    def get_exchange_detail(self, exchange_name: str) -> Optional[Dict[str, Any]]:
        vhost = self._get_vhost_encoded()
        exchange_encoded = quote(exchange_name, safe="")
        base_path = f"/api/exchanges/{vhost}/{exchange_encoded}"

        def _fetch(path: str) -> Optional[Dict[str, Any]]:
            return self._mgmt_request(path, timeout=6.0, retries=1)

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_path = {
                executor.submit(_fetch, base_path): "exchange",
                executor.submit(_fetch, f"{base_path}/bindings/source"): "bindings",
            }
            results: Dict[str, Any] = {}
            try:
                for future in as_completed(future_to_path, timeout=15.0):
                    path_key = future_to_path[future]
                    try:
                        results[path_key] = future.result()
                    except Exception as e:
                        logger.debug(f"Failed to fetch {path_key}: {e}")
                        results[path_key] = None
            except TimeoutError:
                logger.debug(f"Timeout fetching exchange detail for {exchange_name}, returning partial data")
                for path_key, future in future_to_path.items():
                    if path_key not in results:
                        if future.done():
                            try:
                                results[path_key] = future.result()
                            except Exception:
                                results[path_key] = None
                        else:
                            results[path_key] = None
                            future.cancel()

        data = results.get("exchange")
        if data is None:
            return None

        bindings = results.get("bindings")
        bindings_list = []
        if bindings and isinstance(bindings, list):
            for b in bindings:
                bindings_list.append({
                    "source": b.get("source", ""),
                    "destination": b.get("destination", ""),
                    "destination_type": b.get("destination_type", ""),
                    "routing_key": b.get("routing_key", ""),
                    "arguments": b.get("arguments", {}),
                    "properties_key": b.get("properties_key", ""),
                })

        return {
            "name": data.get("name", ""),
            "vhost": data.get("vhost", "/"),
            "type": data.get("type", "direct"),
            "durable": data.get("durable", False),
            "auto_delete": data.get("auto_delete", False),
            "internal": data.get("internal", False),
            "arguments": data.get("arguments", {}),
            "bindings": bindings_list,
        }

    def create_exchange(
        self,
        exchange_name: str,
        exchange_type: str = "direct",
        durable: bool = True,
        auto_delete: bool = False,
        internal: bool = False,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> bool:
        vhost = self._get_vhost_encoded()
        exchange_encoded = quote(exchange_name, safe="")
        url = f"/api/exchanges/{vhost}/{exchange_encoded}"
        body = {
            "type": exchange_type,
            "durable": durable,
            "auto_delete": auto_delete,
            "internal": internal,
            "arguments": arguments or {},
        }
        return self._mgmt_request_put(url, body, timeout=6.0, retries=1)

    def delete_exchange(self, exchange_name: str, if_unused: bool = False) -> bool:
        vhost = self._get_vhost_encoded()
        exchange_encoded = quote(exchange_name, safe="")
        params = []
        if if_unused:
            params.append("if-unused=true")
        url = f"/api/exchanges/{vhost}/{exchange_encoded}"
        if params:
            url += "?" + "&".join(params)
        return self._mgmt_request_delete(url, timeout=6.0, retries=1)

    def create_binding(
        self,
        exchange_name: str,
        destination: str,
        destination_type: str = "queue",
        routing_key: str = "",
        arguments: Optional[Dict[str, Any]] = None,
    ) -> bool:
        vhost = self._get_vhost_encoded()
        exchange_encoded = quote(exchange_name, safe="")
        destination_encoded = quote(destination, safe="")
        type_short = "q" if destination_type == "queue" else "e"
        url = f"/api/bindings/{vhost}/e/{exchange_encoded}/{type_short}/{destination_encoded}"
        body = {
            "routing_key": routing_key,
            "arguments": arguments or {},
        }
        return self._mgmt_request_post(url, body, timeout=6.0, retries=1)

    def delete_binding(
        self,
        exchange_name: str,
        destination: str,
        destination_type: str = "queue",
        properties_key: str = "",
    ) -> bool:
        vhost = self._get_vhost_encoded()
        exchange_encoded = quote(exchange_name, safe="")
        destination_encoded = quote(destination, safe="")
        props_encoded = quote(properties_key, safe="")
        type_short = "q" if destination_type == "queue" else "e"
        url = f"/api/bindings/{vhost}/e/{exchange_encoded}/{type_short}/{destination_encoded}/{props_encoded}"
        return self._mgmt_request_delete(url, timeout=6.0, retries=1)

    def _mgmt_request_post(self, path: str, body: Dict[str, Any], timeout: float = 5.0, retries: int = 1) -> bool:
        last_error = None
        for attempt in range(retries + 1):
            try:
                host = self._get_host()
                mgmt_port = self._config.get("rabbitmq_mgmt_port", "15672")
                username = self._config.get("rabbitmq_username", "admin")
                password = self._config.get("rabbitmq_password", "admin123")
                url = f"http://{host}:{mgmt_port}{path}"
                auth = base64.b64encode(f"{username}:{password}".encode()).decode()
                data = json.dumps(body).encode()
                req = Request(
                    url,
                    data=data,
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(req, timeout=timeout) as resp:
                    return 200 <= resp.status < 300
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.debug(f"Management API POST failed for {path} after {retries + 1} attempts: {e}")
                return False


monitor = RabbitMQMonitor()

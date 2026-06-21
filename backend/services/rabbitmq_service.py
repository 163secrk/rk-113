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

        self._msg_channel: Optional[pika.channel.Channel] = None
        self._msg_lock = threading.Lock()
        self._msg_current_queue: Optional[str] = None
        self._unacked_messages: Dict[int, Dict[str, Any]] = {}

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
            if self._msg_channel and self._msg_channel.is_open:
                self._msg_channel.close()
        except Exception:
            pass
        try:
            if self._connection and self._connection.is_open:
                self._connection.close()
        except Exception:
            pass
        self._connection = None
        self._channel = None
        self._msg_channel = None
        self._connected = False
        self._msg_current_queue = None
        self._unacked_messages = {}

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

    def _mgmt_request_post_data(self, path: str, body: Dict[str, Any], timeout: float = 5.0, retries: int = 1) -> Optional[Any]:
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
                    resp_data = resp.read().decode()
                    return json.loads(resp_data)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.debug(f"Management API POST data failed for {path} after {retries + 1} attempts: {e}")
                return None

    def _ensure_msg_channel(self) -> bool:
        try:
            if self._msg_channel and self._msg_channel.is_open:
                return True
            if self._connection and self._connection.is_open:
                self._msg_channel = self._connection.channel()
                return True
        except Exception as e:
            logger.debug(f"Failed to create msg channel: {e}")
        if self._connect_once():
            try:
                if self._connection and self._connection.is_open:
                    self._msg_channel = self._connection.channel()
                    return True
            except Exception as e:
                logger.debug(f"Failed to create msg channel after reconnect: {e}")
        return False

    def _nack_all_unacked(self) -> None:
        if not self._msg_channel or not self._msg_channel.is_open:
            return
        try:
            if self._unacked_messages:
                self._msg_channel.basic_nack(
                    delivery_tag=max(self._unacked_messages.keys()),
                    multiple=True,
                    requeue=True,
                )
                self._unacked_messages = {}
        except Exception as e:
            logger.debug(f"Failed to nack all unacked messages: {e}")

    def publish_message(
        self,
        target_type: str,
        target_name: str,
        routing_key: str = "",
        payload: str = "",
        headers: Optional[Dict[str, str]] = None,
        content_encoding: Optional[str] = None,
        delivery_mode: int = 2,
        priority: int = 0,
        content_type: str = "application/json",
    ) -> Optional[int]:
        with self._lock:
            if not self._ensure_msg_channel():
                return None
            try:
                if target_type == "queue":
                    exchange_name = ""
                    final_routing_key = target_name
                else:
                    exchange_name = target_name
                    final_routing_key = routing_key or ""

                properties = pika.BasicProperties(
                    content_type=content_type,
                    content_encoding=content_encoding,
                    delivery_mode=delivery_mode,
                    priority=priority,
                    headers=headers or {},
                    timestamp=int(time.time()),
                )

                self._msg_channel.basic_publish(
                    exchange=exchange_name,
                    routing_key=final_routing_key,
                    body=payload.encode() if isinstance(payload, str) else payload,
                    properties=properties,
                )

                if target_type == "queue":
                    return 1

                if exchange_name:
                    q_result = self._mgmt_request_get_queue_count()
                    if q_result is not None:
                        return max(1, q_result)
                return 1
            except Exception as e:
                logger.error(f"Failed to publish message: {e}")
                return None

    def _mgmt_request_get_queue_count(self) -> Optional[int]:
        vhost = self._get_vhost_encoded()
        data = self._mgmt_request(f"/api/queues/{vhost}", timeout=5.0, retries=1)
        if data is None:
            return None
        total = 0
        for q in data:
            total += q.get("messages", 0)
        return total

    def get_queue_messages(
        self,
        queue_name: str,
        limit: int = 50,
        requeue: bool = True,
    ) -> Optional[Dict[str, Any]]:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        path = f"/api/queues/{vhost}/{queue_encoded}"
        queue_info = self._mgmt_request(path, timeout=5.0, retries=1)
        total_messages = 0
        if queue_info:
            total_messages = queue_info.get("messages", 0)

        if requeue:
            body = {
                "count": min(limit, total_messages) if total_messages > 0 else limit,
                "requeue": True,
                "encoding": "auto",
                "truncate": 50000,
            }
            mgmt_path = f"/api/queues/{vhost}/{queue_encoded}/get"
            raw_messages = self._mgmt_request_post_data(mgmt_path, body, timeout=10.0, retries=1)
            if raw_messages is None:
                return None
            messages = []
            for idx, msg in enumerate(raw_messages):
                payload = msg.get("payload", "")
                payload_bytes = len(payload.encode("utf-8")) if isinstance(payload, str) else len(payload)
                props = msg.get("properties", {})
                headers = props.get("headers", {}) or {}
                dead_letter = self._parse_dead_letter_info(headers)

                messages.append({
                    "id": f"{queue_name}-{idx}-{int(time.time() * 1000)}",
                    "index": idx + 1,
                    "payload": payload,
                    "payload_bytes": payload_bytes,
                    "headers": headers,
                    "properties": {
                        "content_type": props.get("content_type"),
                        "content_encoding": props.get("content_encoding"),
                        "delivery_mode": props.get("delivery_mode"),
                        "priority": props.get("priority"),
                        "correlation_id": props.get("correlation_id"),
                        "reply_to": props.get("reply_to"),
                        "expiration": props.get("expiration"),
                        "message_id": props.get("message_id"),
                        "timestamp": props.get("timestamp"),
                        "type": props.get("type"),
                        "user_id": props.get("user_id"),
                        "app_id": props.get("app_id"),
                        "cluster_id": props.get("cluster_id"),
                    },
                    "exchange": msg.get("exchange", ""),
                    "routing_key": msg.get("routing_key", ""),
                    "redelivered": bool(msg.get("redelivered", False)),
                    "delivery_tag": idx + 1,
                    "vhost": self._config.get("rabbitmq_vhost", "/"),
                    "dead_letter": dead_letter,
                })
            return {
                "success": True,
                "messages": messages,
                "total": total_messages,
                "queue": queue_name,
                "mode": "requeue",
            }
        else:
            with self._lock:
                if not self._ensure_msg_channel():
                    return None

                self._nack_all_unacked()
                self._msg_current_queue = queue_name

                messages = []
                for i in range(limit):
                    try:
                        method, properties, body = self._msg_channel.basic_get(
                            queue=queue_name,
                            auto_ack=False,
                        )
                        if method is None:
                            break

                        delivery_tag = method.delivery_tag
                        payload = body.decode("utf-8") if isinstance(body, bytes) else str(body)
                        payload_bytes = len(payload.encode("utf-8"))
                        headers = dict(properties.headers) if properties.headers else {}
                        dead_letter = self._parse_dead_letter_info(headers)

                        msg_info = {
                            "id": f"{queue_name}-{delivery_tag}-{int(time.time() * 1000)}",
                            "index": len(messages) + 1,
                            "payload": payload,
                            "payload_bytes": payload_bytes,
                            "headers": headers,
                            "properties": {
                                "content_type": properties.content_type,
                                "content_encoding": properties.content_encoding,
                                "delivery_mode": properties.delivery_mode,
                                "priority": properties.priority,
                                "correlation_id": properties.correlation_id,
                                "reply_to": properties.reply_to,
                                "expiration": properties.expiration,
                                "message_id": properties.message_id,
                                "timestamp": properties.timestamp,
                                "type": properties.type,
                                "user_id": properties.user_id,
                                "app_id": properties.app_id,
                                "cluster_id": properties.cluster_id,
                            },
                            "exchange": method.exchange,
                            "routing_key": method.routing_key,
                            "redelivered": method.redelivered,
                            "delivery_tag": delivery_tag,
                            "vhost": self._config.get("rabbitmq_vhost", "/"),
                            "dead_letter": dead_letter,
                        }
                        messages.append(msg_info)
                        self._unacked_messages[delivery_tag] = msg_info
                    except Exception as e:
                        logger.debug(f"Failed to get message {i}: {e}")
                        break

                return {
                    "success": True,
                    "messages": messages,
                    "total": total_messages,
                    "queue": queue_name,
                    "mode": "no-requeue",
                }

    def ack_message(self, queue_name: str, delivery_tag: int) -> bool:
        with self._lock:
            if not self._ensure_msg_channel():
                return False
            try:
                if self._msg_current_queue != queue_name:
                    logger.warning(f"ACK queue mismatch: expected {self._msg_current_queue}, got {queue_name}")
                    return False
                self._msg_channel.basic_ack(delivery_tag=delivery_tag)
                if delivery_tag in self._unacked_messages:
                    del self._unacked_messages[delivery_tag]
                return True
            except Exception as e:
                logger.error(f"Failed to ack message {delivery_tag}: {e}")
                return False

    def reject_message(self, queue_name: str, delivery_tag: int, requeue: bool = False) -> bool:
        with self._lock:
            if not self._ensure_msg_channel():
                return False
            try:
                if self._msg_current_queue != queue_name:
                    logger.warning(f"Reject queue mismatch: expected {self._msg_current_queue}, got {queue_name}")
                    return False
                self._msg_channel.basic_reject(
                    delivery_tag=delivery_tag,
                    requeue=requeue,
                )
                if delivery_tag in self._unacked_messages:
                    del self._unacked_messages[delivery_tag]
                return True
            except Exception as e:
                logger.error(f"Failed to reject message {delivery_tag}: {e}")
                return False

    @staticmethod
    def _parse_dead_letter_info(headers: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not headers:
            return None
        x_death = headers.get("x-death")
        if not x_death or not isinstance(x_death, list) or len(x_death) == 0:
            return None

        death_info = x_death[0]
        reason = death_info.get("reason")
        original_queue = death_info.get("queue")
        routing_keys = death_info.get("routing-keys", [])
        original_routing_key = routing_keys[0] if routing_keys and isinstance(routing_keys, list) else None
        original_exchange = death_info.get("exchange")
        count = death_info.get("count")
        time_val = death_info.get("time")

        return {
            "reason": reason,
            "original_queue": original_queue,
            "original_routing_key": original_routing_key,
            "original_exchange": original_exchange,
            "count": count,
            "time": str(time_val) if time_val else None,
        }

    def _is_dead_letter_queue(self, queue_name: str) -> bool:
        name_lower = queue_name.lower()
        return "dlq" in name_lower or "dead-letter" in name_lower or "dead_letter" in name_lower

    def check_queue_exists(self, queue_name: str) -> bool:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        path = f"/api/queues/{vhost}/{queue_encoded}"
        data = self._mgmt_request(path, timeout=5.0, retries=1)
        return data is not None and isinstance(data, dict) and data.get("name") == queue_name

    def republish_dead_letter_message(
        self,
        queue_name: str,
        delivery_tag: int,
        original_queue: Optional[str] = None,
        original_routing_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._ensure_msg_channel():
                return None
            try:
                if self._msg_current_queue != queue_name:
                    logger.warning(f"Republish queue mismatch: expected {self._msg_current_queue}, got {queue_name}")
                    return None

                msg_info = self._unacked_messages.get(delivery_tag)
                if not msg_info:
                    logger.warning(f"Message with delivery_tag {delivery_tag} not found in unacked messages")
                    return None

                headers = msg_info.get("headers", {}) or {}
                dl_info = self._parse_dead_letter_info(headers)

                target_queue = original_queue
                if not target_queue and dl_info:
                    target_queue = dl_info.get("original_queue")
                if not target_queue:
                    return {"success": False, "message": "无法确定原始队列名称，请手动指定"}

                if not self.check_queue_exists(target_queue):
                    return {"success": False, "message": f"原始队列 '{target_queue}' 不存在，无法投递"}

                target_routing_key = original_routing_key
                if not target_routing_key and dl_info:
                    target_routing_key = dl_info.get("original_routing_key") or ""

                props_data = msg_info.get("properties", {})
                clean_headers = {k: v for k, v in headers.items() if not k.startswith("x-")}

                properties = pika.BasicProperties(
                    content_type=props_data.get("content_type"),
                    content_encoding=props_data.get("content_encoding"),
                    delivery_mode=props_data.get("delivery_mode", 2),
                    priority=props_data.get("priority", 0),
                    headers=clean_headers,
                    correlation_id=props_data.get("correlation_id"),
                    reply_to=props_data.get("reply_to"),
                    expiration=props_data.get("expiration"),
                    message_id=props_data.get("message_id"),
                    timestamp=props_data.get("timestamp") or int(time.time()),
                    type=props_data.get("type"),
                    user_id=props_data.get("user_id"),
                    app_id=props_data.get("app_id"),
                    cluster_id=props_data.get("cluster_id"),
                )

                payload = msg_info.get("payload", "")
                self._msg_channel.basic_publish(
                    exchange="",
                    routing_key=target_queue,
                    body=payload.encode() if isinstance(payload, str) else payload,
                    properties=properties,
                )

                self._msg_channel.basic_ack(delivery_tag=delivery_tag)
                if delivery_tag in self._unacked_messages:
                    del self._unacked_messages[delivery_tag]

                return {
                    "success": True,
                    "message": f"消息已重新投递到队列 '{target_queue}'",
                    "target_queue": target_queue,
                    "target_routing_key": target_routing_key,
                }
            except Exception as e:
                logger.error(f"Failed to republish message {delivery_tag}: {e}")
                return {"success": False, "message": f"重新投递失败: {str(e)}"}

    def republish_all_dead_letters(self, queue_name: str) -> Optional[Dict[str, Any]]:
        vhost = self._get_vhost_encoded()
        queue_encoded = quote(queue_name, safe="")
        path = f"/api/queues/{vhost}/{queue_encoded}"
        queue_info = self._mgmt_request(path, timeout=5.0, retries=1)
        total_messages = 0
        if queue_info:
            total_messages = queue_info.get("messages", 0)

        if total_messages == 0:
            return {"success": True, "message": "死信队列为空，无需投递", "total": 0, "success_count": 0, "failed_count": 0}

        with self._lock:
            if not self._ensure_msg_channel():
                return None

            try:
                self._nack_all_unacked()
                self._msg_current_queue = queue_name

                success_count = 0
                failed_count = 0
                failed_details = []
                processed_count = min(total_messages, 500)

                for i in range(processed_count):
                    try:
                        method, properties, body = self._msg_channel.basic_get(
                            queue=queue_name,
                            auto_ack=False,
                        )
                        if method is None:
                            break

                        delivery_tag = method.delivery_tag
                        payload = body.decode("utf-8") if isinstance(body, bytes) else str(body)
                        headers = dict(properties.headers) if properties.headers else {}
                        dl_info = self._parse_dead_letter_info(headers)

                        target_queue = None
                        if dl_info:
                            target_queue = dl_info.get("original_queue")
                        if not target_queue:
                            failed_count += 1
                            failed_details.append(f"消息 #{i+1}: 无法确定原始队列")
                            self._msg_channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                            continue

                        if not self.check_queue_exists(target_queue):
                            failed_count += 1
                            failed_details.append(f"消息 #{i+1}: 原始队列 '{target_queue}' 不存在")
                            self._msg_channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                            continue

                        target_routing_key = None
                        if dl_info:
                            target_routing_key = dl_info.get("original_routing_key") or ""

                        clean_headers = {k: v for k, v in headers.items() if not k.startswith("x-")}
                        new_properties = pika.BasicProperties(
                            content_type=properties.content_type,
                            content_encoding=properties.content_encoding,
                            delivery_mode=properties.delivery_mode or 2,
                            priority=properties.priority or 0,
                            headers=clean_headers,
                            correlation_id=properties.correlation_id,
                            reply_to=properties.reply_to,
                            expiration=properties.expiration,
                            message_id=properties.message_id,
                            timestamp=properties.timestamp or int(time.time()),
                            type=properties.type,
                            user_id=properties.user_id,
                            app_id=properties.app_id,
                            cluster_id=properties.cluster_id,
                        )

                        self._msg_channel.basic_publish(
                            exchange="",
                            routing_key=target_queue,
                            body=payload.encode() if isinstance(payload, str) else payload,
                            properties=new_properties,
                        )

                        self._msg_channel.basic_ack(delivery_tag=delivery_tag)
                        success_count += 1
                    except Exception as e:
                        logger.debug(f"Failed to republish message {i}: {e}")
                        failed_count += 1
                        failed_details.append(f"消息 #{i+1}: {str(e)}")
                        try:
                            self._msg_channel.basic_nack(delivery_tag=method.delivery_tag if method else 0, requeue=True)
                        except Exception:
                            pass

                return {
                    "success": True,
                    "message": f"批量重新投递完成，成功 {success_count} 条，失败 {failed_count} 条",
                    "total": processed_count,
                    "success_count": success_count,
                    "failed_count": failed_count,
                    "failed_details": failed_details[:10] if failed_details else [],
                }
            except Exception as e:
                logger.error(f"Failed to republish all dead letters: {e}")
                return {"success": False, "message": f"批量重新投递失败: {str(e)}"}


monitor = RabbitMQMonitor()

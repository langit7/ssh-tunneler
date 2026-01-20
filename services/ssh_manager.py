"""
SSH Connection Manager with Auto-Reconnect Support
"""
import threading
import logging
import time
from typing import Dict, Callable, Optional, Union
from dataclasses import dataclass
import paramiko
from sshtunnel import SSHTunnelForwarder

from models.tunnel import Tunnel, TunnelType, AuthType, TunnelStatus
from services.socks5_server import Socks5Server


@dataclass
class TunnelConnection:
    """Active tunnel connection state"""
    tunnel: Tunnel
    server: Optional[Union[SSHTunnelForwarder, Socks5Server]] = None
    thread: Optional[threading.Thread] = None
    stop_event: Optional[threading.Event] = None
    status: TunnelStatus = TunnelStatus.STOPPED


class SSHManager:
    """Manages SSH tunnel connections with auto-reconnect support"""

    def __init__(self, status_callback: Optional[Callable[[str, TunnelStatus, str], None]] = None):
        """
        Initialize SSH Manager

        Args:
            status_callback: Function called when tunnel status changes.
                            Signature: callback(tunnel_id, status, error_message)
        """
        self.connections: Dict[str, TunnelConnection] = {}
        self.status_callback = status_callback
        self._lock = threading.Lock()

    def _notify_status(self, tunnel_id: str, status: TunnelStatus, error: str = ""):
        """Notify status change via callback"""
        if self.status_callback:
            self.status_callback(tunnel_id, status, error)

    def _create_tunnel_server(self, tunnel: Tunnel) -> SSHTunnelForwarder:
        """Create SSHTunnelForwarder based on tunnel configuration"""
        # Authentication parameters
        auth_kwargs = {}
        if tunnel.auth_type == AuthType.PASSWORD:
            auth_kwargs["ssh_password"] = tunnel.ssh_password
        else:
            auth_kwargs["ssh_pkey"] = tunnel.ssh_key_path

        # Base parameters
        base_kwargs = {
            "ssh_address_or_host": (tunnel.ssh_host, tunnel.ssh_port),
            "ssh_username": tunnel.ssh_user,
            **auth_kwargs,
        }

        # Keep-alive settings
        if tunnel.keepalive_enabled:
            base_kwargs["set_keepalive"] = tunnel.keepalive_interval

        # Proxy settings - create proxy socket if enabled
        if tunnel.proxy_enabled and tunnel.proxy_host and tunnel.proxy_port:
            proxy_sock = self._create_proxy_socket(tunnel)
            if proxy_sock:
                base_kwargs["ssh_proxy"] = proxy_sock

        if tunnel.tunnel_type == TunnelType.LOCAL:
            # Local port forwarding: local_port -> remote_host:remote_port
            return SSHTunnelForwarder(
                **base_kwargs,
                local_bind_address=("127.0.0.1", tunnel.local_port),
                remote_bind_address=(tunnel.remote_host, tunnel.remote_port),
            )
        elif tunnel.tunnel_type == TunnelType.REMOTE:
            # Remote port forwarding: ssh_server:remote_port -> local_port
            return SSHTunnelForwarder(
                **base_kwargs,
                remote_bind_address=("127.0.0.1", tunnel.local_port),
                local_bind_address=("127.0.0.1", tunnel.remote_port),
            )
        else:
            # Dynamic (SOCKS) forwarding
            return Socks5Server(tunnel, self.status_callback)

    def _create_proxy_socket(self, tunnel: Tunnel):
        """Create a socket connected through proxy for SSH connection"""
        import socket
        from models.tunnel import ProxyType
        
        try:
            if tunnel.proxy_type == ProxyType.SOCKS5:
                # Use PySocks for SOCKS5 proxy
                try:
                    import socks
                except ImportError:
                    logging.error("PySocks not installed. Run: pip install pysocks")
                    return None
                
                proxy_sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
                proxy_sock.set_proxy(
                    proxy_type=socks.SOCKS5,
                    addr=tunnel.proxy_host,
                    port=tunnel.proxy_port,
                    username=tunnel.proxy_user if tunnel.proxy_user else None,
                    password=tunnel.proxy_password if tunnel.proxy_password else None,
                )
                proxy_sock.connect((tunnel.ssh_host, tunnel.ssh_port))
                return proxy_sock
            
            elif tunnel.proxy_type == ProxyType.HTTP:
                # HTTP CONNECT proxy
                proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                proxy_sock.connect((tunnel.proxy_host, tunnel.proxy_port))
                
                # Send CONNECT request
                connect_header = f"CONNECT {tunnel.ssh_host}:{tunnel.ssh_port} HTTP/1.1\r\n"
                connect_header += f"Host: {tunnel.ssh_host}:{tunnel.ssh_port}\r\n"
                
                if tunnel.proxy_user and tunnel.proxy_password:
                    import base64
                    credentials = base64.b64encode(
                        f"{tunnel.proxy_user}:{tunnel.proxy_password}".encode()
                    ).decode()
                    connect_header += f"Proxy-Authorization: Basic {credentials}\r\n"
                
                connect_header += "\r\n"
                proxy_sock.sendall(connect_header.encode())
                
                # Read response
                response = b""
                while b"\r\n\r\n" not in response:
                    chunk = proxy_sock.recv(4096)
                    if not chunk:
                        raise Exception("Proxy connection closed")
                    response += chunk
                
                # Check for 200 OK
                status_line = response.split(b"\r\n")[0].decode()
                if "200" not in status_line:
                    raise Exception(f"Proxy error: {status_line}")
                
                return proxy_sock
            
        except Exception as e:
            logging.error(f"Failed to create proxy connection: {e}")
            return None
        
        return None

    def _tunnel_worker(self, tunnel: Tunnel, stop_event: threading.Event):
        """Background worker thread for managing tunnel connection"""
        tunnel_id = tunnel.id
        retry_delay = 5  # seconds
        logger = logging.getLogger(f"SSHManager.{tunnel.name}")

        logger.info(f"Worker started for tunnel: {tunnel.name}")

        while not stop_event.is_set():
            server = None
            try:
                logger.info(f"Connecting to {tunnel.ssh_host}:{tunnel.ssh_port}...")
                self._notify_status(tunnel_id, TunnelStatus.CONNECTING)
                server = self._create_tunnel_server(tunnel)
                server.start()

                if server.is_active:
                    logger.info(f"Tunnel {tunnel.name} is now ACTIVE")
                    self._notify_status(tunnel_id, TunnelStatus.RUNNING)

                    # Update connection reference
                    with self._lock:
                        if tunnel_id in self.connections:
                            self.connections[tunnel_id].server = server

                    # Keep-alive loop
                    while not stop_event.is_set() and server.is_active:
                        time.sleep(1)

                    if stop_event.is_set():
                        break

                    # Connection dropped
                    msg = "Connection lost. Reconnecting..." if tunnel.auto_reconnect else "Connection lost"
                    logger.warning(msg)
                    self._notify_status(tunnel_id, TunnelStatus.ERROR, msg)
                    if not tunnel.auto_reconnect:
                        break
                else:
                    raise Exception("Failed to establish tunnel")

            except paramiko.AuthenticationException as e:
                logger.error(f"Authentication failed: {e}")
                self._notify_status(tunnel_id, TunnelStatus.ERROR, f"Authentication failed: {e}")
                break  # Don't retry on auth failure

            except Exception as e:
                import traceback
                error_msg = str(e)
                logger.error(f"Error: {error_msg}")
                # logger.debug(f"Traceback: {traceback.format_exc()}") # Optional, maybe too noisy for GUI log

                if tunnel.auto_reconnect and not stop_event.is_set():
                    msg = f"{error_msg}. Retrying in {retry_delay}s..."
                    logger.info(msg)
                    self._notify_status(tunnel_id, TunnelStatus.ERROR, msg)
                    # Wait for retry or stop signal
                    stop_event.wait(retry_delay)
                else:
                    self._notify_status(tunnel_id, TunnelStatus.ERROR, error_msg)
                    break

            finally:
                if server:
                    try:
                        server.stop()
                    except:
                        pass

        # Cleanup
        self._notify_status(tunnel_id, TunnelStatus.STOPPED)
        with self._lock:
            if tunnel_id in self.connections:
                self.connections[tunnel_id].server = None

    def start_tunnel(self, tunnel: Tunnel) -> bool:
        """Start a tunnel connection"""
        tunnel_id = tunnel.id

        with self._lock:
            # Check if already running
            if tunnel_id in self.connections:
                conn = self.connections[tunnel_id]
                if conn.thread and conn.thread.is_alive():
                    return False  # Already running

            # Create new connection
            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._tunnel_worker,
                args=(tunnel, stop_event),
                daemon=True,
                name=f"tunnel-{tunnel_id[:8]}",
            )

            self.connections[tunnel_id] = TunnelConnection(
                tunnel=tunnel,
                thread=thread,
                stop_event=stop_event,
                status=TunnelStatus.CONNECTING,
            )

        thread.start()
        return True

    def stop_tunnel(self, tunnel_id: str) -> bool:
        """Stop a tunnel connection"""
        with self._lock:
            if tunnel_id not in self.connections:
                return False

            conn = self.connections[tunnel_id]

            # Signal thread to stop
            if conn.stop_event:
                conn.stop_event.set()

            # Stop the server
            if conn.server:
                try:
                    conn.server.stop()
                except:
                    pass

        # Wait for thread to finish (outside lock)
        if conn.thread and conn.thread.is_alive():
            conn.thread.join(timeout=3)

        return True

    def stop_all(self):
        """Stop all tunnel connections"""
        with self._lock:
            tunnel_ids = list(self.connections.keys())

        for tunnel_id in tunnel_ids:
            self.stop_tunnel(tunnel_id)

    def start_all(self, tunnels: list[Tunnel]):
        """Start all provided tunnels"""
        for tunnel in tunnels:
            self.start_tunnel(tunnel)

    def is_running(self, tunnel_id: str) -> bool:
        """Check if a tunnel is currently running"""
        with self._lock:
            if tunnel_id in self.connections:
                conn = self.connections[tunnel_id]
                return conn.thread is not None and conn.thread.is_alive()
        return False

    def get_status(self, tunnel_id: str) -> TunnelStatus:
        """Get current status of a tunnel"""
        with self._lock:
            if tunnel_id in self.connections:
                return self.connections[tunnel_id].status
        return TunnelStatus.STOPPED

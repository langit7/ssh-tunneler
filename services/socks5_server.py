"""
SOCKS5 Proxy Server with SSH Tunnel Support
Implements a local SOCKS5 server that forwards traffic through an SSH tunnel.
"""
import logging
import socket
import select
import threading
import struct
from typing import Optional, Callable
import paramiko

from models.tunnel import Tunnel, AuthType, TunnelStatus


# SOCKS5 Constants
SOCKS_VERSION = 5
AUTH_NONE = 0
AUTH_PASSWORD = 2
CMD_CONNECT = 1
ATYP_IPV4 = 1
ATYP_DOMAIN = 3
ATYP_IPV6 = 4


class Socks5Server:
    """Local SOCKS5 proxy server that forwards connections through SSH"""

    def __init__(
        self,
        tunnel: Tunnel,
        status_callback: Optional[Callable[[str, TunnelStatus, str], None]] = None
    ):
        self.tunnel = tunnel
        self.status_callback = status_callback
        self.local_port = tunnel.local_port
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self.logger = logging.getLogger(f"Socks5Server.{tunnel.name}")

    def _notify_status(self, status: TunnelStatus, error: str = ""):
        """Notify status change via callback"""
        if self.status_callback:
            self.status_callback(self.tunnel.id, status, error)

    def _connect_ssh(self) -> bool:
        """Establish SSH connection"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.tunnel.ssh_host,
                "port": self.tunnel.ssh_port,
                "username": self.tunnel.ssh_user,
                "timeout": 30,
            }

            if self.tunnel.auth_type == AuthType.PASSWORD:
                connect_kwargs["password"] = self.tunnel.ssh_password
            else:
                connect_kwargs["key_filename"] = self.tunnel.ssh_key_path

            self.logger.info(f"Connecting to SSH server {self.tunnel.ssh_host}:{self.tunnel.ssh_port}...")
            self.ssh_client.connect(**connect_kwargs)
            self.transport = self.ssh_client.get_transport()
            self.logger.info(f"SSH connection established")
            return True

        except paramiko.AuthenticationException as e:
            self.logger.error(f"SSH authentication failed: {e}")
            self._notify_status(TunnelStatus.ERROR, f"Authentication failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"SSH connection failed: {e}")
            self._notify_status(TunnelStatus.ERROR, str(e))
            return False

    def _handle_client(self, client_socket: socket.socket, client_addr: tuple):
        """Handle a single SOCKS5 client connection"""
        try:
            # SOCKS5 handshake - greeting
            header = client_socket.recv(2)
            version = header[0]

            # Check for HTTP traffic (GET, POST, CONNECT, HEAD, etc.)
            # 'C' = 67 (CONNECT)
            if version == 67: 
                 # Likely HTTP CONNECT
                 self._handle_http_connect(client_socket, header)
                 return
            
            # Other HTTP methods (GET, POST, etc) - Basic warning for now
            if version in [71, 80, 72, 79, 68]:
                 self.logger.warning(f"Received HTTP method (byte {version}). Only HTTP CONNECT is currently auto-supported.")
                 self.logger.info(f"Please use HTTPS or SOCKS5.")
                 return

            if version != SOCKS_VERSION:
                self.logger.error(f"Unsupported SOCKS version: {version}")
                return

            nmethods = header[1]
            # Get authentication methods (SOCKS5)
            methods = client_socket.recv(nmethods)

            # We support no authentication
            if AUTH_NONE not in methods:
                client_socket.sendall(struct.pack("!BB", SOCKS_VERSION, 0xFF))  # No acceptable methods
                return

            # Send no auth required
            client_socket.sendall(struct.pack("!BB", SOCKS_VERSION, AUTH_NONE))

            # Receive connection request
            request = client_socket.recv(4)
            if len(request) < 4:
                return

            version, cmd, _, atyp = struct.unpack("!BBBB", request)

            if cmd != CMD_CONNECT:
                # Only support CONNECT command
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 7, 0, ATYP_IPV4, 0, 0)
                client_socket.sendall(reply)
                return

            # Parse destination address
            if atyp == ATYP_IPV4:
                addr_data = client_socket.recv(4)
                dest_addr = socket.inet_ntoa(addr_data)
            elif atyp == ATYP_DOMAIN:
                domain_len = client_socket.recv(1)[0]
                dest_addr = client_socket.recv(domain_len).decode('utf-8')
            elif atyp == ATYP_IPV6:
                addr_data = client_socket.recv(16)
                dest_addr = socket.inet_ntop(socket.AF_INET6, addr_data)
            else:
                return

            # Get destination port
            port_data = client_socket.recv(2)
            dest_port = struct.unpack("!H", port_data)[0]

            self.logger.info(f"Forwarding connection to {dest_addr}:{dest_port}")

            # Open SSH channel to destination
            try:
                if self.transport is None or not self.transport.is_active():
                    raise Exception("SSH transport not available")

                channel = self.transport.open_channel(
                    "direct-tcpip",
                    (dest_addr, dest_port),
                    client_addr
                )

                if channel is None:
                    raise Exception("Failed to open SSH channel")

            except Exception as e:
                self.logger.error(f"Failed to open channel: {e}")
                # Send connection refused
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 5, 0, ATYP_IPV4, 0, 0)
                client_socket.sendall(reply)
                return

            # Send success reply
            bind_addr = client_socket.getsockname()
            reply = struct.pack(
                "!BBBB",
                SOCKS_VERSION, 0, 0, ATYP_IPV4
            ) + socket.inet_aton(bind_addr[0]) + struct.pack("!H", bind_addr[1])
            client_socket.sendall(reply)

            # Forward data between client and SSH channel
            self._forward_data(client_socket, channel)

        except Exception as e:
            self.logger.error(f"Client handler error: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass


    def _handle_http_connect(self, client_socket: socket.socket, initial_bytes: bytes):
        """Handle HTTP CONNECT method for HTTPS proxying"""
        try:
            # We already read 2 bytes. We need to read the rest of the request line.
            # Typical request: CONNECT host:port HTTP/1.1\r\n...
            
            buffer = initial_bytes
            while b'\r\n' not in buffer:
                chunk = client_socket.recv(1024)
                if not chunk:
                    return
                buffer += chunk
                if len(buffer) > 8192: # Safety limit
                    return

            # Parse request line
            headers_end = buffer.find(b'\r\n\r\n')
            if headers_end == -1:
                # Read until headers end if not found
                while b'\r\n\r\n' not in buffer:
                     chunk = client_socket.recv(1024)
                     if not chunk: break
                     buffer += chunk
                     if len(buffer) > 16384: break
                headers_end = buffer.find(b'\r\n\r\n')
            
            if headers_end == -1:
                return # Invalid HTTP request
            
            # Extract request line
            lines = buffer[:headers_end].split(b'\r\n')
            request_line = lines[0].decode('utf-8', errors='ignore')
            parts = request_line.split()
            
            if len(parts) < 2 or parts[0].upper() != 'CONNECT':
                self.logger.warning(f"[HTTP-PROXY] Invalid CONNECT request: {request_line}")
                return

            dest = parts[1] # host:port
            if ':' in dest:
                host, port_str = dest.split(':')
                port = int(port_str)
            else:
                host = dest
                port = 443

            self.logger.info(f"[HTTP-PROXY] HTTP CONNECT to {host}:{port}")

            # Establish SSH Tunnel
            try:
                if self.transport is None or not self.transport.is_active():
                    raise Exception("SSH transport not available")

                channel = self.transport.open_channel(
                    "direct-tcpip",
                    (host, port),
                    client_socket.getpeername()
                )

                if channel is None:
                    raise Exception("Failed to open SSH channel")

                # Send HTTP 200 OK
                client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

                # If there was extra data in buffer (unlikely for CONNECT but possible), send to channel
                extra_data = buffer[headers_end+4:]
                if extra_data:
                    channel.send(extra_data)

                # Forward data
                self._forward_data(client_socket, channel)

            except Exception as e:
                self.logger.error(f"[HTTP-PROXY] Tunnel failed: {e}")
                client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                
        except Exception as e:
            self.logger.error(f"[HTTP-PROXY] Error: {e}")


            # Send no auth required
            client_socket.sendall(struct.pack("!BB", SOCKS_VERSION, AUTH_NONE))

            # Receive connection request
            request = client_socket.recv(4)
            if len(request) < 4:
                return

            version, cmd, _, atyp = struct.unpack("!BBBB", request)

            if cmd != CMD_CONNECT:
                # Only support CONNECT command
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 7, 0, ATYP_IPV4, 0, 0)
                client_socket.sendall(reply)
                return

            # Parse destination address
            if atyp == ATYP_IPV4:
                addr_data = client_socket.recv(4)
                dest_addr = socket.inet_ntoa(addr_data)
            elif atyp == ATYP_DOMAIN:
                domain_len = client_socket.recv(1)[0]
                dest_addr = client_socket.recv(domain_len).decode('utf-8')
            elif atyp == ATYP_IPV6:
                addr_data = client_socket.recv(16)
                dest_addr = socket.inet_ntop(socket.AF_INET6, addr_data)
            else:
                return

            # Get destination port
            port_data = client_socket.recv(2)
            dest_port = struct.unpack("!H", port_data)[0]

            print(f"[SOCKS5] Forwarding connection to {dest_addr}:{dest_port}")

            # Open SSH channel to destination
            try:
                if self.transport is None or not self.transport.is_active():
                    raise Exception("SSH transport not available")

                channel = self.transport.open_channel(
                    "direct-tcpip",
                    (dest_addr, dest_port),
                    client_addr
                )

                if channel is None:
                    raise Exception("Failed to open SSH channel")

            except Exception as e:
                print(f"[SOCKS5] Failed to open channel: {e}")
                # Send connection refused
                reply = struct.pack("!BBBBIH", SOCKS_VERSION, 5, 0, ATYP_IPV4, 0, 0)
                client_socket.sendall(reply)
                return

            # Send success reply
            bind_addr = client_socket.getsockname()
            reply = struct.pack(
                "!BBBB",
                SOCKS_VERSION, 0, 0, ATYP_IPV4
            ) + socket.inet_aton(bind_addr[0]) + struct.pack("!H", bind_addr[1])
            client_socket.sendall(reply)

            # Forward data between client and SSH channel
            self._forward_data(client_socket, channel)

        except Exception as e:
            print(f"[SOCKS5] Client handler error: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _forward_data(self, client_socket: socket.socket, ssh_channel: paramiko.Channel):
        """Forward data between client socket and SSH channel"""
        try:
            sockets = [client_socket, ssh_channel]
            while not self._stop_event.is_set():
                readable, _, _ = select.select(sockets, [], [], 1.0)

                if not readable:
                    # Check if channel or socket is still active
                    if ssh_channel.closed or client_socket.fileno() == -1:
                        break
                    continue

                for sock in readable:
                    if sock is client_socket:
                        data = client_socket.recv(4096)
                        if not data:
                            return
                        ssh_channel.send(data)
                    else:
                        data = ssh_channel.recv(4096)
                        if not data:
                            return
                        client_socket.send(data)

        except Exception as e:
            pass  # Connection closed
        finally:
            try:
                ssh_channel.close()
            except:
                pass

    def start(self) -> bool:
        """Start the SOCKS5 proxy server"""
        self._notify_status(TunnelStatus.CONNECTING)

        # Connect SSH first
        if not self._connect_ssh():
            return False

        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("127.0.0.1", self.local_port))
            self.server_socket.listen(100)
            self.server_socket.settimeout(1.0)  # For checking stop event

            self.running = True
            self._stop_event.clear()

            self.logger.info(f"SOCKS5 proxy running on 127.0.0.1:{self.local_port}")
            self._notify_status(TunnelStatus.RUNNING)

            # Start server loop in background
            server_thread = threading.Thread(target=self._server_loop, daemon=True)
            server_thread.start()
            self._threads.append(server_thread)

            return True

        except Exception as e:
            self.logger.error(f"Server error: {e}")
            self._notify_status(TunnelStatus.ERROR, str(e))
            self.stop()
            return False

    def _server_loop(self):
        """Main server loop to accept connections"""
        try:
            # Accept connections
            while self.running and not self._stop_event.is_set():
                try:
                    if self.server_socket:
                        client_socket, client_addr = self.server_socket.accept()
                        thread = threading.Thread(
                            target=self._handle_client,
                            args=(client_socket, client_addr),
                            daemon=True
                        )
                        thread.start()
                        self._threads.append(thread)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.logger.error(f"Accept error: {e}")
                    break
        finally:
            self.stop()

    def stop(self):
        """Stop the SOCKS5 proxy server"""
        self.running = False
        self._stop_event.set()

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
            self.ssh_client = None

        self.transport = None
        self._notify_status(TunnelStatus.STOPPED)
        if hasattr(self, 'logger'):
             self.logger.info(f"Proxy stopped")

    @property
    def is_active(self) -> bool:
        """Check if the SOCKS5 server is running"""
        return self.running and self.transport is not None and self.transport.is_active()

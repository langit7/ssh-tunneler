"""
Tunnel Data Model
"""
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from enum import Enum


class TunnelType(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"
    DYNAMIC = "dynamic"


class AuthType(str, Enum):
    PASSWORD = "password"
    KEY = "key"


class TunnelStatus(str, Enum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    RUNNING = "running"
    ERROR = "error"


class ProxyType(str, Enum):
    HTTP = "http"
    SOCKS5 = "socks5"


@dataclass
class Tunnel:
    """SSH Tunnel Configuration"""
    name: str
    tunnel_type: TunnelType
    local_port: int
    ssh_host: str
    ssh_port: int
    ssh_user: str
    auth_type: AuthType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    remote_host: str = ""
    remote_port: int = 0
    ssh_password: str = ""
    ssh_key_path: str = ""
    auto_reconnect: bool = False
    status: TunnelStatus = TunnelStatus.STOPPED
    error_message: str = ""
    # Keep-alive settings
    keepalive_enabled: bool = True
    keepalive_interval: int = 30
    keepalive_count_max: int = 3
    # Proxy settings
    proxy_enabled: bool = False
    proxy_type: ProxyType = ProxyType.SOCKS5
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_user: str = ""
    proxy_password: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "tunnel_type": self.tunnel_type.value,
            "local_port": self.local_port,
            "remote_host": self.remote_host,
            "remote_port": self.remote_port,
            "ssh_host": self.ssh_host,
            "ssh_port": self.ssh_port,
            "ssh_user": self.ssh_user,
            "auth_type": self.auth_type.value,
            "ssh_password": self.ssh_password,
            "ssh_key_path": self.ssh_key_path,
            "auto_reconnect": self.auto_reconnect,
            # Keep-alive settings
            "keepalive_enabled": self.keepalive_enabled,
            "keepalive_interval": self.keepalive_interval,
            "keepalive_count_max": self.keepalive_count_max,
            # Proxy settings
            "proxy_enabled": self.proxy_enabled,
            "proxy_type": self.proxy_type.value,
            "proxy_host": self.proxy_host,
            "proxy_port": self.proxy_port,
            "proxy_user": self.proxy_user,
            "proxy_password": self.proxy_password,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tunnel":
        """Create Tunnel from dictionary"""
        # Parse proxy_type with default
        proxy_type_str = data.get("proxy_type", ProxyType.SOCKS5.value)
        try:
            proxy_type = ProxyType(proxy_type_str)
        except ValueError:
            proxy_type = ProxyType.SOCKS5

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            tunnel_type=TunnelType(data["tunnel_type"]),
            local_port=int(data["local_port"]),
            remote_host=data.get("remote_host", ""),
            remote_port=int(data.get("remote_port", 0)),
            ssh_host=data["ssh_host"],
            ssh_port=int(data.get("ssh_port", 22)),
            ssh_user=data["ssh_user"],
            auth_type=AuthType(data["auth_type"]),
            ssh_password=data.get("ssh_password", ""),
            ssh_key_path=data.get("ssh_key_path", ""),
            auto_reconnect=data.get("auto_reconnect", False),
            # Keep-alive settings
            keepalive_enabled=data.get("keepalive_enabled", True),
            keepalive_interval=int(data.get("keepalive_interval", 30)),
            keepalive_count_max=int(data.get("keepalive_count_max", 3)),
            # Proxy settings
            proxy_enabled=data.get("proxy_enabled", False),
            proxy_type=proxy_type,
            proxy_host=data.get("proxy_host", ""),
            proxy_port=int(data.get("proxy_port", 0)),
            proxy_user=data.get("proxy_user", ""),
            proxy_password=data.get("proxy_password", ""),
        )

    def get_forwarding_rule(self) -> str:
        """Get human-readable forwarding rule"""
        if self.tunnel_type == TunnelType.LOCAL:
            return f"localhost:{self.local_port} → {self.remote_host}:{self.remote_port}"
        elif self.tunnel_type == TunnelType.REMOTE:
            return f"{self.ssh_host}:{self.remote_port} → localhost:{self.local_port}"
        else:  # DYNAMIC
            return f"SOCKS5 on localhost:{self.local_port}"

    def get_type_display(self) -> str:
        """Get display name for tunnel type"""
        return {
            TunnelType.LOCAL: "Local",
            TunnelType.REMOTE: "Remote",
            TunnelType.DYNAMIC: "Dynamic",
        }.get(self.tunnel_type, "Unknown")

"""
JSON Storage Service for Tunnel Configurations
"""
import json
import os
from pathlib import Path
from typing import List, Optional
from models.tunnel import Tunnel


class StorageService:
    """Handles persistence of tunnel configurations to JSON file"""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default to tunnels.json in user's app data or current directory
            self.storage_path = Path(__file__).parent.parent / "tunnels.json"

    def load_tunnels(self) -> List[Tunnel]:
        """Load all tunnel configurations from storage"""
        if not self.storage_path.exists():
            return []

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Tunnel.from_dict(t) for t in data.get("tunnels", [])]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error loading tunnels: {e}")
            return []

    def save_tunnels(self, tunnels: List[Tunnel]) -> bool:
        """Save all tunnel configurations to storage"""
        try:
            data = {"tunnels": [t.to_dict() for t in tunnels]}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving tunnels: {e}")
            return False

    def add_tunnel(self, tunnel: Tunnel) -> bool:
        """Add a new tunnel configuration"""
        tunnels = self.load_tunnels()
        tunnels.append(tunnel)
        return self.save_tunnels(tunnels)

    def update_tunnel(self, tunnel_id: str, updated_tunnel: Tunnel) -> bool:
        """Update an existing tunnel configuration"""
        tunnels = self.load_tunnels()
        for i, t in enumerate(tunnels):
            if t.id == tunnel_id:
                updated_tunnel.id = tunnel_id  # Preserve original ID
                tunnels[i] = updated_tunnel
                return self.save_tunnels(tunnels)
        return False

    def delete_tunnel(self, tunnel_id: str) -> bool:
        """Delete a tunnel configuration by ID"""
        tunnels = self.load_tunnels()
        original_count = len(tunnels)
        tunnels = [t for t in tunnels if t.id != tunnel_id]

        if len(tunnels) < original_count:
            return self.save_tunnels(tunnels)
        return False

    def get_tunnel(self, tunnel_id: str) -> Optional[Tunnel]:
        """Get a specific tunnel by ID"""
        tunnels = self.load_tunnels()
        for t in tunnels:
            if t.id == tunnel_id:
                return t
        return None

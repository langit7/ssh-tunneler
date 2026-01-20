import json
import os
from pathlib import Path
from typing import List, Optional
from cryptography.fernet import Fernet
from models.tunnel import Tunnel

class StorageService:
    """Handles persistence of tunnel configurations to JSON file with encryption"""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default to tunnels.json in user's app data or current directory
            self.storage_path = Path(__file__).parent.parent / "tunnels.json"
        
        self.key_path = self.storage_path.parent / ".secret.key"
        self._load_or_generate_key()

    def _load_or_generate_key(self):
        """Load encryption key or generate a new one if missing"""
        if self.key_path.exists():
            try:
                with open(self.key_path, "rb") as key_file:
                    self.key = key_file.read()
                    self.cipher_suite = Fernet(self.key)
            except Exception as e:
                print(f"Error loading key: {e}. Generating new key (old encrypted data will be lost).")
                self._generate_key()
        else:
            self._generate_key()

    def _generate_key(self):
        """Generate and save a new encryption key"""
        self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)
        try:
            with open(self.key_path, "wb") as key_file:
                key_file.write(self.key)
        except Exception as e:
            print(f"Error saving key file: {e}")

    def _encrypt(self, text: str) -> str:
        """Encrypt string"""
        if not text: return ""
        try:
            return self.cipher_suite.encrypt(text.encode()).decode()
        except Exception:
            return ""

    def _decrypt(self, text: str) -> str:
        """Decrypt string"""
        if not text: return ""
        try:
            return self.cipher_suite.decrypt(text.encode()).decode()
        except Exception:
            return text # Return original if decryption fails (backward compatibility)

    def load_tunnels(self) -> List[Tunnel]:
        """Load all tunnel configurations from storage"""
        if not self.storage_path.exists():
            return []

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                tunnels = []
                for t_dict in data.get("tunnels", []):
                    # Handle decryption of SSH password
                    if "ssh_password_enc" in t_dict:
                         t_dict["ssh_password"] = self._decrypt(t_dict.pop("ssh_password_enc"))
                    # Handle decryption of proxy password
                    if "proxy_password_enc" in t_dict:
                         t_dict["proxy_password"] = self._decrypt(t_dict.pop("proxy_password_enc"))
                    
                    try:
                        tunnels.append(Tunnel.from_dict(t_dict))
                    except Exception as e:
                        print(f"Skipping invalid tunnel: {e}")
                
                return tunnels
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error loading tunnels: {e}")
            return []

    def save_tunnels(self, tunnels: List[Tunnel]) -> bool:
        """Save all tunnel configurations to storage"""
        try:
            serialized_tunnels = []
            for t in tunnels:
                data = t.to_dict()
                # Encrypt SSH password
                if data.get("ssh_password"):
                    data["ssh_password_enc"] = self._encrypt(data.pop("ssh_password"))
                else:
                    data.pop("ssh_password", None)
                # Encrypt proxy password
                if data.get("proxy_password"):
                    data["proxy_password_enc"] = self._encrypt(data.pop("proxy_password"))
                else:
                    data.pop("proxy_password", None)
                serialized_tunnels.append(data)

            data_wrapper = {"tunnels": serialized_tunnels}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data_wrapper, f, indent=2)
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

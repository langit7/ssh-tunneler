import customtkinter as ctk
from typing import List, Dict, Callable, Optional, Tuple
from models.tunnel import Tunnel, TunnelStatus, TunnelType
from services.storage import StorageService
from services.ssh_manager import SSHManager
from ui.components import StatusBadge, ActionButton, TunnelTypeChip, Colors
from ui.tunnel_modal import TunnelDialog
import threading

class TunnelRow(ctk.CTkFrame):
    """A row in the tunnel list representing a single tunnel"""
    def __init__(
        self,
        master,
        tunnel: Tunnel,
        status: TunnelStatus,
        on_edit: Callable[[Tunnel], None],
        on_delete: Callable[[str], None],
        on_toggle: Callable[[str, bool], None],
        error_message: str = "",
        **kwargs
    ):
        super().__init__(master, fg_color=("gray95", "gray25"), **kwargs)
        self.tunnel = tunnel
        self.current_status = status
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_toggle = on_toggle

        self.grid_columnconfigure(0, weight=2) # Name
        self.grid_columnconfigure(1, weight=1) # Type
        self.grid_columnconfigure(2, weight=1) # Status
        self.grid_columnconfigure(3, weight=2) # Rule
        self.grid_columnconfigure(4, weight=2) # SSH Server
        self.grid_columnconfigure(5, weight=1) # Actions

        # Name
        self.name_label = ctk.CTkLabel(self, text=tunnel.name, font=("Roboto", 13, "bold"), anchor="w")
        self.name_label.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Type
        self.type_chip = TunnelTypeChip(self, text=tunnel.get_type_display())
        self.type_chip.grid(row=0, column=1, padx=5, sticky="w")

        # Status
        self.status_badge = StatusBadge(self, status, tooltip=error_message)
        self.status_badge.grid(row=0, column=2, padx=5, sticky="w")
        
        # Rule
        self.rule_label = ctk.CTkLabel(self, text=tunnel.get_forwarding_rule(), text_color="gray", font=("Roboto", 12))
        self.rule_label.grid(row=0, column=3, padx=5, sticky="w")
        
        # SSH Server
        self.ssh_label = ctk.CTkLabel(self, text=f"{tunnel.ssh_user}@{tunnel.ssh_host}:{tunnel.ssh_port}", text_color="gray", font=("Roboto", 12))
        self.ssh_label.grid(row=0, column=4, padx=5, sticky="w")
        
        # Actions
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.grid(row=0, column=5, padx=5, sticky="e")
        
        is_running = status in [TunnelStatus.RUNNING, TunnelStatus.CONNECTING]
        self.toggle_btn = ctk.CTkButton(
            self.actions_frame, 
            text="Stop" if is_running else "Start",
            width=60,
            fg_color=Colors.RED_400 if is_running else Colors.GREEN_400,
            hover_color=Colors.RED_700 if is_running else Colors.GREEN_700,
            command=self._on_toggle_click
        )
        self.toggle_btn.pack(side="left", padx=2)
        
        self.edit_btn = ctk.CTkButton(
            self.actions_frame, text="Edit", width=50,
            fg_color=Colors.BLUE_400, hover_color=Colors.BLUE_700,
            command=self._on_edit_click
        )
        self.edit_btn.pack(side="left", padx=2)
        
        self.delete_btn = ctk.CTkButton(
            self.actions_frame, text="Del", width=50,
            fg_color=Colors.RED_400, hover_color=Colors.RED_700,
            command=self._on_delete_click
        )
        self.delete_btn.pack(side="left", padx=2)

    def _on_toggle_click(self):
        is_running = self.current_status in [TunnelStatus.RUNNING, TunnelStatus.CONNECTING]
        self.on_toggle(self.tunnel.id, not is_running)

    def _on_edit_click(self):
        self.on_edit(self.tunnel)

    def _on_delete_click(self):
        self.on_delete(self.tunnel.id)

    def update_status(self, status: TunnelStatus, error_message: str = ""):
        self.current_status = status
        self.status_badge.update_status(status, error_message)
        
        is_running = status in [TunnelStatus.RUNNING, TunnelStatus.CONNECTING]
        self.toggle_btn.configure(
            text="Stop" if is_running else "Start",
            fg_color=Colors.RED_400 if is_running else Colors.GREEN_400,
            hover_color=Colors.RED_700 if is_running else Colors.GREEN_700
        )


from services.logger import setup_logger

class LogPanel(ctk.CTkFrame):
    """Scrollable log viewer panel"""
    def __init__(self, master, **kwargs):
        super().__init__(master, height=150, **kwargs)
        self.pack_propagate(False)
        
        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 11))
        self.textbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.textbox.configure(state="disabled") # Read-only initially
        
    def append(self, message: str):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

class Dashboard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.storage = StorageService()
        self.ssh_manager = SSHManager(status_callback=self._on_tunnel_status_change)
        
        self.tunnels: List[Tunnel] = []
        self.tunnel_rows: Dict[str, TunnelRow] = {}
        self.status_cache: Dict[str, Tuple[TunnelStatus, str]] = {}
        
        self._init_ui()
        
        # Setup Logger
        setup_logger(self._on_log_message)
        
        self.refresh_tunnels()

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Scroll area expands
        self.grid_rowconfigure(2, weight=0) # Log panel fixed height

        # Header
        self.header = ctk.CTkFrame(self, fg_color=("gray90", "gray15"), height=60, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False) # Fixed height
        
        ctk.CTkLabel(self.header, text="SSH Tunnel Manager", font=("Roboto", 20, "bold")).pack(side="left", padx=20)
        
        self.header_btns = ctk.CTkFrame(self.header, fg_color="transparent")
        self.header_btns.pack(side="right", padx=20)
        
        ctk.CTkButton(self.header_btns, text="New Tunnel", command=self._on_new_tunnel, fg_color=Colors.BLUE_600).pack(side="right", padx=5)
        ctk.CTkButton(self.header_btns, text="Stop All", command=self._on_stop_all, fg_color=Colors.RED_700).pack(side="right", padx=5)
        ctk.CTkButton(self.header_btns, text="Start All", command=self._on_start_all, fg_color=Colors.GREEN_700).pack(side="right", padx=5)

        # Content Area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        self.empty_state_lbl = ctk.CTkLabel(self, text="No SSH Tunnels.\nClick 'New SSH Tunnel' to create one.", font=("Roboto", 16))
        
        # Log Panel
        self.log_panel = LogPanel(self)
        self.log_panel.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _on_log_message(self, message: str):
        # Update on main thread
        self.after(0, lambda: self.log_panel.append(message))

    def refresh_tunnels(self):
        # Clear existing rows
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.tunnel_rows.clear()
        
        self.tunnels = self.storage.load_tunnels()
        
        if not self.tunnels:
            self.empty_state_lbl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_state_lbl.place_forget()
            for tunnel in self.tunnels:
                status, error = self.status_cache.get(tunnel.id, (TunnelStatus.STOPPED, ""))
                row = TunnelRow(
                    self.scroll_frame,
                    tunnel=tunnel,
                    status=status,
                    on_edit=self._on_edit_tunnel,
                    on_delete=self._on_delete_tunnel,
                    on_toggle=self._on_toggle_tunnel,
                    error_message=error
                )
                row.pack(fill="x", pady=5)
                self.tunnel_rows[tunnel.id] = row

    def _on_tunnel_status_change(self, tunnel_id: str, status: TunnelStatus, error: str):
        # Schedule update on main thread
        self.after(0, lambda: self._update_row_status(tunnel_id, status, error))

    def _update_row_status(self, tunnel_id: str, status: TunnelStatus, error: str):
        self.status_cache[tunnel_id] = (status, error)
        if tunnel_id in self.tunnel_rows:
            self.tunnel_rows[tunnel_id].update_status(status, error)

    # Actions
    def _on_new_tunnel(self):
        TunnelDialog(self.winfo_toplevel(), on_save=self._save_new_tunnel)

    def _save_new_tunnel(self, tunnel: Tunnel):
        self.storage.add_tunnel(tunnel)
        self.refresh_tunnels()

    def _on_edit_tunnel(self, tunnel: Tunnel):
        TunnelDialog(self.winfo_toplevel(), on_save=self._save_edited_tunnel, tunnel=tunnel)

    def _save_edited_tunnel(self, tunnel: Tunnel):
        self.storage.update_tunnel(tunnel.id, tunnel)
        self.refresh_tunnels()

    def _on_delete_tunnel(self, tunnel_id: str):
        self.ssh_manager.stop_tunnel(tunnel_id)
        self.storage.delete_tunnel(tunnel_id)
        self.refresh_tunnels()

    def _on_toggle_tunnel(self, tunnel_id: str, start: bool):
        tunnel = self.storage.get_tunnel(tunnel_id)
        if not tunnel:
            return
            
        if start:
            threading.Thread(target=self.ssh_manager.start_tunnel, args=(tunnel,), daemon=True).start()
        else:
            threading.Thread(target=self.ssh_manager.stop_tunnel, args=(tunnel_id,), daemon=True).start()

    def _on_start_all(self):
        threading.Thread(target=self.ssh_manager.start_all, args=(self.tunnels,), daemon=True).start()

    def _on_stop_all(self):
        threading.Thread(target=self.ssh_manager.stop_all, daemon=True).start()

    def cleanup(self):
        self.ssh_manager.stop_all()

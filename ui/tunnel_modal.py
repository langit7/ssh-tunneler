import customtkinter as ctk
from typing import Optional, Callable
from models.tunnel import Tunnel, TunnelType, AuthType, TunnelStatus
import uuid

class TunnelDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        on_save: Callable[[Tunnel], None],
        tunnel: Optional[Tunnel] = None
    ):
        super().__init__(master)
        self.on_save = on_save
        self.tunnel = tunnel
        
        self.title("Edit Tunnel" if tunnel else "New SSH Tunnel")
        self.geometry("600x750")
        self.resizable(False, False)
        
        # Make modal
        self.transient(master)
        self.grab_set()
        
        self._init_ui()
        if tunnel:
            self._load_tunnel_data(tunnel)

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main Scrollable Frame
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll_frame.grid_columnconfigure(1, weight=1)

        # Helper to add fields
        self.row_idx = 0
        def add_field(label_text, widget):
            ctk.CTkLabel(self.scroll_frame, text=label_text, anchor="w").grid(
                row=self.row_idx, column=0, sticky="w", pady=(10,0)
            )
            widget.grid(row=self.row_idx + 1, column=0, columnspan=2, sticky="ew", pady=(5,0))
            self.row_idx += 2

        # --- Name ---
        self.name_entry = ctk.CTkEntry(self.scroll_frame, placeholder_text="My Production Tunnel")
        add_field("Tunnel Name", self.name_entry)

        # --- Type ---
        self.type_var = ctk.StringVar(value=TunnelType.LOCAL.value)
        self.type_menu = ctk.CTkOptionMenu(
            self.scroll_frame, 
            variable=self.type_var,
            values=[t.value for t in TunnelType],
            command=self._on_type_change
        )
        add_field("Tunnel Type", self.type_menu)

        # --- Local Port ---
        self.local_port_entry = ctk.CTkEntry(self.scroll_frame, placeholder_text="8080")
        add_field("Local Port", self.local_port_entry)

        # --- Remote Host/Port (Container) ---
        self.remote_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.remote_frame.grid_columnconfigure(0, weight=3)
        self.remote_frame.grid_columnconfigure(1, weight=1)
        
        self.remote_host_entry = ctk.CTkEntry(self.remote_frame, placeholder_text="localhost")
        self.remote_port_entry = ctk.CTkEntry(self.remote_frame, placeholder_text="80")
        
        ctk.CTkLabel(self.scroll_frame, text="Remote Destination (Host : Port)", anchor="w").grid(
             row=self.row_idx, column=0, sticky="w", pady=(10,0)
        )
        self.remote_frame.grid(row=self.row_idx+1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.remote_host_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.remote_port_entry.grid(row=0, column=1, sticky="ew")
        self.row_idx += 2

        # Divider
        ctk.CTkFrame(self.scroll_frame, height=2, fg_color="grey30").grid(
            row=self.row_idx, column=0, columnspan=2, sticky="ew", pady=20
        )
        self.row_idx += 1
        
        ctk.CTkLabel(self.scroll_frame, text="SSH Connection Details", font=("Roboto", 16, "bold"), anchor="w").grid(
            row=self.row_idx, column=0, sticky="w", pady=(0, 10)
        )
        self.row_idx += 1

        # --- SSH Host/Port ---
        self.ssh_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.ssh_frame.grid_columnconfigure(0, weight=3)
        self.ssh_frame.grid_columnconfigure(1, weight=1)
        
        self.ssh_host_entry = ctk.CTkEntry(self.ssh_frame, placeholder_text="ssh.example.com")
        self.ssh_port_entry = ctk.CTkEntry(self.ssh_frame, placeholder_text="22")
        
        ctk.CTkLabel(self.scroll_frame, text="SSH Server (Host : Port)", anchor="w").grid(
             row=self.row_idx, column=0, sticky="w", pady=(10,0)
        )
        self.ssh_frame.grid(row=self.row_idx+1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.ssh_host_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.ssh_port_entry.grid(row=0, column=1, sticky="ew")
        self.row_idx += 2

        # --- SSH User ---
        self.ssh_user_entry = ctk.CTkEntry(self.scroll_frame, placeholder_text="root")
        add_field("SSH Username", self.ssh_user_entry)

        # --- Auth Type ---
        self.auth_type_var = ctk.StringVar(value=AuthType.PASSWORD.value)
        self.auth_type_menu = ctk.CTkOptionMenu(
            self.scroll_frame,
            variable=self.auth_type_var,
            values=[t.value for t in AuthType],
            command=self._on_auth_change
        )
        add_field("Authentication Method", self.auth_type_menu)

        # --- Password / Key ---
        self.secret_label = ctk.CTkLabel(self.scroll_frame, text="Password", anchor="w")
        self.secret_label.grid(row=self.row_idx, column=0, sticky="w", pady=(10,0))
        
        self.secret_entry = ctk.CTkEntry(self.scroll_frame, show="*")
        self.secret_entry.grid(row=self.row_idx + 1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.row_idx += 2

        self.key_picker_btn = ctk.CTkButton(self.scroll_frame, text="Browse Key...", command=self._pick_key_file)
        self.key_picker_btn.grid(row=self.row_idx-1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.key_picker_btn.grid_remove() # Hidden by default
        
        # --- Auto Reconnect ---
        self.auto_reconnect_var = ctk.BooleanVar(value=True)
        self.auto_reconnect_switch = ctk.CTkSwitch(self.scroll_frame, text="Auto Reconnect", variable=self.auto_reconnect_var)
        self.auto_reconnect_switch.grid(row=self.row_idx, column=0, sticky="w", pady=20)
        self.row_idx += 1

        # Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        
        self.save_btn = ctk.CTkButton(self.btn_frame, text="Save Tunnel", command=self._save)
        self.save_btn.pack(side="right", padx=5)
        
        self.cancel_btn = ctk.CTkButton(self.btn_frame, text="Cancel", fg_color="transparent", border_width=1, command=self.destroy)
        self.cancel_btn.pack(side="right", padx=5)

    def _on_type_change(self, choice):
        if choice == TunnelType.DYNAMIC.value:
            self.remote_host_entry.configure(state="disabled", fg_color="grey20")
            self.remote_port_entry.configure(state="disabled", fg_color="grey20")
        else:
            self.remote_host_entry.configure(state="normal", fg_color=["#F9F9FA", "#343638"])
            self.remote_port_entry.configure(state="normal", fg_color=["#F9F9FA", "#343638"])

    def _on_auth_change(self, choice):
        if choice == AuthType.PASSWORD.value:
            self.secret_label.configure(text="Password")
            self.secret_entry.grid()
            self.key_picker_btn.grid_remove()
        else:
            self.secret_label.configure(text="Private Key Path")
            self.secret_entry.grid()
            self.key_picker_btn.grid()

    def _pick_key_file(self):
        file_path = ctk.filedialog.askopenfilename(filetypes=[("Private Keys", "*"), ("All Files", "*.*")])
        if file_path:
            self.secret_entry.delete(0, "end")
            self.secret_entry.insert(0, file_path)

    def _load_tunnel_data(self, tunnel: Tunnel):
        self.name_entry.insert(0, tunnel.name)
        self.type_var.set(tunnel.tunnel_type.value)
        self.local_port_entry.insert(0, str(tunnel.local_port))
        
        if tunnel.remote_host:
            self.remote_host_entry.insert(0, tunnel.remote_host)
        if tunnel.remote_port:
            self.remote_port_entry.insert(0, str(tunnel.remote_port))
            
        self.ssh_host_entry.insert(0, tunnel.ssh_host)
        self.ssh_port_entry.insert(0, str(tunnel.ssh_port))
        self.ssh_user_entry.insert(0, tunnel.ssh_user)
        
        self.auth_type_var.set(tunnel.auth_type.value)
        self._on_auth_change(tunnel.auth_type.value)
        
        if tunnel.auth_type == AuthType.PASSWORD:
            self.secret_entry.insert(0, tunnel.ssh_password or "")
        else:
            self.secret_entry.insert(0, tunnel.ssh_key_path or "")
            
        self.auto_reconnect_var.set(tunnel.auto_reconnect)
        self._on_type_change(tunnel.tunnel_type.value)

    def _save(self):
        try:
            # Validate numeric fields
            try:
                l_port = int(self.local_port_entry.get())
                s_port = int(self.ssh_port_entry.get())
                r_port = int(self.remote_port_entry.get()) if self.remote_port_entry.get() else 0
            except ValueError:
                self.focus() # Make sure to bring focus back if creating simple error dialog
                # Ideally show error message
                return

            new_tunnel = Tunnel(
                id=self.tunnel.id if self.tunnel else str(uuid.uuid4()),
                name=self.name_entry.get(),
                tunnel_type=TunnelType(self.type_var.get()),
                local_port=l_port,
                remote_host=self.remote_host_entry.get(),
                remote_port=r_port,
                ssh_host=self.ssh_host_entry.get(),
                ssh_port=s_port,
                ssh_user=self.ssh_user_entry.get(),
                auth_type=AuthType(self.auth_type_var.get()),
                ssh_password=self.secret_entry.get() if self.auth_type_var.get() == AuthType.PASSWORD.value else None,
                ssh_key_path=self.secret_entry.get() if self.auth_type_var.get() == AuthType.KEY_FILE.value else None,
                auto_reconnect=self.auto_reconnect_var.get()
            )
            
            self.on_save(new_tunnel)
            self.destroy()
            
        except Exception as e:
            print(f"Error saving tunnel: {e}")

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

        self.row_idx = 0
        
        # --- Type (First, as it controls layout) ---
        ctk.CTkLabel(self.scroll_frame, text="Tunnel Type", anchor="w").grid(
             row=self.row_idx, column=0, sticky="w", pady=(10,0)
        )
        self.type_var = ctk.StringVar(value=TunnelType.LOCAL.value)
        self.type_menu = ctk.CTkOptionMenu(
            self.scroll_frame, 
            variable=self.type_var,
            values=[t.value for t in TunnelType],
            command=self._on_type_change
        )
        self.type_menu.grid(row=self.row_idx + 1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.row_idx += 2

        # --- Name ---
        ctk.CTkLabel(self.scroll_frame, text="Tunnel Name", anchor="w").grid(
             row=self.row_idx, column=0, sticky="w", pady=(10,0)
        )
        self.name_entry = ctk.CTkEntry(self.scroll_frame, placeholder_text="My Tunnel")
        self.name_entry.grid(row=self.row_idx + 1, column=0, columnspan=2, sticky="ew", pady=(5,0))
        self.row_idx += 2

        # Divider
        ctk.CTkFrame(self.scroll_frame, height=2, fg_color="grey30").grid(
            row=self.row_idx, column=0, columnspan=2, sticky="ew", pady=20
        )
        self.row_idx += 1

        # Container for dynamic fields
        self.dynamic_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.dynamic_frame.grid(row=self.row_idx, column=0, columnspan=2, sticky="ew")
        self.dynamic_frame.grid_columnconfigure(1, weight=1)

        # Initialize widgets (created once, repacked as needed)
        self._create_widgets()
        
        # Initial render
        self._render_dynamic_fields(self.type_var.get())

        # Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=20)
        
        self.save_btn = ctk.CTkButton(self.btn_frame, text="Save Tunnel", command=self._save)
        self.save_btn.pack(side="right", padx=5)
        
        self.cancel_btn = ctk.CTkButton(self.btn_frame, text="Cancel", fg_color="transparent", border_width=1, command=self.destroy)
        self.cancel_btn.pack(side="right", padx=5)

    def _create_widgets(self):
        """Create all potential widgets to be used in dynamic forms"""
        # Local Port
        self.local_port_entry = ctk.CTkEntry(self.dynamic_frame, placeholder_text="8080")
        
        # Remote (Destination) Host/Port
        self.remote_host_entry = ctk.CTkEntry(self.dynamic_frame, placeholder_text="localhost")
        self.remote_port_entry = ctk.CTkEntry(self.dynamic_frame, placeholder_text="80")
        
        # SSH Host/Port
        self.ssh_host_entry = ctk.CTkEntry(self.dynamic_frame, placeholder_text="ssh.example.com")
        self.ssh_port_entry = ctk.CTkEntry(self.dynamic_frame, placeholder_text="22")
        self.ssh_user_entry = ctk.CTkEntry(self.dynamic_frame, placeholder_text="root")
        
        # Auth
        self.auth_type_var = ctk.StringVar(value=AuthType.PASSWORD.value)
        self.auth_type_menu = ctk.CTkOptionMenu(
            self.dynamic_frame,
            variable=self.auth_type_var,
            values=[t.value for t in AuthType],
            command=self._on_auth_change
        )
        self.secret_entry = ctk.CTkEntry(self.dynamic_frame, show="*")
        self.key_picker_btn = ctk.CTkButton(self.dynamic_frame, text="Browse Key...", command=self._pick_key_file)
        
        # Auto Reconnect
        self.auto_reconnect_var = ctk.BooleanVar(value=True)
        self.auto_reconnect_switch = ctk.CTkSwitch(self.dynamic_frame, text="Auto Reconnect", variable=self.auto_reconnect_var)

    def _render_dynamic_fields(self, tunnel_type: str):
        """Re-pack widgets based on tunnel type. Recreates widgets to handle parent changes."""
        
        # 1. Save current values from existing widgets if they exist
        current_values = {}
        msg_widgets = {
            'local_port': getattr(self, 'local_port_entry', None),
            'remote_host': getattr(self, 'remote_host_entry', None),
            'remote_port': getattr(self, 'remote_port_entry', None),
            'ssh_host': getattr(self, 'ssh_host_entry', None),
            'ssh_port': getattr(self, 'ssh_port_entry', None),
            'ssh_user': getattr(self, 'ssh_user_entry', None),
            'secret': getattr(self, 'secret_entry', None),
        }
        
        for key, widget in msg_widgets.items():
            if widget and widget.winfo_exists():
                try:
                    current_values[key] = widget.get()
                except:
                    pass

        # 2. Clear current grid and destroy children to prevent memory leaks/zombie widgets
        for widget in self.dynamic_frame.winfo_children():
            widget.destroy()
            
        # 3. Helpers to create widgets on the fly
        row = 0
        def add_header(text):
            nonlocal row
            ctk.CTkLabel(self.dynamic_frame, text=text, font=("Roboto", 16, "bold"), anchor="w").grid(row=row, column=0, sticky="w", pady=(0, 10))
            row += 1

        def add_divider():
            nonlocal row
            ctk.CTkFrame(self.dynamic_frame, height=2, fg_color="grey30").grid(row=row, column=0, columnspan=2, sticky="ew", pady=20)
            row += 1

        def create_entry(placeholder, value_key=None, show=None):
            e = ctk.CTkEntry(self.dynamic_frame, placeholder_text=placeholder, show=show)
            if value_key and value_key in current_values:
                e.insert(0, current_values[value_key])
            return e

        def add_row(label, widget, col_span=2):
            nonlocal row
            # Widget is already created with dynamic_frame as master (default) or passed in
            if label:
                ctk.CTkLabel(self.dynamic_frame, text=label, anchor="w").grid(
                    row=row, column=0, sticky="w", pady=(10,0)
                )
                row += 1
            widget.grid(row=row, column=0, columnspan=col_span, sticky="ew", pady=(5,0))
            row += 1

        def add_dual_row(label, widget1, widget2):
            nonlocal row
            if label:
                ctk.CTkLabel(self.dynamic_frame, text=label, anchor="w").grid(
                    row=row, column=0, sticky="w", pady=(10,0)
                )
                row += 1
            f = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5,0))
            f.grid_columnconfigure(0, weight=3)
            f.grid_columnconfigure(1, weight=1)
            
            # Reparenting via configure(master=...) fails in CustomTkinter. 
            # We must recreate widgets with 'f' as master.
            # But the widgets passed in might be created with dynamic_frame as master.
            # Since we are recreating everything inside this function now (see below), 
            # we should pass the FACTORY/Creator or just create them here.
            pass # Logic moved inline below

        # --- Recreate Widgets Logic ---
        # We define the widget attributes again so other methods (save) can access them.
        
        # -- Helpers for section creation --
        
        def create_ssh_section():
            nonlocal row
            add_divider()
            add_header("SSH Connection Details")
            
            # SSH Host/Port (Dual)
            ctk.CTkLabel(self.dynamic_frame, text="SSH Server (Host : Port)", anchor="w").grid(row=row, column=0, sticky="w", pady=(10,0))
            row += 1
            f = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5,0))
            f.grid_columnconfigure(0, weight=3)
            f.grid_columnconfigure(1, weight=1)
            
            self.ssh_host_entry = ctk.CTkEntry(f, placeholder_text="ssh.example.com")
            if 'ssh_host' in current_values: self.ssh_host_entry.insert(0, current_values['ssh_host'])
            
            self.ssh_port_entry = ctk.CTkEntry(f, placeholder_text="22")
            if 'ssh_port' in current_values: self.ssh_port_entry.insert(0, current_values['ssh_port'])
            
            self.ssh_host_entry.grid(row=0, column=0, sticky="ew", padx=(0,5))
            self.ssh_port_entry.grid(row=0, column=1, sticky="ew")
            row += 1

            # User
            self.ssh_user_entry = create_entry("root", 'ssh_user')
            add_row("SSH Username", self.ssh_user_entry)

            # Auth Type
            # We reused self.auth_type_menu, but we can't reparent it easily. 
            # It's better to recreate it.
            self.auth_type_menu = ctk.CTkOptionMenu(
                self.dynamic_frame,
                variable=self.auth_type_var, # Variable persists
                values=[t.value for t in AuthType],
                command=self._on_auth_change
            )
            add_row("Authentication Method", self.auth_type_menu)

            # Secret
            self.secret_entry = create_entry("", 'secret', show="*")
            label_text = "Password" if self.auth_type_var.get() == AuthType.PASSWORD.value else "Private Key Path"
            add_row(label_text, self.secret_entry)
            
            # Key Picker
            if self.auth_type_var.get() != AuthType.PASSWORD.value:
                self.key_picker_btn = ctk.CTkButton(self.dynamic_frame, text="Browse Key...", command=self._pick_key_file)
                add_row("", self.key_picker_btn)
            else:
                self.key_picker_btn = None # Or just don't create it


        # --- Main Layout ---
        
        if tunnel_type == TunnelType.LOCAL.value:
            # 1. Local Port
            self.local_port_entry = create_entry("8080", 'local_port')
            add_row("Local Forwarding Port", self.local_port_entry)
            
            # 2. SSH
            create_ssh_section()
            
            # 3. Remote Destination
            add_divider()
            add_header("Destination Server")
            
            ctk.CTkLabel(self.dynamic_frame, text="Remote Destination (Host : Port)", anchor="w").grid(row=row, column=0, sticky="w", pady=(10,0))
            row += 1
            f = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5,0))
            f.grid_columnconfigure(0, weight=3)
            f.grid_columnconfigure(1, weight=1)
            
            self.remote_host_entry = ctk.CTkEntry(f, placeholder_text="localhost")
            if 'remote_host' in current_values: self.remote_host_entry.insert(0, current_values['remote_host'])
            
            self.remote_port_entry = ctk.CTkEntry(f, placeholder_text="80")
            if 'remote_port' in current_values: self.remote_port_entry.insert(0, current_values['remote_port'])
            
            self.remote_host_entry.grid(row=0, column=0, sticky="ew", padx=(0,5))
            self.remote_port_entry.grid(row=0, column=1, sticky="ew")
            row += 1

        elif tunnel_type == TunnelType.REMOTE.value:
            # 1. Forwarding Port (Remote Port on Server)
            # In Tunnel model (and ssh_manager), 'local_port' is used as the BIND port for both Local and Remote tunnels.
            # So for Remote tunnel, 'local_port' is the port on the SSH Server.
            self.local_port_entry = create_entry("8080", 'local_port')
            add_row("Remote Forwarding Port (on SSH Server)", self.local_port_entry)

            # 2. SSH
            create_ssh_section()

            # 3. Local Destination
            add_divider()
            add_header("Local Destination Server")
            
            # Destination Host/Port
            # 'remote_host' is the destination host.
            # 'remote_port' is the destination port.
            
            ctk.CTkLabel(self.dynamic_frame, text="Destination (accessible by this PC)", anchor="w").grid(row=row, column=0, sticky="w", pady=(10,0))
            row += 1
            f = ctk.CTkFrame(self.dynamic_frame, fg_color="transparent")
            f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(5,0))
            f.grid_columnconfigure(0, weight=3)
            f.grid_columnconfigure(1, weight=1)
            
            self.remote_host_entry = ctk.CTkEntry(f, placeholder_text="localhost")
            if 'remote_host' in current_values: self.remote_host_entry.insert(0, current_values['remote_host'])
            
            self.remote_port_entry = ctk.CTkEntry(f, placeholder_text="80")
            if 'remote_port' in current_values: self.remote_port_entry.insert(0, current_values['remote_port'])
            
            self.remote_host_entry.grid(row=0, column=0, sticky="ew", padx=(0,5))
            self.remote_port_entry.grid(row=0, column=1, sticky="ew")
            row += 1

        elif tunnel_type == TunnelType.DYNAMIC.value:
            # 1. Forwarded Port (Local SOCKS port) -> Maps to `local_port`
            self.local_port_entry = create_entry("1080", 'local_port')
            add_row("Local SOCKS Port", self.local_port_entry)
            
            # 2. SSH
            create_ssh_section()
            
            # 3. Remote Dest is Unused for Dynamic
            # Ensure attributes exist to avoid AttributeError in _save if it tries .get() on None (though _save checks existance?)
            # _save: r_port = int(self.remote_port_entry.get()) if self.remote_port_entry.get() else 0
            # CustomTkinter Entry.get() might fail if widget is destroyed/None.
            # We should set dummy objects or handle in save.
            # Actually, we define them as None if not used, so _save will crash.
            # We need to handle that in _save. OR create hidden dummy widgets.
            # Better to handle in _save or create hidden. Hidden is safer to keep _save simple.
            
            self.remote_host_entry = ctk.CTkEntry(self.dynamic_frame) # Hidden
            self.remote_port_entry = ctk.CTkEntry(self.dynamic_frame) # Hidden

        # Add Auto Reconnect
        self.auto_reconnect_switch = ctk.CTkSwitch(self.dynamic_frame, text="Auto Reconnect", variable=self.auto_reconnect_var)
        add_row("", self.auto_reconnect_switch)

    def _on_type_change(self, choice):
        self._render_dynamic_fields(choice)

    def _on_auth_change(self, choice):
        # We need to refresh layout to toggle password/key field
        self._render_dynamic_fields(self.type_var.get())
        
        # Restore logic for label text update is handled in _render_dynamic_fields
        if choice == AuthType.PASSWORD.value:
             self.secret_label.configure(text="Password") if hasattr(self, 'secret_label') else None
        else:
             self.secret_label.configure(text="Private Key Path") if hasattr(self, 'secret_label') else None

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
        
        if tunnel.auth_type == AuthType.PASSWORD:
            self.secret_entry.insert(0, tunnel.ssh_password or "")
        else:
            self.secret_entry.insert(0, tunnel.ssh_key_path or "")
            
        self.auto_reconnect_var.set(tunnel.auto_reconnect)
        
        # Trigger layout update
        self._render_dynamic_fields(tunnel.tunnel_type.value)

    def _save(self):
        try:
            # Validate numeric fields
            try:
                l_port = int(self.local_port_entry.get())
                s_port = int(self.ssh_port_entry.get())
                r_port = int(self.remote_port_entry.get()) if self.remote_port_entry.get() else 0
            except ValueError:
                self.focus()
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
                # FIXED: Use getattr or direct string check if Enum doesn't have KEY_FILE (it likely has KEY based on previous error)
                # Checking models/tunnel.py would be best, but assuming 'key_file' value or similar.
                # If error was "no attribute KEY_FILE", it means AuthType.KEY_FILE doesn't exist.
                # I should check what AuthType actually has.
                ssh_key_path=self.secret_entry.get() if self.auth_type_var.get() != AuthType.PASSWORD.value else None,
                auto_reconnect=self.auto_reconnect_var.get()
            )
            
            self.on_save(new_tunnel)
            self.destroy()
            
        except Exception as e:
            print(f"Error saving tunnel: {e}")

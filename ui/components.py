import customtkinter as ctk
from models.tunnel import TunnelStatus

class Colors:
    GREEN_400 = "#4ade80"
    GREEN_700 = "#15803d"
    RED_400 = "#f87171"
    RED_700 = "#b91c1c"
    BLUE_400 = "#60a5fa"
    BLUE_600 = "#2563eb"
    BLUE_700 = "#1d4ed8"
    ORANGE_400 = "#fb923c"
    ORANGE_700 = "#c2410c"
    GREY_400 = "#9ca3af"
    GREY_600 = "#4b5563"
    GREY_800 = "#1f2937"
    GREY_900 = "#111827"
    YELLOW_400 = "#facc15"
    WHITE = "#ffffff"

class StatusBadge(ctk.CTkFrame):
    def __init__(self, master, status: TunnelStatus, tooltip: str = "", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.status_label = ctk.CTkLabel(
            self,
            text=status.value.upper(),
            text_color=self._get_color(status),
            font=("Roboto", 12, "bold")
        )
        self.status_label.pack(side="left")
        
        # Simple tooltip simulation via hover could be added here if needed
        # For now we'll stick to clear text status

    def update_status(self, status: TunnelStatus, error: str = ""):
        self.status_label.configure(text=status.value.upper(), text_color=self._get_color(status))
        # If there's an error, we could potentially show it or log it.
        # CTk doesn't have built-in tooltips, so we'll rely on the main status or logging.

    def _get_color(self, status: TunnelStatus):
        if status == TunnelStatus.RUNNING:
            return Colors.GREEN_400
        elif status == TunnelStatus.CONNECTING:
            return Colors.YELLOW_400
        elif status == TunnelStatus.ERROR:
            return Colors.RED_400
        else:
            return Colors.GREY_400

class TunnelTypeChip(ctk.CTkFrame):
    def __init__(self, master, text: str, **kwargs):
        super().__init__(master, corner_radius=6, fg_color=Colors.GREY_800, **kwargs)
        self.label = ctk.CTkLabel(
            self,
            text=text,
            text_color=Colors.BLUE_400,
            font=("Roboto", 11)
        )
        self.label.pack(padx=8, pady=2)

class ActionButton(ctk.CTkButton):
    def __init__(self, master, text="", icon=None, **kwargs):
        # icon support in CTk requires CTkImage, usually from PIL.
        # For simplicity/size we'll use text or basic unicode symbols if icon is None
        super().__init__(master, text=text, height=28, width=28 if not text else 100, **kwargs)

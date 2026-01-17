"""
SSH Tunnel Manager - Desktop Application
A cross-platform GUI for managing SSH tunnels.
"""
import customtkinter as ctk
from ui.dashboard import Dashboard
import sys

# Configure appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SSH Tunnel Manager")
        self.geometry("1100x700")
        
        # Dashboard
        self.dashboard = Dashboard(self)
        self.dashboard.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.dashboard.cleanup()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = App()
    app.mainloop()

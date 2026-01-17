import logging
import threading
from typing import Callable

class GuiLogHandler(logging.Handler):
    """Custom logging handler that sends logs to a GUI callback"""
    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(msg)
        except Exception:
            self.handleError(record)

def setup_logger(gui_callback: Callable[[str], None]):
    """Configure the logging system"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

    # GUI Handler
    gui_handler = GuiLogHandler(gui_callback)
    gui_handler.setFormatter(formatter)
    root_logger.addHandler(gui_handler)

    # Console Handler (keep stdout working)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.info("Logging initialized")

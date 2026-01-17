# ssh-tunneler

A modern, cross-platform desktop GUI application for managing SSH tunnels. Built with **CustomTkinter** for a native look and feel.

It supports Local, Remote, and Dynamic port forwarding, with built-in **dual protocol support** (SOCKS5 + HTTP) for dynamic tunnels.

## Features

- 🎨 **Modern GUI** - Clean, dark-themed interface built with CustomTkinter
- 🔒 **Local Port Forwarding** - Map local ports to remote servers via SSH
- 🔄 **Remote Port Forwarding** - Expose local services to remote networks
- 🌐 **Dynamic Port Forwarding (Dual Mode)** 
    - Works as a standard **SOCKS5** proxy
    - **NEW!** Automatically detects and handles **HTTP CONNECT** requests (HTTPS proxy), allowing you to use it with clients that only support HTTP proxies.
- 📝 **Live Logging** - View real-time connection logs, traffic events, and errors directly in the GUI
- 🔑 **Authentication** - Password or Private Key (PEM/PPK) support
- 🔁 **Auto-Reconnect** - Automatic reconnection on network changes
- 💾 **Persistent Storage** - Save and load tunnel configurations

## Requirements

- Python 3.9 or higher
- Windows / macOS / Linux

## Quick Start

### 1. Create Virtual Environment

```bash
# Navigate to project directory
cd tunneler

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Application

```bash
python main.py
```

The application will launch.

## Building Executable (EXE)

### Using PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "ssh-tunneler" --icon=assets/icon.ico main.py
```

The output file will be in `dist/ssh-tunneler.exe`.

## Project Structure

```
tunneler/
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies (`customtkinter`, `paramiko`, etc.)
├── README.md            # This file
├── models/
│   └── tunnel.py        # Tunnel data model
├── services/
│   ├── storage.py       # JSON persistence
│   ├── ssh_manager.py   # SSH connection manager
│   ├── socks5_server.py # SOCKS5/HTTP Proxy server
│   └── logger.py        # Centralized logging service
└── ui/
    ├── dashboard.py     # Main dashboard view
    ├── tunnel_modal.py  # Configuration dialog
    └── components.py    # Reusable UI components
```

## Usage

1. Click **"New Tunnel"** to create a new tunnel.
2. Select tunnel type:
   - **LOCAL**: Access a remote service locally.
   - **REMOTE**: Expose a local service to the remote server.
   - **DYNAMIC**: Create a proxy (SOCKS5/HTTP) to browse via the remote server.
3. Fill in the SSH details (Host, Port, User, Key/Password).
4. Click **Save**.
5. Click **Start** to connect.
6. Monitor the **Log Panel** at the bottom for connection status.

### Using Dynamic Tunnels (Proxy)

When you start a **DYNAMIC** tunnel (e.g., on port 1080), you can use it with **any** client:

- **SOCKS5 Client**: `curl -x socks5h://localhost:1080 http://example.com`
- **HTTP Proxy Client**: `curl -x http://localhost:1080 http://example.com`
- **Browser**: Configure your browser to use `localhost:1080` as your proxy (works for both SOCKS and HTTP settings).

## License

MIT License

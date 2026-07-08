"""
BoxLite Module

Backend-based sandbox environment using BoxLite VM technology.
This provides hardware-isolated container execution for the Agent.

Architecture:
- BoxLite VMs run on the server (not in browser like WebContainers)
- All file/terminal operations happen on backend
- Frontend communicates via WebSocket for real-time updates
- Preview is served via port forwarding from the VM

Key Features:
- Full Linux environment in isolated VM
- Hardware-level security isolation
- Persistent file system via QCOW2 snapshots
- Real-time stdout/stderr streaming
- Port forwarding for web preview
"""

from .routes import boxlite_router, boxlite_ws_router
from .sandbox_manager import BoxLiteSandboxManager, get_sandbox_manager

__all__ = [
    "boxlite_router",
    "boxlite_ws_router",
    "BoxLiteSandboxManager",
    "get_sandbox_manager",
]

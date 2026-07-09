"""
BoxLite Sandbox Manager

Manages BoxLite VM instances for sandbox execution.
Provides file operations, command execution, and port forwarding.

Since BoxLite is not yet fully available, this implementation uses
a subprocess-based fallback that simulates the BoxLite API using
local Docker containers or native processes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

from .models import (
    BuildError,
    CommandResult,
    ConsoleMessage,
    DOMNode,
    ErrorSource,
    FileEntry,
    PreviewState,
    ProcessOutput,
    SandboxState,
    SandboxStatus,
    TerminalSession,
    VisualSummary,
)

logger = logging.getLogger(__name__)


# ============================================
# Constants
# ============================================

import platform
import subprocess

_IS_WINDOWS = platform.system() == "Windows"


# Find Git Bash on Windows for Unix-like command execution
def _find_git_bash() -> Optional[str]:
    """Find Git Bash executable on Windows for Unix command support."""
    if not _IS_WINDOWS:
        return None

    # Common Git Bash locations on Windows
    possible_paths = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Git\bin\bash.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\Git\usr\bin\bash.exe"),
        r"C:\Users\10598\AppData\Local\Programs\Git\bin\bash.exe",
        r"C:\Users\10598\AppData\Local\Programs\Git\usr\bin\bash.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # Try to find via 'where' command
    try:
        result = subprocess.run(
            ["where", "bash"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            paths = result.stdout.strip().split("\n")
            for p in paths:
                p = p.strip()
                if p and os.path.exists(p) and "git" in p.lower():
                    return p
    except Exception:
        pass

    return None


_GIT_BASH_PATH = _find_git_bash()
if _IS_WINDOWS and _GIT_BASH_PATH:
    logging.getLogger(__name__).info(f"[Sandbox] Found Git Bash: {_GIT_BASH_PATH}")
else:
    logging.getLogger(__name__).info(
        f"[Sandbox] Git Bash not found, using default shell"
    )

SANDBOX_BASE_DIR = os.getenv(
    "BOXLITE_SANDBOX_DIR",
    os.path.join(os.environ.get("TEMP", "C:\\Temp"), "boxlite-sandboxes")
    if _IS_WINDOWS
    else "/tmp/boxlite-sandboxes",
)
DEV_SERVER_PORT = int(os.getenv("BOXLITE_DEV_PORT", "8080"))
MAX_TERMINALS = 5
MAX_CONSOLE_MESSAGES = 200
MAX_OUTPUT_LINES = 1000
DEFAULT_TIMEOUT = 60.0  # seconds

# Default project template
DEFAULT_FILES = {
    "package.json": json.dumps(
        {
            "name": "nexting-agent-project",
            "version": "1.0.0",
            "private": True,
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            },
            "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
            "devDependencies": {
                "@vitejs/plugin-react": "^4.2.0",
                "vite": "^5.0.0",
                "tailwindcss": "^3.4.0",
                "postcss": "^8.4.32",
                "autoprefixer": "^10.4.17",
            },
        },
        indent=2,
    ),
    "vite.config.js": f"""import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({{
  plugins: [react()],
  esbuild: {{
    loader: 'jsx',
    include: /src/.*\\.js$/,  // Allow JSX in .js files (e.g. siteData.js)
  }},
  server: {{
    host: '0.0.0.0',
    port: {DEV_SERVER_PORT},
    strictPort: true,  // Never switch to another port - fail if 8080 is taken
    headers: {{
      // Allow cross-origin resources (images, fonts, etc.) to load freely
      'Cross-Origin-Resource-Policy': 'cross-origin',
      'Access-Control-Allow-Origin': '*',
    }},
    cors: true,
  }}
}})
""",
    "tailwind.config.js": """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
""",
    "postcss.config.js": """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
""",
    "index.html": """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>BoxLite Project</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
    "src/main.jsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""",
    "src/App.jsx": """import React from 'react'

function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md">
        <h1 className="text-3xl font-bold text-gray-800">
          Welcome to Nexting Agent
        </h1>
        <p className="mt-2 text-gray-600">
          Start building your application here.
        </p>
      </div>
    </div>
  )
}

export default App
""",
    "src/index.css": """@tailwind base;
@tailwind components;
@tailwind utilities;
""",
}


# ============================================
# Terminal Process Wrapper
# ============================================


@dataclass
class TerminalProcess:
    """Wrapper for a running terminal process"""

    session: TerminalSession
    process: Optional[asyncio.subprocess.Process] = None
    output_buffer: List[str] = field(default_factory=list)
    on_output: Optional[Callable[[str], None]] = None
    _read_tasks: List[asyncio.Task] = field(default_factory=list)

    def start_reading(self):
        """Start reading process output (both stdout and stderr)

        Note: This is a synchronous method that creates background tasks.
        The tasks run independently and don't need to be awaited.
        """
        tasks = []
        if self.process and self.process.stdout:
            # Check if stdout is an async stream (asyncio.subprocess.Process)
            # or a regular file object (subprocess.Popen on Windows)
            if hasattr(self.process.stdout, 'readline') and asyncio.iscoroutinefunction(self.process.stdout.readline):
                # Async stream - use async read
                tasks.append(
                    asyncio.create_task(self._read_stream(self.process.stdout, "stdout"))
                )
            else:
                # Synchronous file object (subprocess.Popen on Windows)
                tasks.append(
                    asyncio.create_task(self._read_stream_sync(self.process.stdout, "stdout"))
                )
        if self.process and self.process.stderr:
            if hasattr(self.process.stderr, 'readline') and asyncio.iscoroutinefunction(self.process.stderr.readline):
                tasks.append(
                    asyncio.create_task(self._read_stream(self.process.stderr, "stderr"))
                )
            else:
                tasks.append(
                    asyncio.create_task(self._read_stream_sync(self.process.stderr, "stderr"))
                )
        # Store tasks for later cleanup (don't wrap in gather for Python 3.9 compatibility)
        self._read_tasks = tasks

    async def _read_stream(self, stream, stream_name: str):
        """Read output from an async stream (stdout or stderr)"""
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace")
                self.output_buffer.append(decoded)

                # Trim buffer if too large
                if len(self.output_buffer) > MAX_OUTPUT_LINES:
                    self.output_buffer = self.output_buffer[-MAX_OUTPUT_LINES:]

                # Callback for real-time streaming
                if self.on_output:
                    self.on_output(decoded)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading {stream_name}: {e}")

    async def _read_stream_sync(self, stream, stream_name: str):
        """Read output from a synchronous file object (subprocess.Popen on Windows)"""
        try:
            while True:
                # Use to_thread to avoid blocking the event loop
                line = await asyncio.to_thread(stream.readline)
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line)
                self.output_buffer.append(decoded)

                # Trim buffer if too large
                if len(self.output_buffer) > MAX_OUTPUT_LINES:
                    self.output_buffer = self.output_buffer[-MAX_OUTPUT_LINES:]

                # Callback for real-time streaming
                if self.on_output:
                    self.on_output(decoded)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading sync {stream_name}: {e}")

    async def stop(self):
        """Stop the process"""
        # Cancel all reading tasks
        for task in self._read_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._read_tasks = []

        if self.process:
            try:
                self.process.terminate()
                # Handle both asyncio.subprocess.Process and subprocess.Popen
                if hasattr(self.process.wait, '__call__'):
                    # Check if wait() is a coroutine function (asyncio) or regular (Popen)
                    if asyncio.iscoroutinefunction(self.process.wait):
                        await asyncio.wait_for(self.process.wait(), timeout=5.0)
                    else:
                        # subprocess.Popen.wait() is synchronous - run in thread
                        await asyncio.to_thread(self.process.wait)
            except asyncio.TimeoutError:
                self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping process: {e}")

        self.session.is_running = False


# ============================================
# BoxLite Sandbox Manager
# ============================================


class BoxLiteSandboxManager:
    """
    Manages BoxLite sandbox instances.

    This implementation uses a process-based approach for local development.
    In production, it would use the actual BoxLite SDK.
    """

    def __init__(self, sandbox_id: Optional[str] = None):
        self.sandbox_id = sandbox_id or f"sandbox-{uuid.uuid4().hex[:12]}"
        self.work_dir = Path(SANDBOX_BASE_DIR) / self.sandbox_id
        self.state = SandboxState(sandbox_id=self.sandbox_id)
        self.terminals: Dict[str, TerminalProcess] = {}
        self.dev_server_process: Optional[TerminalProcess] = None
        self._output_callbacks: List[Callable[[ProcessOutput], None]] = []
        self._initialized = False
        self._lock = asyncio.Lock()

    # ============================================
    # Lifecycle Methods
    # ============================================

    async def reconnect(self) -> SandboxState:
        """Reconnect to existing sandbox without resetting files

        This method:
        1. Syncs state from disk (preserves user's files)
        2. Restarts dev server if not running
        3. Does NOT clear files or conversation history

        Returns:
            Current sandbox state
        """
        async with self._lock:
            logger.info(f"Reconnecting to sandbox: {self.sandbox_id}")

            # Check if work directory exists and has files
            if not self.work_dir.exists():
                logger.info(f"Sandbox directory doesn't exist, will need fresh start")
                return await self._do_initialize(reset=True)

            # Count files (excluding node_modules)
            file_count = 0
            for item in self.work_dir.iterdir():
                if item.name not in (".git", "node_modules", ".cache"):
                    file_count += 1

            if file_count == 0:
                logger.info(f"Sandbox directory is empty, will need fresh start")
                return await self._do_initialize(reset=True)

            logger.info(
                f"Found existing sandbox with {file_count} items, reconnecting..."
            )

            # Sync files from disk (don't delete!)
            await self._scan_files_from_disk()
            logger.info(f"Synced {len(self.state.files)} files from disk")

            self.state.status = SandboxStatus.READY
            self._initialized = True

            # Restart dev server if not running
            if not self.dev_server_process or not self.state.preview_url:
                logger.info("Dev server not running, starting...")
                await self.start_dev_server()
            else:
                logger.info(f"Dev server already running at {self.state.preview_url}")

            return self.state

    async def initialize(self, reset: bool = False) -> SandboxState:
        """Initialize the sandbox environment

        Args:
            reset: If True, force complete reset (kill processes, clear files, fresh start)
        """
        async with self._lock:
            if self._initialized and not reset:
                return self.state
            return await self._do_initialize(reset)

    async def _do_initialize(self, reset: bool = False) -> SandboxState:
        """Internal initialization logic (called without lock)"""
        logger.info(f"Initializing sandbox: {self.sandbox_id} (reset={reset})")
        self.state.status = SandboxStatus.CREATING

        try:
            # STEP 1: Stop all running processes first
            if self.dev_server_process:
                logger.info("Stopping existing dev server...")
                await self.dev_server_process.stop()
                self.dev_server_process = None

            # Stop all terminal processes
            for terminal in list(self.terminals.values()):
                await terminal.stop()
            self.terminals.clear()
            self.state.terminals.clear()

            # STEP 2: Kill port 8080 to ensure clean state (MUST succeed)
            logger.info(
                f"[Initialize] Killing port {DEV_SERVER_PORT} for clean start..."
            )
            port_killed = await self._kill_port(DEV_SERVER_PORT, max_attempts=10)
            if port_killed:
                logger.info(f"[Initialize] Port {DEV_SERVER_PORT} successfully freed")
            else:
                logger.warning(
                    f"[Initialize] Could not free port {DEV_SERVER_PORT}, continuing anyway..."
                )

            # STEP 3: Clear all state
            self.state.preview_url = None
            self.state.preview = PreviewState()
            self.state.console_messages.clear()
            self.state.error = None
            self._initialized = False

            # STEP 4: Reset file system
            logger.info(f"Creating fresh sandbox with default template")

            # Clean up existing files (keep node_modules for speed)
            if self.work_dir.exists():
                for item in self.work_dir.iterdir():
                    if item.name != "node_modules":
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
            else:
                self.work_dir.mkdir(parents=True, exist_ok=True)

            # Clear state files
            self.state.files.clear()

            # Write default files
            for path, content in DEFAULT_FILES.items():
                file_path = self.work_dir / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                self.state.files[f"/{path}"] = content

            self.state.status = SandboxStatus.READY
            self._initialized = True

            # Create default terminal
            await self._create_default_terminal()

            logger.info(f"Sandbox reset complete: {self.sandbox_id}")

            # Auto-start dev server
            logger.info(f"Auto-starting dev server for sandbox: {self.sandbox_id}")
            await self.start_dev_server()

        except Exception as e:
            self.state.status = SandboxStatus.ERROR
            self.state.error = str(e)
            logger.error(f"Failed to initialize sandbox: {e}")

        return self.state

    async def _scan_files_from_disk(self):
        """Scan all files from disk to state.files (disk is SSOT)"""
        self.state.files.clear()

        def scan_dir(dir_path: Path, prefix: str = ""):
            try:
                for item in dir_path.iterdir():
                    # Skip hidden files and node_modules
                    if item.name.startswith(".") or item.name == "node_modules":
                        continue

                    rel_path = f"{prefix}/{item.name}"
                    if item.is_file():
                        try:
                            # Only read text files
                            content = item.read_text(encoding="utf-8")
                            self.state.files[rel_path] = content
                        except UnicodeDecodeError:
                            # Skip binary files
                            pass
                        except Exception as e:
                            logger.warning(f"Failed to read file {rel_path}: {e}")
                    elif item.is_dir():
                        scan_dir(item, rel_path)
            except Exception as e:
                logger.error(f"Error scanning directory {dir_path}: {e}")

        scan_dir(self.work_dir)
        logger.info(f"Scanned {len(self.state.files)} files from disk")

    async def cleanup(self):
        """Cleanup sandbox resources"""
        logger.info(f"Cleaning up sandbox: {self.sandbox_id}")

        # Stop all terminal processes
        for terminal in list(self.terminals.values()):
            await terminal.stop()
        self.terminals.clear()

        # Stop dev server
        if self.dev_server_process:
            await self.dev_server_process.stop()
            self.dev_server_process = None

        # Remove work directory
        try:
            if self.work_dir.exists():
                shutil.rmtree(self.work_dir)
        except Exception as e:
            logger.warning(f"Failed to remove sandbox directory: {e}")

        self.state.status = SandboxStatus.STOPPED

    async def _create_default_terminal(self):
        """Create default terminal for the sandbox"""
        try:
            # Import here to avoid circular dependency with create_terminal lock
            session = await self.create_terminal("main")
            logger.info(f"Default terminal created: {session.id}")
        except Exception as e:
            logger.warning(f"Failed to create default terminal: {e}")

    # ============================================
    # File Operations
    # ============================================

    async def write_file(self, path: str, content: str) -> bool:
        """Write content to a file"""
        import threading

        try:
            # Normalize path
            normalized = path.lstrip("/")
            file_path = self.work_dir / normalized

            # DEBUG: Log write operation with thread info
            thread_id = threading.current_thread().ident
            content_preview = content[:100].replace("\n", " ") if content else "(empty)"
            logger.info(
                f"[write_file] Thread {thread_id}: Writing {path} ({len(content)} chars)"
            )
            logger.debug(f"[write_file] Content preview: {content_preview}...")

            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path.write_text(content, encoding="utf-8")

            # Update state
            state_path = f"/{normalized}"
            self.state.files[state_path] = content
            self.state.updated_at = datetime.now()

            logger.info(f"[write_file] ✓ Wrote {path} ({len(content)} chars)")
            return True

        except Exception as e:
            logger.error(f"Failed to write file {path}: {e}")
            return False

    async def read_file(self, path: str) -> Optional[str]:
        """Read file content"""
        try:
            normalized = path.lstrip("/")
            file_path = self.work_dir / normalized

            if file_path.exists() and file_path.is_file():
                content = file_path.read_text(encoding="utf-8")
                # Update cache
                self.state.files[f"/{normalized}"] = content
                return content

            return None

        except Exception as e:
            logger.error(f"Failed to read file {path}: {e}")
            return None

    async def delete_file(self, path: str) -> bool:
        """Delete a file"""
        try:
            normalized = path.lstrip("/")
            file_path = self.work_dir / normalized

            if file_path.exists():
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

            # Update state
            state_path = f"/{normalized}"
            self.state.files.pop(state_path, None)
            self.state.updated_at = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")
            return False

    async def list_files(self, path: str = "/") -> List[FileEntry]:
        """List files in a directory"""
        try:
            normalized = path.lstrip("/") or "."
            dir_path = self.work_dir / normalized

            if not dir_path.exists() or not dir_path.is_dir():
                return []

            entries = []
            for item in dir_path.iterdir():
                # Skip hidden files and node_modules
                if item.name.startswith(".") or item.name == "node_modules":
                    continue

                rel_path = "/" + str(item.relative_to(self.work_dir))
                entry = FileEntry(
                    name=item.name,
                    path=rel_path,
                    type="directory" if item.is_dir() else "file",
                    size=item.stat().st_size if item.is_file() else None,
                    modified_at=datetime.fromtimestamp(item.stat().st_mtime),
                )
                entries.append(entry)

            return sorted(
                entries, key=lambda e: (e.type != "directory", e.name.lower())
            )

        except Exception as e:
            logger.error(f"Failed to list files in {path}: {e}")
            return []

    async def create_directory(self, path: str) -> bool:
        """Create a directory"""
        try:
            normalized = path.lstrip("/")
            dir_path = self.work_dir / normalized
            dir_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return False

    async def rename_file(self, old_path: str, new_path: str) -> bool:
        """Rename/move a file"""
        try:
            old_normalized = old_path.lstrip("/")
            new_normalized = new_path.lstrip("/")

            old_file = self.work_dir / old_normalized
            new_file = self.work_dir / new_normalized

            if not old_file.exists():
                return False

            # Create parent directory if needed
            new_file.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            old_file.rename(new_file)

            # Update state
            old_state = f"/{old_normalized}"
            new_state = f"/{new_normalized}"
            if old_state in self.state.files:
                self.state.files[new_state] = self.state.files.pop(old_state)

            return True

        except Exception as e:
            logger.error(f"Failed to rename {old_path} to {new_path}: {e}")
            return False

    async def sync_files_to_state(self):
        """Sync file system to state"""
        self.state.files.clear()

        def scan_dir(dir_path: Path, prefix: str = ""):
            for item in dir_path.iterdir():
                if item.name.startswith(".") or item.name == "node_modules":
                    continue

                rel_path = f"{prefix}/{item.name}"
                if item.is_file():
                    try:
                        content = item.read_text(encoding="utf-8")
                        self.state.files[rel_path] = content
                    except Exception:
                        pass  # Skip binary files
                elif item.is_dir():
                    scan_dir(item, rel_path)

        scan_dir(self.work_dir)

    # ============================================
    # Command Execution
    # ============================================

    async def run_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        background: bool = False,
    ) -> CommandResult:
        """Execute a shell command"""
        args = args or []
        full_command = [command] + args
        cmd_str = " ".join(full_command)

        logger.info(f"Running command: {cmd_str}")

        try:
            # On Windows, wrap command in Git Bash for Unix command support
            if _IS_WINDOWS and _GIT_BASH_PATH:
                # Prefix command with cd to sandbox work_dir to ensure Git Bash
                # resolves /src/ etc. relative to the sandbox, not Git install dir
                # (--login resets cwd, so we need explicit cd)
                prefixed_cmd = f"cd {self.work_dir} && {cmd_str}"
                # Use Git Bash with -c flag to run the command
                # --noprofile skips slow .bash_profile loading for faster startup
                bash_cmd = [_GIT_BASH_PATH, "--login", "--noprofile", "-c", prefixed_cmd]
                logger.info(
                    f"[RunCommand] Using Git Bash: {' '.join(bash_cmd[:3])}...{prefixed_cmd[:80]}"
                )
            else:
                bash_cmd = cmd_str

            if background:
                # Start background process
                terminal_id = f"term-{uuid.uuid4().hex[:8]}"
                session = TerminalSession(
                    id=terminal_id,
                    name=f"Background: {command}",
                    is_running=True,
                    command=cmd_str,
                )

                if _IS_WINDOWS and _GIT_BASH_PATH:
                    # Use subprocess.Popen via to_thread for Windows compatibility
                    bg_prefixed_cmd = f"cd {self.work_dir} && {cmd_str}"
                    def _create_bg_process():
                        return subprocess.Popen(
                            [_GIT_BASH_PATH, "--login", "--noprofile", "-c", bg_prefixed_cmd],
                            cwd=str(self.work_dir),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            env={**os.environ, "NODE_ENV": "development"},
                        )
                    process = await asyncio.to_thread(_create_bg_process)
                else:
                    process = await asyncio.create_subprocess_shell(
                        cmd_str,
                        cwd=str(self.work_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                        env={**os.environ, "NODE_ENV": "development"},
                    )

                term_process = TerminalProcess(
                    session=session,
                    process=process,
                    on_output=lambda data: self._emit_output(terminal_id, data),
                )
                term_process.start_reading()
                self.terminals[terminal_id] = term_process
                self.state.terminals.append(session)

                return CommandResult(
                    success=True,
                    exit_code=0,
                    stdout=f"Started background process: {cmd_str}",
                    stderr="",
                    duration_ms=0,
                )

            # Foreground command - use subprocess.run via to_thread for Windows compatibility
            start = datetime.now()
            if _IS_WINDOWS and _GIT_BASH_PATH:
                # Run via synchronous subprocess (avoids asyncio subprocess issues on Windows)
                result = await asyncio.to_thread(
                    subprocess.run,
                    [_GIT_BASH_PATH, "--login", "--noprofile", "-c", cmd_str],
                    cwd=str(self.work_dir),
                    capture_output=True,
                    timeout=timeout,
                    env={**os.environ, "NODE_ENV": "development"},
                )
                duration = (datetime.now() - start).total_seconds() * 1000
                return CommandResult(
                    success=result.returncode == 0,
                    exit_code=result.returncode or 0,
                    stdout=result.stdout.decode("utf-8", errors="replace"),
                    stderr=result.stderr.decode("utf-8", errors="replace"),
                    duration_ms=int(duration),
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    cmd_str,
                    cwd=str(self.work_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "NODE_ENV": "development"},
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    return CommandResult(
                        success=False,
                        exit_code=-1,
                        stdout="",
                        stderr=f"Command timed out after {timeout}s",
                        duration_ms=int(timeout * 1000),
                    )

                duration = (datetime.now() - start).total_seconds() * 1000

                return CommandResult(
                    success=process.returncode == 0,
                    exit_code=process.returncode or 0,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=stderr.decode("utf-8", errors="replace"),
                    duration_ms=int(duration),
                )

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return CommandResult(
                success=False, exit_code=-1, stdout="", stderr=str(e), duration_ms=0
            )

    async def install_dependencies(
        self, packages: Optional[List[str]] = None, dev: bool = False
    ) -> CommandResult:
        """Install npm packages"""
        if packages:
            pkg_str = " ".join(packages)
            if dev:
                return await self.run_command(
                    "npm", ["install", "--save-dev"] + packages, timeout=120
                )
            return await self.run_command("npm", ["install"] + packages, timeout=120)
        return await self.run_command("npm", ["install"], timeout=120)

    async def _kill_port(self, port: int, max_attempts: int = 10) -> bool:
        """Kill any process using the specified port (cross-platform)"""
        logger.info(
            f"[KillPort] Starting to kill port {port}, max_attempts={max_attempts}"
        )

        for attempt in range(max_attempts):
            try:
                if _IS_WINDOWS:
                    # Windows: use synchronous subprocess.run (avoids asyncio subprocess issues)
                    find_result = await asyncio.to_thread(
                        subprocess.run,
                        ["netstat", "-ano"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )

                    if find_result.returncode != 0:
                        logger.warning(
                            f"[KillPort] netstat returned code {find_result.returncode}, stderr: {find_result.stderr[:200]}"
                        )

                    pids = set()
                    for line in find_result.stdout.splitlines():
                        line = line.strip()
                        # Match lines containing the port number (e.g., ":8080" or ":8080 ")
                        if f":{port}" in line:
                            parts = line.split()
                            if parts:
                                try:
                                    # Last column is PID
                                    pid = parts[-1]
                                    # Validate it's a number
                                    if pid.isdigit() and int(pid) > 0:
                                        pids.add(pid)
                                except (IndexError, ValueError):
                                    pass
                    pids = list(pids)
                else:
                    find_result = await asyncio.to_thread(
                        subprocess.run,
                        ["lsof", f"-ti:{port}"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    pids = [
                        p.strip()
                        for p in find_result.stdout.strip().split("\n")
                        if p.strip()
                    ]

                logger.info(
                    f"[KillPort] Attempt {attempt + 1}: Found PIDs on port {port}: {pids if pids else 'none'}"
                )

                if not pids:
                    logger.info(
                        f"[KillPort] Port {port} is FREE (attempt {attempt + 1})"
                    )
                    return True

                for pid in pids:
                    try:
                        if _IS_WINDOWS:
                            kill_result = await asyncio.to_thread(
                                subprocess.run,
                                ["taskkill", "/F", "/PID", pid],
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                        else:
                            kill_result = await asyncio.to_thread(
                                subprocess.run,
                                ["kill", "-9", pid],
                                capture_output=True,
                                text=True,
                                timeout=10,
                            )
                        if kill_result.returncode == 0:
                            logger.info(f"[KillPort] Successfully killed PID {pid}")
                        else:
                            logger.warning(
                                f"[KillPort] Kill returned code {kill_result.returncode} for PID {pid}: {kill_result.stderr[:100]}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[KillPort] Failed to kill PID {pid}: {type(e).__name__}: {e}"
                        )

                await asyncio.sleep(1.5)

            except Exception as e:
                logger.error(
                    f"[KillPort] Error on attempt {attempt + 1}: {type(e).__name__}: {e}"
                )
                await asyncio.sleep(1.0)

        logger.error(f"[KillPort] FAILED: Could not free port {port}")
        return False

    _dev_server_starting: bool = False  # Prevent concurrent starts

    async def start_dev_server(self) -> CommandResult:
        """Start the development server on port 8080

        Steps:
        1. Kill any process on port 8080 (MUST succeed)
        2. Run npm install (wait for completion)
        3. Run npm run dev (background)
        """
        # Prevent concurrent starts
        if self._dev_server_starting:
            logger.warning("[DevServer] Already starting, skipping duplicate request")
            return CommandResult(
                success=True,
                exit_code=0,
                stdout="Dev server is already starting...",
                stderr="",
                duration_ms=0,
            )

        if self.dev_server_process:
            logger.info("[DevServer] Already running, skipping")
            return CommandResult(
                success=True,
                exit_code=0,
                stdout=f"Dev server already running on port {DEV_SERVER_PORT}",
                stderr="",
                duration_ms=0,
            )

        self._dev_server_starting = True
        logger.info("[DevServer] ========== STARTING DEV SERVER ==========")

        try:
            # STEP 0: Stop any existing dev server terminal and clear output
            if self.dev_server_process:
                logger.info("[DevServer] Stopping existing dev server terminal...")
                await self.dev_server_process.stop()
                self.dev_server_process = None

            # Clear all terminals except the default one to remove old output
            terminals_to_remove = [
                tid
                for tid, term in self.terminals.items()
                if "npm run dev" in (term.session.command or "")
                or "vite" in (term.session.command or "").lower()
            ]
            for tid in terminals_to_remove:
                logger.info(f"[DevServer] Removing old terminal: {tid}")
                await self.terminals[tid].stop()
                del self.terminals[tid]
                self.state.terminals = [t for t in self.state.terminals if t.id != tid]

            # STEP 1: Kill port 8080 - MUST succeed before continuing
            logger.info(f"[DevServer] Step 1: Killing port {DEV_SERVER_PORT}...")
            port_killed = await self._kill_port(DEV_SERVER_PORT, max_attempts=10)
            if not port_killed:
                logger.error(f"[DevServer] Failed to free port {DEV_SERVER_PORT}!")
                return CommandResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Failed to free port {DEV_SERVER_PORT}. Please manually kill the process.",
                    duration_ms=0,
                )
            logger.info(f"[DevServer] Port {DEV_SERVER_PORT} confirmed free")

            # STEP 2: Install dependencies (wait for completion)
            logger.info("[DevServer] Step 2: Running npm install...")
            install_result = await self.install_dependencies()
            if not install_result.success:
                logger.error(f"[DevServer] npm install failed: {install_result.stderr}")
                return install_result
            logger.info("[DevServer] npm install completed")

            # STEP 3: Double-check port is still free before starting Vite
            logger.info(f"[DevServer] Step 3: Final port check before Vite...")
            final_check = await self._kill_port(DEV_SERVER_PORT, max_attempts=5)
            if not final_check:
                logger.error(
                    f"[DevServer] Port {DEV_SERVER_PORT} got occupied during npm install!"
                )
                return CommandResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Port {DEV_SERVER_PORT} got occupied. Please try again.",
                    duration_ms=0,
                )

            # Wait extra time for port to be fully released (TIME_WAIT state)
            logger.info(
                f"[DevServer] Waiting 2s for port {DEV_SERVER_PORT} to be fully released..."
            )
            await asyncio.sleep(2)

            # STEP 4: Start dev server in background
            logger.info("[DevServer] Step 4: Running npm run dev...")
            result = await self.run_command("npm", ["run", "dev"], background=True)

            if result.success:
                # Find the terminal process for dev server
                for tid, term in self.terminals.items():
                    if "npm run dev" in (term.session.command or ""):
                        self.dev_server_process = term
                        break

                # Wait for server to be ready
                await asyncio.sleep(3)

                # Set preview URL
                self.state.preview_url = f"http://localhost:{DEV_SERVER_PORT}"
                self.state.preview = PreviewState(url=self.state.preview_url)
                self.state.status = SandboxStatus.RUNNING
                logger.info(
                    f"[DevServer] ========== STARTED ON PORT {DEV_SERVER_PORT} =========="
                )

            return result

        finally:
            self._dev_server_starting = False

    async def stop_dev_server(self) -> bool:
        """Stop the development server"""
        if self.dev_server_process:
            await self.dev_server_process.stop()
            self.dev_server_process = None
            self.state.preview_url = None
            self.state.preview = PreviewState()
            self.state.status = SandboxStatus.READY
            return True
        return False

    # ============================================
    # Terminal Management
    # ============================================

    async def create_terminal(self, name: Optional[str] = None) -> TerminalSession:
        """Create a new terminal session"""
        if len(self.terminals) >= MAX_TERMINALS:
            raise ValueError(f"Maximum terminals ({MAX_TERMINALS}) reached")

        terminal_id = f"term-{uuid.uuid4().hex[:8]}"
        session = TerminalSession(
            id=terminal_id,
            name=name or f"Terminal {len(self.terminals) + 1}",
            is_running=False,
        )

        # Create terminal process (shell)
        # Use Git Bash on Windows for Unix command support, bash on Linux/Mac
        if _IS_WINDOWS and _GIT_BASH_PATH:
            shell_cmd = _GIT_BASH_PATH
            # Git Bash needs --login to initialize the environment
            # --noprofile skips slow .bash_profile loading for faster startup
            shell_args = ["--login", "--noprofile"]
        else:
            shell_cmd = "bash" if not _IS_WINDOWS else "cmd.exe"
            shell_args = []

        logger.info(f"[Terminal] Starting shell: {shell_cmd} {shell_args}")

        # Use subprocess.Popen via to_thread for Windows compatibility
        # (avoids asyncio.create_subprocess_exec issues on Windows)
        if _IS_WINDOWS:
            def _create_process():
                return subprocess.Popen(
                    [shell_cmd] + shell_args,
                    cwd=str(self.work_dir),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                )

            proc = await asyncio.to_thread(_create_process)

            # Wrap in asyncio process-compatible object
            class _PopenWrapper:
                """Minimal wrapper to match asyncio.subprocess.Process interface"""
                def __init__(self, proc):
                    self._proc = proc
                    self.stdin = proc.stdin
                    self.stdout = proc.stdout
                    self.stderr = proc.stderr
                    self.returncode = proc.returncode

                async def communicate(self):
                    # Read stdout in a thread to avoid blocking
                    def _read():
                        return self._proc.stdout.read() if self._proc.stdout else b''
                    stdout_data = await asyncio.to_thread(_read)
                    return stdout_data, b''

                def terminate(self):
                    self._proc.terminate()

                def kill(self):
                    self._proc.kill()

                async def wait(self):
                    return await asyncio.to_thread(self._proc.wait)

            process = _PopenWrapper(proc)
        else:
            process = await asyncio.create_subprocess_shell(
                shell_cmd,
                cwd=str(self.work_dir),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

        term_process = TerminalProcess(
            session=session,
            process=process,
            on_output=lambda data: self._emit_output(terminal_id, data),
        )
        term_process.start_reading()

        self.terminals[terminal_id] = term_process
        self.state.terminals.append(session)
        self.state.active_terminal_id = terminal_id

        return session

    async def send_terminal_input(self, terminal_id: str, input_text: str) -> bool:
        """Send input to a terminal"""
        term = self.terminals.get(terminal_id)
        if not term or not term.process or not term.process.stdin:
            return False

        try:
            data = input_text.encode()
            if hasattr(term.process.stdin, 'drain'):
                # Async stream (asyncio.subprocess.Process)
                term.process.stdin.write(data)
                await term.process.stdin.drain()
            else:
                # Synchronous BufferedWriter (subprocess.Popen on Windows)
                await asyncio.to_thread(term.process.stdin.write, data)
                await asyncio.to_thread(term.process.stdin.flush)
            return True
        except Exception as e:
            logger.error(f"Failed to send input to terminal: {e}")
            return False

    async def kill_terminal(self, terminal_id: str) -> bool:
        """Kill a terminal session"""
        term = self.terminals.get(terminal_id)
        if not term:
            return False

        await term.stop()
        del self.terminals[terminal_id]

        # Remove from state
        self.state.terminals = [t for t in self.state.terminals if t.id != terminal_id]

        return True

    def get_terminal_output(self, terminal_id: str, lines: int = 50) -> List[str]:
        """Get recent terminal output"""
        term = self.terminals.get(terminal_id)
        if not term:
            return []

        return term.output_buffer[-lines:]

    # ============================================
    # Preview / Build Error Detection
    # ============================================

    async def get_build_errors(
        self, source: Literal["all", "terminal", "browser", "static"] = "all"
    ) -> List[BuildError]:
        """
        Unified error detection from multiple sources.

        Args:
            source: Which detection layer(s) to use
                - "all": All three layers (terminal + browser + static)
                - "terminal": Only parse terminal output
                - "browser": Only use Playwright browser detection
                - "static": Only static code analysis

        Returns:
            List of BuildError objects, deduplicated and sorted by priority
        """
        from .error_detector import ErrorDetector

        detector = ErrorDetector(self)
        return await detector.detect(source=source)

    async def quick_error_check(self) -> List[BuildError]:
        """
        Quick error check for auto-attach to file operations.
        Only runs terminal + static analysis (no Playwright - too slow).

        Returns:
            List of BuildError objects
        """
        from .error_detector import ErrorDetector

        detector = ErrorDetector(self)
        return await detector.quick_check()

    async def get_visual_summary(self) -> VisualSummary:
        """
        Get visual summary of preview page using Playwright.

        Takes a screenshot of the preview URL (localhost:8080) and extracts
        page information like title and visible text.
        """
        preview_url = self.state.preview_url
        screenshot_base64 = None
        page_title = "Nexting Agent Project"
        visible_text = None
        error = None
        visible_element_count = 0

        if not preview_url:
            return VisualSummary(
                has_content=False,
                visible_element_count=0,
                text_preview="",
                viewport={"width": 1280, "height": 720},
                body_size={"width": 1280, "height": 720},
                preview_url=None,
                page_title=page_title,
                visible_text=None,
                screenshot_base64=None,
                error="Preview server not started",
            )

        try:
            import base64

            # Try async Playwright first, fall back to sync on Windows Python 3.13
            screenshot_bytes = None
            try:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        viewport={"width": 1024, "height": 768}
                    )
                    page = await context.new_page()

                    try:
                        await page.goto(
                            preview_url, timeout=15000, wait_until="networkidle"
                        )
                        page_title = await page.title() or "Nexting Agent Project"
                        visible_text = await page.evaluate("""() => {
                            return document.body?.innerText?.substring(0, 1000) || '';
                        }""")
                        visible_element_count = await page.evaluate("""() => {
                            return document.querySelectorAll('*').length;
                        }""")
                        screenshot_bytes = await page.screenshot(type="png", full_page=False)
                    except Exception as e:
                        logger.warning(f"[Sandbox] Async screenshot inner error: {e}")
                    finally:
                        await browser.close()
            except (NotImplementedError, Exception) as async_err:
                logger.warning(f"[Sandbox] Async Playwright failed ({async_err}), trying sync fallback...")
                try:
                    from playwright.sync_api import sync_playwright
                    import concurrent.futures

                    def _sync_screenshot():
                        with sync_playwright() as p:
                            browser = p.chromium.launch(headless=True)
                            ctx = browser.new_context(viewport={"width": 1024, "height": 768})
                            pg = ctx.new_page()
                            try:
                                pg.goto(preview_url, timeout=15000, wait_until="networkidle")
                                title = pg.title() or "Nexting Agent Project"
                                text = pg.evaluate("""() => {
                                    return document.body?.innerText?.substring(0, 1000) || '';
                                }""")
                                count = pg.evaluate("""() => {
                                    return document.querySelectorAll('*').length;
                                }""")
                                shot = pg.screenshot(type="png", full_page=False)
                                return title, text, count, shot, None
                            except Exception as e:
                                return None, None, 0, None, str(e)
                            finally:
                                browser.close()

                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = await loop.run_in_executor(pool, _sync_screenshot)
                    page_title_result, text_result, count_result, shot, sync_err = result
                    if page_title_result:
                        page_title = page_title_result
                    if text_result:
                        visible_text = text_result
                    if count_result:
                        visible_element_count = count_result
                    if shot:
                        screenshot_bytes = shot
                    elif sync_err:
                        error = f"Sync screenshot failed: {sync_err}"
                except Exception as sync_err:
                    logger.error(f"[Sandbox] Sync Playwright fallback also failed: {sync_err}")
                    error = f"Screenshot failed (async and sync both failed): {sync_err}"

            # Compress screenshot if we got one
            if screenshot_bytes:
                try:
                    import io

                    from PIL import Image

                    img = Image.open(io.BytesIO(screenshot_bytes))
                    original_size = len(screenshot_bytes)

                    max_width = 600
                    max_height = 800

                    width_ratio = (
                        max_width / img.width if img.width > max_width else 1
                    )
                    height_ratio = (
                        max_height / img.height if img.height > max_height else 1
                    )
                    ratio = min(width_ratio, height_ratio)

                    if ratio < 1:
                        new_size = (int(img.width * ratio), int(img.height * ratio))
                        img = img.resize(new_size, Image.LANCZOS)

                    quality = 50
                    max_bytes = 50000

                    while quality >= 20:
                        buffer = io.BytesIO()
                        img.convert("RGB").save(
                            buffer, format="JPEG", quality=quality, optimize=True
                        )
                        screenshot_bytes = buffer.getvalue()

                        if len(screenshot_bytes) <= max_bytes:
                            break
                        quality -= 10

                    logger.info(
                        f"[Sandbox] Screenshot compressed: {original_size} -> {len(screenshot_bytes)} bytes (quality={quality}, size={img.width}x{img.height})"
                    )
                except ImportError:
                    logger.warning("[Sandbox] Pillow not available, using raw PNG")

                screenshot_base64 = base64.b64encode(screenshot_bytes).decode(
                    "utf-8"
                )

                logger.info(
                    f"[Sandbox] Screenshot captured: {len(screenshot_bytes)} bytes"
                )

        except ImportError:
            error = "Playwright not installed. Run: pip install playwright && playwright install chromium"
            logger.warning("[Sandbox] Playwright not available for screenshots")
        except Exception as e:
            error = f"Screenshot failed: {str(e)}"
            logger.error(f"[Sandbox] Screenshot error: {e}")

        return VisualSummary(
            has_content=screenshot_base64 is not None,
            visible_element_count=visible_element_count,
            text_preview=visible_text[:200] if visible_text else "",
            viewport={"width": 1280, "height": 720},
            body_size={"width": 1280, "height": 720},
            preview_url=preview_url,
            page_title=page_title,
            visible_text=visible_text,
            screenshot_base64=screenshot_base64,
            error=error,
        )

    # ============================================
    # Callbacks and Events
    # ============================================

    def on_output(self, callback: Callable[[ProcessOutput], None]):
        """Register output callback, returns callback for later removal"""
        self._output_callbacks.append(callback)
        return callback

    def remove_output_callback(self, callback: Callable[[ProcessOutput], None]):
        """Remove a registered output callback"""
        if callback in self._output_callbacks:
            self._output_callbacks.remove(callback)

    def clear_output_callbacks(self):
        """Clear all output callbacks"""
        self._output_callbacks.clear()

    def _emit_output(self, terminal_id: str, data: str):
        """Emit output to all callbacks"""
        output = ProcessOutput(terminal_id=terminal_id, data=data, stream="stdout")

        for callback in self._output_callbacks:
            try:
                callback(output)
            except Exception as e:
                logger.error(f"Output callback error: {e}")

    # ============================================
    # State Access
    # ============================================

    def get_state(self) -> SandboxState:
        """Get current sandbox state"""
        self.state.updated_at = datetime.now()
        return self.state

    def get_state_dict(self) -> Dict[str, Any]:
        """Get state as dictionary

        SSOT: Always sync files from disk before returning state.
        This ensures frontend always receives the latest disk content.
        """
        # Sync files from disk to ensure SSOT
        self._sync_files_from_disk()
        return self.state.model_dump(mode="json")

    def _sync_files_from_disk(self):
        """Sync files from disk to state (synchronous version for get_state_dict)"""
        if not self.work_dir.exists():
            return

        self.state.files.clear()

        def scan_dir(dir_path: Path, prefix: str = ""):
            try:
                for item in dir_path.iterdir():
                    # Skip hidden files and node_modules
                    if item.name.startswith(".") or item.name == "node_modules":
                        continue

                    rel_path = f"{prefix}/{item.name}"
                    if item.is_file():
                        try:
                            content = item.read_text(encoding="utf-8")
                            self.state.files[rel_path] = content
                        except UnicodeDecodeError:
                            pass  # Skip binary files
                        except Exception:
                            pass
                    elif item.is_dir():
                        scan_dir(item, rel_path)
            except Exception:
                pass

        scan_dir(self.work_dir)


# ============================================
# Global Sandbox Manager
# ============================================

_sandbox_managers: Dict[str, BoxLiteSandboxManager] = {}

# Singleton mode: reuse the same sandbox instead of creating new ones
# This prevents port conflicts when using fixed port (8080)
SINGLETON_MODE = os.getenv("BOXLITE_SINGLETON_MODE", "true").lower() in (
    "true",
    "1",
    "yes",
)
_singleton_sandbox_id: Optional[str] = None


def get_sandbox_manager(sandbox_id: Optional[str] = None) -> BoxLiteSandboxManager:
    """Get or create a sandbox manager

    In singleton mode (default), always returns the same sandbox instance.
    This prevents port conflicts when using a fixed dev server port.

    If a sandbox_id is provided but not in memory, this will attempt
    to restore files from disk (handles backend restarts gracefully).
    """
    global _singleton_sandbox_id

    # Singleton mode: reuse existing sandbox
    if SINGLETON_MODE:
        if _singleton_sandbox_id and _singleton_sandbox_id in _sandbox_managers:
            logger.info(f"Reusing existing sandbox: {_singleton_sandbox_id}")
            return _sandbox_managers[_singleton_sandbox_id]

        # Check if there's files on disk for a previous sandbox
        if sandbox_id:
            sandbox_dir = Path(SANDBOX_BASE_DIR) / sandbox_id
            if sandbox_dir.exists():
                file_count = sum(1 for item in sandbox_dir.iterdir() if item.name not in ('.git', 'node_modules', '.cache'))
                if file_count > 0:
                    logger.info(f"Restoring singleton sandbox from disk: {sandbox_id} ({file_count} items)")
                    manager = BoxLiteSandboxManager(sandbox_id)
                    _sandbox_managers[manager.sandbox_id] = manager
                    _singleton_sandbox_id = manager.sandbox_id
                    return manager

        # Create new singleton sandbox
        manager = BoxLiteSandboxManager(sandbox_id)
        _sandbox_managers[manager.sandbox_id] = manager
        _singleton_sandbox_id = manager.sandbox_id
        logger.info(f"Created singleton sandbox: {manager.sandbox_id}")
        return manager

    # Non-singleton mode: allow multiple sandboxes
    if sandbox_id and sandbox_id in _sandbox_managers:
        return _sandbox_managers[sandbox_id]

    # Check if there's files on disk for this sandbox_id
    if sandbox_id:
        sandbox_dir = Path(SANDBOX_BASE_DIR) / sandbox_id
        if sandbox_dir.exists():
            file_count = sum(1 for item in sandbox_dir.iterdir() if item.name not in ('.git', 'node_modules', '.cache'))
            if file_count > 0:
                logger.info(f"Restoring sandbox from disk: {sandbox_id} ({file_count} items)")
                manager = BoxLiteSandboxManager(sandbox_id)
                _sandbox_managers[manager.sandbox_id] = manager
                return manager

    manager = BoxLiteSandboxManager(sandbox_id)
    _sandbox_managers[manager.sandbox_id] = manager
    return manager


async def cleanup_sandbox(sandbox_id: str):
    """Cleanup a sandbox"""
    if sandbox_id in _sandbox_managers:
        manager = _sandbox_managers.pop(sandbox_id)
        await manager.cleanup()


async def cleanup_all_sandboxes():
    """Cleanup all sandboxes"""
    for manager in list(_sandbox_managers.values()):
        await manager.cleanup()
    _sandbox_managers.clear()

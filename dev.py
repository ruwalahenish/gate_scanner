#!/usr/bin/env python3
"""
dev.py  ─  One command to start the entire GATE Platform.

    python dev.py              # start everything
    python dev.py --no-worker  # skip Celery (lighter, manual scans still work)

Services started:
  • Redis        via Docker (skipped when Redis already on :6379)
  • FastAPI API  uvicorn --reload on :8000
  • Celery       worker with 2 concurrency slots
  • Celery Beat  periodic task scheduler (paper trade monitoring + price broadcast)
  • Next.js      npm run dev on :3000

Prerequisites:
  • Python 3.11+  (pip install -r backend/requirements.txt already run)
  • Node.js + npm (npm install in apps/web already run — auto-triggered if missing)
  • Docker        (only needed if Redis is not already running locally)
  • .env file at project root (copy .env.example and fill in DATABASE_URL)
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# ── Project paths ──────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
WEB     = ROOT / "apps" / "web"

IS_WIN = platform.system() == "Windows"

# ── ANSI colours ──────────────────────────────────────────────────────────
# Enable VT processing on Windows 10+ so ANSI codes render in cmd/PowerShell
if IS_WIN:
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

_C = {
    "redis":  "\033[35m",   # magenta
    "api":    "\033[36m",   # cyan
    "worker": "\033[33m",   # yellow
    "beat":   "\033[34m",   # blue
    "web":    "\033[32m",   # green
    "info":   "\033[90m",   # grey
    "ok":     "\033[32;1m", # bold green
    "err":    "\033[31;1m", # bold red
    "dim":    "\033[2m",
    "reset":  "\033[0m",
}

def c(key: str) -> str:
    return _C.get(key, "")


def banner(msg: str, colour: str = "ok") -> None:
    print(f"\n{c(colour)}{msg}{c('reset')}\n", flush=True)


def log(name: str, line: str) -> None:
    print(f"{c(name)}[{name:<6}]{c('reset')} {line}", flush=True)


# ── Process registry ──────────────────────────────────────────────────────
_procs: list[subprocess.Popen] = []
_redis_ours = False          # True when we launched the Docker container
_shutdown_called = False

# ── Subprocess helpers ────────────────────────────────────────────────────

def _npm_cmd() -> str:
    return "npm.cmd" if IS_WIN else "npm"


def _stream(proc: subprocess.Popen, name: str) -> None:
    """Forward stdout+stderr of a process to the console with a prefix."""
    assert proc.stdout
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip()
        if line:
            log(name, line)


def _spawn(name: str, cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.Popen:
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WIN else 0
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=flags,
    )
    _procs.append(proc)
    threading.Thread(target=_stream, args=(proc, name), daemon=True).start()
    return proc


# ── Redis ──────────────────────────────────────────────────────────────────

def _redis_alive() -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", 6379))
            return True
        except OSError:
            return False


def ensure_redis() -> None:
    global _redis_ours

    if _redis_alive():
        log("info", "Redis already running on 127.0.0.1:6379 — reusing")
        return

    if not shutil.which("docker"):
        print(
            f"{c('err')}✗  Redis is not running and Docker was not found.\n"
            f"   Install Docker Desktop or start Redis manually, then re-run.{c('reset')}"
        )
        sys.exit(1)

    log("info", "Starting Redis via Docker…")
    # Remove any stale container silently
    subprocess.run(["docker", "rm", "-f", "gate-redis"], capture_output=True)
    result = subprocess.run([
        "docker", "run", "-d",
        "--name", "gate-redis",
        "-p", "6379:6379",
        "redis:7-alpine",
        "redis-server",
        "--maxmemory", "128mb",
        "--maxmemory-policy", "allkeys-lru",
    ], capture_output=True)

    if result.returncode != 0:
        print(
            f"{c('err')}✗  Could not start Redis container:\n"
            f"   {result.stderr.decode().strip()}{c('reset')}"
        )
        sys.exit(1)

    _redis_ours = True

    # Wait up to 8 s for Redis to be ready
    for _ in range(16):
        if _redis_alive():
            log("redis", f"{c('ok')}Ready on :6379{c('reset')}")
            return
        time.sleep(0.5)

    print(f"{c('err')}✗  Redis container started but port is not open after 8 s.{c('reset')}")
    sys.exit(1)


# ── Dependency checks ──────────────────────────────────────────────────────

def ensure_npm_deps() -> None:
    """Run 'npm install' if node_modules is missing or outdated."""
    nm = WEB / "node_modules"
    pkg = WEB / "package.json"
    lock = WEB / "package-lock.json"

    needs_install = (
        not nm.exists()
        or (lock.exists() and lock.stat().st_mtime > nm.stat().st_mtime)
    )

    if needs_install:
        log("web", "node_modules missing or outdated — running npm install…")
        r = subprocess.run([_npm_cmd(), "install"], cwd=WEB, capture_output=False)
        if r.returncode != 0:
            print(f"{c('err')}✗  npm install failed{c('reset')}")
            sys.exit(1)


# ── Healthcheck ────────────────────────────────────────────────────────────

def _wait_for_api(timeout: int = 30) -> bool:
    """Poll /api/health until FastAPI responds or we time out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(1)
            try:
                s.connect(("127.0.0.1", 8000))
                return True
            except OSError:
                time.sleep(0.5)
    return False


# ── Shutdown ───────────────────────────────────────────────────────────────

def shutdown(*_) -> None:
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True

    banner("Shutting down GATE Platform…", "err")

    for proc in _procs:
        try:
            if IS_WIN:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
        except Exception:
            pass

    for proc in _procs:
        try:
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()

    if _redis_ours:
        log("redis", "Stopping Docker container…")
        subprocess.run(["docker", "stop", "gate-redis"], capture_output=True)

    sys.exit(0)


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Start the GATE Platform")
    parser.add_argument(
        "--no-worker", action="store_true",
        help="Skip Celery worker (scans still trigger but run inline via asyncio fallback)"
    )
    args = parser.parse_args()

    # Ensure .env present
    if not (ROOT / ".env").exists():
        print(
            f"{c('err')}✗  .env file not found at {ROOT / '.env'}\n"
            f"   Copy .env.example to .env and set DATABASE_URL.{c('reset')}"
        )
        sys.exit(1)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    banner("GATE Platform — starting all services…")

    # ── 1. Redis ──────────────────────────────────────────────────────────
    ensure_redis()

    # ── 2. npm deps ───────────────────────────────────────────────────────
    ensure_npm_deps()

    # Shared env: gate_scanner now lives inside backend/, so PYTHONPATH points there
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
        "PYTHONUNBUFFERED": "1",
        "FORCE_COLOR": "1",
    }

    # ── 3. FastAPI backend ────────────────────────────────────────────────
    log("api", "Starting FastAPI on :8000…")
    _spawn("api", [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", "8000",
        "--reload",
        "--log-level", "info",
    ], cwd=BACKEND, env=env)

    log("info", "Waiting for API to be ready…")
    if _wait_for_api(30):
        log("api", f"{c('ok')}Listening on :8000{c('reset')}")
    else:
        log("api", f"{c('err')}Did not respond within 30 s — check logs above{c('reset')}")

    # ── 4. Celery worker + Beat scheduler ────────────────────────────────
    if not args.no_worker:
        log("worker", "Starting Celery worker…")
        worker_cmd = [
            sys.executable, "-m", "celery",
            "-A", "app.tasks.celery_app", "worker",
            "--loglevel=info",
            "--without-gossip",
            "--without-mingle",
        ]
        # billiard prefork pool uses POSIX shared memory that doesn't work on Windows
        if IS_WIN:
            worker_cmd.append("--pool=solo")
        else:
            worker_cmd += ["--concurrency=2"]
        _spawn("worker", worker_cmd, cwd=BACKEND, env=env)

        log("beat", "Starting Celery Beat scheduler…")
        _spawn("beat", [
            sys.executable, "-m", "celery",
            "-A", "app.tasks.celery_app", "beat",
            "--loglevel=info",
        ], cwd=BACKEND, env=env)
    else:
        log("info", "Celery worker + Beat skipped (--no-worker)")

    # ── 5. Next.js dev server ─────────────────────────────────────────────
    log("web", "Starting Next.js on :3000…")
    _spawn("web", [_npm_cmd(), "run", "dev"], cwd=WEB, env={
        **os.environ,
        "NEXT_PUBLIC_API_URL": "http://localhost:8000",
        "NEXT_PUBLIC_WS_URL":  "ws://localhost:8000/ws",
    })

    # ── Ready banner ──────────────────────────────────────────────────────
    print(f"""
{c('ok')}┌─────────────────────────────────────────────┐
│         GATE Platform is running            │
├─────────────────────────────────────────────┤
│  Frontend  →  http://localhost:3000         │
│  Backend   →  http://localhost:8000         │
│  API Docs  →  http://localhost:8000/api/docs│
└─────────────────────────────────────────────┘{c('reset')}
{c('dim')}Press Ctrl+C to stop all services.{c('reset')}
""")

    # ── Watch loop ────────────────────────────────────────────────────────
    try:
        while True:
            time.sleep(2)
            for proc in _procs:
                rc = proc.poll()
                if rc is not None:
                    log("err", f"A service exited with code {rc}. Shutting down…")
                    shutdown()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()

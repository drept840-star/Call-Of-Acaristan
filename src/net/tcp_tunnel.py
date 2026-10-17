"""Public raw-TCP tunnels for arena matches.

Bundled bore is preferred: no account and no joiner-side adapter. It relays
unencrypted traffic through bore.pub; availability and latency are not guaranteed.
Configured ngrok on PATH is an optional fallback. Cloudflare quick tunnels are
not used: their public HTTP hostname is not a directly connectable TCP endpoint.
"""
import atexit
import os
import sys
import queue
import re
import shutil
import subprocess
import threading
import time

_ENDPOINT_RE = re.compile(r"(?:tcp://|listening at )([A-Za-z0-9.-]+):(\d{1,5})(?!\d)")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PROCESSES = set()
_PROCESS_LOCK = threading.Lock()
_EXITING = False


def parse_endpoint(line):
    """Parse bore's listening address or ngrok's TCP URL, never an HTTP URL."""
    match = _ENDPOINT_RE.search(_ANSI_RE.sub("", str(line or "")))
    if match and 1 <= int(match.group(2)) <= 65535:
        return match.group(1), int(match.group(2))
    return None


def explain_error(error):
    """Translate provider failures without recommending an HTTP-only tunnel."""
    text = str(error or "")
    low = text.lower()
    if "err_ngrok_8013" in low or "add a credit or debit card" in low:
        return "ngrok TCP needs card verification (8013); use bundled bore instead"
    if "err_ngrok_9009" in low or "pay-as-you-go feature" in low:
        return "ngrok proxy_url requires a paid plan; remove it or use bundled bore"
    if "err_ngrok_4018" in low or "authtoken" in low:
        return "ngrok account is not configured; use bundled bore instead"
    if "bore is not installed" in low:
        return "bore was not found in assets/bin; reinstall the game or run tools/download_bore.py"
    return text


def stop_process(proc):
    """Stop a tunnel process without letting shutdown errors escape."""
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
    except (OSError, AttributeError, subprocess.TimeoutExpired):
        pass
    finally:
        with _PROCESS_LOCK:
            _PROCESSES.discard(proc)
        try:
            if proc.poll() is not None and proc.stdout is not None:
                proc.stdout.close()
        except (AttributeError, OSError, ValueError):
            pass


def _cleanup_processes():
    global _EXITING
    with _PROCESS_LOCK:
        _EXITING = True
        processes = list(_PROCESSES)
    for proc in processes:
        stop_process(proc)


atexit.register(_cleanup_processes)


def _popen(argv, env=None):
    """Start a tunnel CLI with no console window. Returns None on failure."""
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, errors="replace", bufsize=1,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with _PROCESS_LOCK:
            exiting = _EXITING
            if not exiting:
                _PROCESSES.add(proc)
        if exiting:
            stop_process(proc)
            return None
        return proc
    except OSError:
        return None


def _await_endpoint(proc, timeout, fill_port, cancelled=None):
    """Read *proc*'s output until a public endpoint appears.

    Returns ``(endpoint, tail, output_closed)``. The CLI output is the only
    notification either provider gives -- there is no API to poll and no port
    file -- so this has to read the child's stdout.

    ``output_closed`` separates the two failure messages that matter: a
    provider that exited (a missing authtoken, a refused plan) and one that is
    still running but has not published an address yet (a slow cold start).
    The host needs to be told which, because one is fixed by installing
    something and the other is fixed by waiting.
    """
    lines = queue.Queue()
    collecting = threading.Event()
    collecting.set()

    def read_output():
        try:
            for line in iter(proc.stdout.readline, ""):
                # Keep draining logs after startup without accumulating them.
                if collecting.is_set():
                    lines.put(line)
        except (OSError, ValueError):
            pass
        finally:
            lines.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    deadline = time.monotonic() + max(0.1, float(timeout))
    tail = []
    output_closed = False
    while time.monotonic() < deadline:
        if cancelled is not None and cancelled():
            break
        try:
            wait = min(0.25, max(0.01, deadline - time.monotonic()))
            line = lines.get(timeout=wait)
        except queue.Empty:
            if proc.poll() is not None:
                break
            continue
        if line is None:
            output_closed = True
            if proc.poll() is not None:
                break
            continue
        tail.append(line.strip())
        del tail[:-6]
        endpoint = parse_endpoint(line)
        if endpoint:
            host, port = endpoint
            port = fill_port if port is None else port
            if port and 1 <= int(port) <= 65535:
                collecting.clear()
                return (host, int(port)), tail, output_closed
    collecting.clear()
    return None, tail, output_closed


def find_bore():
    """Find a platform-appropriate bundled binary, then fall back to PATH."""
    name = "bore.exe" if os.name == "nt" else "bore"
    bases = [getattr(sys, "_MEIPASS", None),
             os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None,
             os.path.dirname(os.path.abspath(sys.argv[0] or ".")),
             os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
             os.getcwd()]
    for base in bases:
        if base:
            for sub in ("assets/bin", "_internal/assets/bin", "bin", "."):
                candidate = os.path.join(base, sub, name)
                if os.path.isfile(candidate) and (os.name == "nt" or os.access(candidate, os.X_OK)):
                    return candidate
    return shutil.which("bore")


def start_bore_tunnel(local_port, timeout=40.0, cancelled=None):
    """Expose localhost through bore.pub. Caller must stop the returned process."""
    exe = find_bore()
    if not exe:
        return None, None, "bore is not installed"
    env = os.environ.copy()
    env["RUST_LOG"] = "info"
    env["NO_COLOR"] = "1"
    # Avoid accidental inherited configuration on the public, no-secret relay.
    for key in ("BORE_SECRET", "BORE_PORT", "BORE_SERVER", "BORE_LOCAL_HOST"):
        env.pop(key, None)
    proc = _popen([exe, "local", str(int(local_port)), "--to", "bore.pub",
                   "--local-host", "127.0.0.1"], env=env)
    if proc is None:
        return None, None, "could not start bore"
    endpoint, tail, closed = _await_endpoint(proc, timeout, fill_port=None,
                                            cancelled=cancelled)
    if endpoint and proc.poll() is None:
        return endpoint, proc, ""
    stop_process(proc)
    if cancelled is not None and cancelled():
        return None, None, "tunnel start cancelled"
    detail = " | ".join(x for x in tail if x)
    if detail:
        return None, None, "bore could not open a TCP tunnel: %s" % detail[-220:]
    if closed or proc.poll() is not None:
        return None, None, "bore exited before publishing a TCP address"
    return None, None, "bore timed out; relay or outbound TCP port 7835 may be blocked"


def start_ngrok_tunnel(local_port, timeout=30.0, cancelled=None):
    """Start an ngrok TCP endpoint to localhost:*local_port*.

    Returns ``(endpoint, process, error)``. The caller owns the returned
    process and must stop it when the match ends. Missing executables, CLI
    setup errors, and timeout are reported as short player-facing errors.

    Kept as the FALLBACK rather than the default because free TCP is
    card-gated; see the module docstring.
    """
    exe = shutil.which("ngrok")
    if not exe:
        return None, None, (
            "ngrok is not installed; install and configure ngrok to enable "
            "internet hosting when router forwarding is unavailable")

    # ngrok treats an inherited HTTP proxy as a paid-plan-only feature. Try its
    # normal direct outbound path instead of silently surfacing ERR_NGROK_9009
    # on machines launched from proxy-configured IDEs.
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    proc = _popen([exe, "tcp", str(int(local_port))], env=env)
    if proc is None:
        return None, None, "could not start ngrok"
    endpoint, tail, closed = _await_endpoint(proc, timeout, fill_port=None,
                                            cancelled=cancelled)
    if endpoint and proc.poll() is None:
        return endpoint, proc, ""
    stop_process(proc)
    if cancelled is not None and cancelled():
        return None, None, "tunnel start cancelled"
    detail = " | ".join(x for x in tail if x)
    if detail:
        return None, None, "ngrok did not provide a TCP address: %s" % detail[-220:]
    if closed or proc.poll() is not None:
        return None, None, "ngrok exited before providing a TCP address"
    return None, None, "ngrok timed out before providing a TCP address"


def start_tunnel(local_port, timeout=40.0, cancelled=None):
    """Try bore first, configured ngrok second; report both failures honestly.

    *cancelled* is an optional zero-argument callable polled while waiting; when
    it returns true the pending provider is stopped promptly and no fallback runs.
    """
    port = int(local_port)
    if not 1 <= port <= 65535:
        return None, None, "local TCP port must be between 1 and 65535"
    endpoint, proc, err_bore = start_bore_tunnel(port, timeout, cancelled)
    if endpoint:
        return endpoint, proc, "bore"
    if cancelled is not None and cancelled():
        return None, None, "tunnel start cancelled"
    endpoint, proc, err_ngrok = start_ngrok_tunnel(port, timeout, cancelled)
    if endpoint:
        return endpoint, proc, "ngrok"
    return None, None, "; ".join(p for p in (err_bore, err_ngrok) if p)

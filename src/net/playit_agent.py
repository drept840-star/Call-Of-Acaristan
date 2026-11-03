"""Bundled playit.gg agent for hosts without their own playit install.

First use claims a new agent in the player's browser (their own playit
account, free tier) and keeps its secret in a per-user file. While hosting,
the official playitd runs as a child process on its own pipe, so it never
touches a playit service the player installed themselves. Free accounts get
a Terraria-type TCP tunnel plus a UDP tunnel to the game port; the address
comes back as "TCP+UDP" for the host field.
"""
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.request
import webbrowser

from net import tcp_tunnel

# Pinned official signed Windows x64 daemon; tools/download_playit.py uses the same pin.
PLAYITD_VERSION = "1.2.0"
PLAYITD_URL = ("https://github.com/playit-cloud/playit-agent/releases/download/"
               "v1.2.0/playitd-windows-x86_64-signed.exe")
PLAYITD_SHA256 = "e8dff30a9269a10d2c6786c95a0618567772e441d07dd7ebe3c1a37d3f35534d"
API_BASE = "https://api.playit.gg"
PIPE = r"\\.\pipe\acaristan-playitd"
CLAIM_TIMEOUT = 600.0
TUNNEL_TIMEOUT = 60.0

_agent = None


def data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Acaristan", "playit")


def secret_path():
    return os.path.join(data_dir(), "secret.txt")


def load_secret():
    try:
        with open(secret_path(), encoding="ascii") as f:
            value = f.read().strip()
        bytes.fromhex(value)
        return value
    except (OSError, ValueError, UnicodeDecodeError):
        return ""


def find_playitd():
    found = tcp_tunnel.find_bundled("playitd.exe")
    if found:
        return found
    cached = os.path.join(tcp_tunnel.bore_cache_dir(), "playitd.exe")
    if os.path.isfile(cached) and tcp_tunnel._sha256_file(cached) == PLAYITD_SHA256:
        return cached
    return None


def download_playitd(dest, timeout=60.0):
    """Fetch the pinned playitd into *dest*. Returns "" or a short reason."""
    try:
        with urllib.request.urlopen(PLAYITD_URL, timeout=timeout) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != PLAYITD_SHA256:
            return "playitd checksum mismatch"
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest + ".tmp", "wb") as f:
            f.write(data)
        os.replace(dest + ".tmp", dest)
    except Exception as exc:
        return "playitd download failed: %s" % (exc,)
    if tcp_tunnel._sha256_file(dest) != PLAYITD_SHA256:
        return "playitd was removed after download (antivirus?)"
    return ""


def api(path, body, secret=""):
    """POST to the playit API. Returns (status, data); never raises."""
    req = urllib.request.Request(API_BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    if secret:
        req.add_header("Authorization", "Agent-Key " + secret)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            reply = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            reply = json.loads(exc.read().decode("utf-8", "replace"))
        except ValueError:
            return "error", "HTTP %d" % exc.code
    except (OSError, ValueError) as exc:
        return "error", str(exc)
    if not isinstance(reply, dict):
        return "error", "bad reply"
    return reply.get("status", "error"), reply.get("data")


def claim(status, cancelled):
    """Approve a new agent in the browser; save and return its secret, or ""."""
    code = secrets.token_hex(5)
    url = "https://playit.gg/claim/" + code
    try:
        webbrowser.open(url)
    except Exception:
        pass
    status("approve the game in your browser (playit.gg/claim/%s)" % code)
    end = time.time() + CLAIM_TIMEOUT
    while time.time() < end and not cancelled():
        state, data = api("/claim/setup", {"code": code, "agent_type": "assignable",
                                           "version": "Call of Acaristan"})
        if state == "success" and data == "UserAccepted":
            break
        if state == "success" and data == "UserRejected":
            status("playit setup was declined in the browser")
            return ""
        time.sleep(2.0)
    else:
        return ""
    state, data = api("/claim/exchange", {"code": code})
    key = data.get("secret_key", "") if state == "success" and isinstance(data, dict) else ""
    if not key:
        status("playit setup failed: %s" % (data,))
        return ""
    os.makedirs(data_dir(), exist_ok=True)
    with open(secret_path(), "w", encoding="ascii") as f:
        f.write(key)
    return key


def start_agent(secret):
    """Run playitd for *secret* unless this game already runs it. Returns ""
    or a short reason. The process stops with the game (tcp_tunnel atexit)."""
    global _agent
    if _agent is not None and _agent.poll() is None:
        return ""
    exe = find_playitd()
    if not exe and os.name == "nt":
        exe = os.path.join(tcp_tunnel.bore_cache_dir(), "playitd.exe")
        err = download_playitd(exe)
        if err:
            return err
    if not exe:
        return "playit agent is not bundled with this build"
    _agent = tcp_tunnel._popen([exe, "--secret-path", secret_path(),
                                "--socket-path", PIPE])
    return "" if _agent is not None else "could not start the playit agent"


def find_tunnels(tunnels, local_port):
    """Pick the TCP and UDP tunnel addresses that reach *local_port*."""
    tcp = udp = ""
    for t in tunnels or ():
        if not isinstance(t, dict) or t.get("local_port") != local_port or t.get("disabled"):
            continue
        port = (t.get("port") or {}).get("from")
        host = t.get("custom_domain") or t.get("assigned_domain")
        if not host or not port:
            continue
        addr = "%s:%d" % (host, port)
        if t.get("proto") in ("tcp", "both") and not tcp:
            tcp = addr
        if t.get("proto") in ("udp", "both") and not udp:
            udp = addr
    return tcp, udp


def _create_tunnel(secret, agent_id, local_port, tunnel_type, port_type):
    return api("/tunnels/create", {
        "name": "acaristan-" + port_type, "tunnel_type": tunnel_type,
        "port_type": port_type, "port_count": 1,
        "origin": {"type": "agent", "data": {"agent_id": agent_id,
                                             "local_ip": "127.0.0.1",
                                             "local_port": local_port}},
        "enabled": True, "alloc": None, "firewall_id": None,
        "proxy_protocol": None}, secret)


def setup(local_port, status, cancelled):
    """Claim (first time), start the agent and return "TCP+UDP" or ""."""
    secret = load_secret()
    if not secret:
        secret = claim(status, cancelled)
        if not secret:
            return ""
    err = start_agent(secret)
    if err:
        status(err)
        return ""
    status("waiting for playit tunnels...")
    created = False
    end = time.time() + TUNNEL_TIMEOUT
    while time.time() < end and not cancelled():
        state, data = api("/agents/rundata", {}, secret)
        if state != "success" or not isinstance(data, dict):
            status("playit: %s" % (data,))
            time.sleep(3.0)
            continue
        tcp, udp = find_tunnels(data.get("tunnels"), local_port)
        if tcp and udp:
            return tcp + "+" + udp
        if not created:
            created = True
            agent_id = data.get("agent_id")
            if not tcp:
                _create_tunnel(secret, agent_id, local_port, "terraria", "tcp")
            if not udp:
                _create_tunnel(secret, agent_id, local_port, None, "udp")
        time.sleep(3.0)
    if not cancelled():
        try:
            webbrowser.open("https://playit.gg/account/tunnels")
        except Exception:
            pass
        status("add a Terraria TCP and a UDP tunnel to 127.0.0.1:%d on playit.gg"
               % local_port)
    return ""

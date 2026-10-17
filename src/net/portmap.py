
"""Automatic router port forwarding (UPnP IGD + NAT-PMP), stdlib only.

Why this module exists
----------------------
"Run an EXE and give your friends the address" only works if your router
lets traffic in. Almost every home network sits behind NAT, so a server
bound to 0.0.0.0 is reachable from the LAN but invisible from the internet
until the router is told to forward a port to it.

Most routers expose one of two mechanisms, and we try both:

  * **UPnP IGD** -- SSDP discovery on UDP 1900, then a SOAP
    ``AddPortMapping`` call. Universally supported on consumer routers.
  * **NAT-PMP / PCP** -- a tiny UDP protocol on port 5351. Supported by
    Apple routers and modern OpenWrt, and it also hands back the *external*
    IP address, which we need anyway to tell the host what to share.

Either can fail, and both can be disabled by the user. That is why every
function here returns a result object instead of raising, and why
``open_port`` reports a human-readable reason on failure: the host screen
has to tell the player what went wrong and what to do manually.

This is a convenience, never a requirement. If it fails we still know our
LAN address, and the player can forward the port by hand.
"""

import ipaddress
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_TARGETS = (
    "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
)

NATPMP_PORT = 5351
NATPMP_VERSION = 0
OPCODE_EXTERNAL = 0
OPCODE_UDP_MAP = 1
OPCODE_MAP = 2  # TCP mapping; the match listener is TCP.

WAN_SERVICES = (
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANIPConnection:2",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
)


class ForwardResult(object):
    """Outcome of a port-mapping attempt.

    ``method`` is one of "upnp", "natpmp", or None.
    ``external_ip`` may be None when the mechanism did not report one.
    ``guidance`` is a short, player-facing next step on failure.
    """

    def __init__(self, ok, method=None, external_ip=None, error="", guidance=""):
        self.ok = ok
        self.method = method
        self.external_ip = external_ip
        self.error = error
        self.guidance = guidance

    def __repr__(self):
        return ("ForwardResult(ok=%r, method=%r, external_ip=%r, error=%r)"
                % (self.ok, self.method, self.external_ip, self.error))


def _local_ip():
    """Our address on the default route, without sending any traffic.

    Connecting a UDP socket does not send a packet; it just picks the
    outbound interface. That is the standard trick for learning "what
    address would the outside world use to reach me".
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def local_ip():
    """The machine's LAN-visible address (e.g. 192.168.0.185)."""
    return _local_ip()


def _hamachi_address(addr):
    """Return a canonical Hamachi virtual IPv4 address, or None.

    Hamachi assigns virtual IPv4 addresses from 25.0.0.0/8. The address is
    what peers should use for a direct game TCP connection over the overlay.
    """
    try:
        ip = ipaddress.IPv4Address(str(addr).strip())
    except (ipaddress.AddressValueError, ValueError, TypeError):
        return None
    return str(ip) if ip in ipaddress.IPv4Network("25.0.0.0/8") else None


def _parse_hamachi_addresses(output):
    """Extract Hamachi virtual IPv4 addresses from command output."""
    out = []
    for line in str(output or "").splitlines():
        candidate = _hamachi_address(line.strip())
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def hamachi_ipv4():
    """Find this machine's active Hamachi IPv4 address, if any.

    On Windows, query the adapter/IP association so an unrelated 25/8 address
    is not accidentally advertised. If PowerShell's networking cmdlets aren't
    available, fall back to the OS hostname resolver and still require 25/8.
    This is read-only and returns None when Hamachi is absent/offline.
    """
    candidates = []
    if os.name == "nt":
        script = (
            "$a = Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue "
            "| Where-Object { $_.Status -eq 'Up' -and "
            "($_.Name -match 'Hamachi' -or "
            "$_.InterfaceDescription -match 'Hamachi') }; "
            "$i = @($a | ForEach-Object { $_.ifIndex }); "
            "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue "
            "| Where-Object { $_.InterfaceIndex -in $i -and "
            "$_.IPAddress -like '25.*' } "
            "| ForEach-Object { $_.IPAddress }"
        )
        try:
            kwargs = {
                "stderr": subprocess.DEVNULL,
                "timeout": 3.0,
                "text": True,
                "errors": "replace",
            }
            no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if no_window:
                kwargs["creationflags"] = no_window
            output = subprocess.check_output(
                ["powershell.exe", "-NoProfile", "-NonInteractive",
                 "-Command", script], **kwargs)
            candidates.extend(_parse_hamachi_addresses(output))
        except (OSError, subprocess.SubprocessError):
            pass

    if not candidates:
        try:
            entries = socket.getaddrinfo(socket.gethostname(), None,
                                         socket.AF_INET, socket.SOCK_STREAM)
        except OSError:
            entries = ()
        for entry in entries:
            candidate = _hamachi_address(entry[4][0])
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    return candidates[0] if candidates else None


def _windows_default_gateway(output):
    """Extract the IPv4 next hop from ``route print -4`` output."""
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 5 or fields[0] != "0.0.0.0" \
                or fields[1] != "0.0.0.0":
            continue
        gateway = fields[2]
        try:
            socket.inet_aton(gateway)
        except OSError:
            continue
        if gateway != "0.0.0.0":
            return gateway
    return None


def _default_gateway():
    """Best-effort IPv4 default gateway, needed for NAT-PMP requests.

    NAT-PMP is a router protocol, not a local-service protocol. Sending its
    packets to 127.0.0.1 silently guarantees failure on ordinary machines.
    The OS route table is the authoritative source of the default next hop.
    """
    if os.name == "nt":
        try:
            kwargs = {
                "stderr": subprocess.DEVNULL,
                "timeout": 3.0,
                "text": True,
                "errors": "replace",
            }
            no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if no_window:
                kwargs["creationflags"] = no_window
            output = subprocess.check_output(["route", "print", "-4"],
                                             **kwargs)
            return _windows_default_gateway(output)
        except (OSError, subprocess.SubprocessError):
            return None

    # Linux exposes the route table without needing an external command.
    try:
        with open("/proc/net/route", "r", encoding="ascii") as routes:
            next(routes, None)  # column headings
            for line in routes:
                fields = line.split()
                if len(fields) < 4 or fields[1] != "00000000":
                    continue
                if not (int(fields[3], 16) & 0x2):
                    continue
                return socket.inet_ntoa(
                    struct.pack("<I", int(fields[2], 16)))
    except (OSError, ValueError):
        pass

    # macOS and other Unix-like systems commonly ship this read-only query.
    try:
        output = subprocess.check_output(
            ["route", "-n", "get", "default"],
            stderr=subprocess.DEVNULL, timeout=3.0, text=True,
            errors="replace")
        for line in output.splitlines():
            key, sep, value = line.strip().partition(":")
            if sep and key.strip().lower() == "gateway":
                gateway = value.strip()
                socket.inet_aton(gateway)
                return gateway
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def is_private(addr):
    """True if an IPv4 address is not directly reachable from the public internet."""
    try:
        parts = [int(p) for p in addr.split(".")]
    except (ValueError, AttributeError):
        return False
    if len(parts) != 4:
        return False
    a, b = parts[0], parts[1]
    if a in (10, 127):
        return True
    if a == 192 and b == 168:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 100 and 64 <= b <= 127:  # carrier-grade NAT (RFC 6598)
        return True
    if a == 169 and b == 254:  # link-local; no internet route
        return True
    return False


# ── NAT-PMP ──────────────────────────────────────────────────────

def _natpmp_request(sock, opcode, internal_port=0, external_port=0,
                    lifetime=0, gateway=None):
    """Send one NAT-PMP request, return (result_code, external_ip, mapped_port).

    The 8-byte header is version (1), opcode (1), result code (2), and
    epoch (4).
    A mapping request appends internal port, external port (both network
    byte order) and lifetime.
    """
    epoch = int(time.time()) - 1900
    if opcode == OPCODE_MAP:
        body = (struct.pack("!HH", internal_port, external_port)
                + struct.pack("!I", lifetime))
    else:
        body = b""
    pkt = struct.pack("!BBHI", NATPMP_VERSION, opcode, 0, epoch) + body
    if not gateway:
        raise ValueError("NAT-PMP requires the default router address")
    sock.sendto(pkt, (gateway, NATPMP_PORT))
    sock.settimeout(2.0)
    data, _addr = sock.recvfrom(32)
    minimum = 12 if opcode == OPCODE_EXTERNAL else 16
    if len(data) < minimum:
        # Reject truncated replies before reading address/port fields.
        return (12, None, 0)
    _ver, _op, result, _epoch = struct.unpack("!BBHI", data[:8])
    if _ver != NATPMP_VERSION or _op != (opcode | 0x80):
        return (12, None, 0)
    ext_ip = None
    mapped = 0
    if opcode == OPCODE_EXTERNAL and len(data) >= 12:
        # External-address replies are 12 bytes total: 8-byte header plus
        # the 4-byte IPv4 address. Requiring 16 silently discarded every
        # valid response and forced the host to rely on a separate STUN call.
        ext_ip = socket.inet_ntoa(data[8:12])
    if opcode == OPCODE_MAP and len(data) >= 16:
        # Response layout: 8-byte header, internal port, external port,
        # lifetime. The assigned external port is bytes 10..11.
        mapped = struct.unpack("!H", data[10:12])[0]
    return (result, ext_ip, mapped)


_NATPMP_ERRORS = {
    1: "router refused the mapping",
    2: "network failure (no internet?)",
    3: "no gateway available",
    4: "unsupported by this router",
    5: "NAT-PMP disabled on the router",
    6: "router cannot map this port",
    7: "mapping already exists (try again)",
    8: "router is out of resources",
    11: "protocol version not supported",
    12: "unsupported version",
}


def try_natpmp(internal_port, lifetime=3600):
    """Attempt a NAT-PMP mapping through the OS default gateway. Never raises."""
    gateway = _default_gateway()
    if not gateway:
        return ForwardResult(False, error="default router could not be identified")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError as exc:
        return ForwardResult(False, error="socket: %s" % exc)
    try:
        result, ext_ip, _mapped = _natpmp_request(
            sock, OPCODE_EXTERNAL, gateway=gateway)
        if result != 0:
            return ForwardResult(False, error=_NATPMP_ERRORS.get(
                result, "code %d" % result))
        result, _ip, _mapped = _natpmp_request(
            sock, OPCODE_MAP, internal_port, internal_port, lifetime,
            gateway=gateway)
        if result != 0:
            return ForwardResult(False, external_ip=ext_ip,
                                 error=_NATPMP_ERRORS.get(result, "code %d" % result))
        return ForwardResult(True, method="natpmp", external_ip=ext_ip)
    except (OSError, socket.timeout) as exc:
        return ForwardResult(False, error="no NAT-PMP gateway (%s)" % (exc or "timeout"))
    finally:
        sock.close()


# ── UPnP IGD ─────────────────────────────────────────────────────

def _ssdp_discover(timeout=3.0):
    """Return the LOCATION URL(s) of UPnP IGDs on the LAN."""
    found = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
    except OSError:
        return found
    try:
        for target in SSDP_TARGETS:
            msg = (
                "M-SEARCH * HTTP/1.1\r\n"
                "HOST: %s:%d\r\n"
                'MAN: "ssdp:discover"\r\n'
                "MX: 2\r\n"
                "ST: %s\r\n\r\n" % (SSDP_ADDR, SSDP_PORT, target)
            )
            try:
                sock.sendto(msg.encode("ascii"), (SSDP_ADDR, SSDP_PORT))
            except OSError:
                break
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, _addr = sock.recvfrom(2048)
                except (socket.timeout, OSError):
                    break
                for line in data.decode("utf-8", "replace").splitlines():
                    if line.upper().startswith("LOCATION:"):
                        url = line.split(":", 1)[1].strip()
                        if url and url not in found:
                            found.append(url)
    finally:
        sock.close()
    return found


def _http_exchange(url, method, body=None, headers=None, timeout=4.0):
    """Minimal HTTP client. Returns (status_code, body_bytes) or (None, None).

    Deliberately hand-rolled: urllib would work but drags in redirect and
    cookie handling we do not want on a LAN gateway.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or not parts.hostname:
        return (None, None)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    lines = ["%s %s HTTP/1.1" % (method, path),
             "Host: %s" % parts.hostname,
             "Connection: close"]
    for key, value in (headers or {}).items():
        lines.append("%s: %s" % (key, value))
    if body is not None:
        lines.append("Content-Length: %d" % len(body))
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("utf-8")
    if body is not None:
        request += body
    try:
        sock = socket.create_connection((parts.hostname, parts.port or 80), timeout)
    except OSError:
        return (None, None)
    try:
        sock.sendall(request)
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if sum(len(c) for c in chunks) > 512 * 1024:
                break
    except OSError:
        return (None, None)
    finally:
        sock.close()
    raw = b"".join(chunks)
    status = 0
    if raw.startswith(b"HTTP/"):
        try:
            status = int(raw.split(b" ", 2)[1])
        except (IndexError, ValueError):
            status = 0
    for sep in (b"\r\n\r\n", b"\n\n"):
        idx = raw.find(sep)
        if idx != -1:
            return (status, raw[idx + len(sep):])
    return (status, b"")


def _find_wan_service(xml_bytes):
    """Walk the device description tree, return (control_url, service_type).

    The XML nests devices inside devices, so this recurses instead of
    doing a flat search. Returns (None, None) when there is no WAN service.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return (None, None)
    ns = {"d": "urn:schemas-upnp-org:device-1-0"}

    def walk(node):
        for svc in node.findall("d:serviceList/d:service", ns):
            st = svc.findtext("d:serviceType", default="", namespaces=ns)
            cu = svc.findtext("d:controlURL", default="", namespaces=ns)
            if st in WAN_SERVICES and cu:
                return (cu, st)
        for dev in node.findall("d:deviceList/d:device", ns):
            found = walk(dev)
            if found[0]:
                return found
        return (None, None)

    return walk(root)


def _soap_call(base_url, control_url, service_type, action, args, timeout=4.0):
    """Invoke a SOAP action; return the response body bytes or None."""
    body_args = "".join("<%s>%s</%s>" % (k, v, k) for k, v in args)
    envelope = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
        '<u:%s xmlns:u="%s">%s</u:%s>'
        "</s:Body></s:Envelope>" % (action, service_type, body_args, action)
    )
    url = urllib.parse.urljoin(base_url, control_url)
    _status, body = _http_exchange(
        url, "POST", envelope.encode("utf-8"),
        {"Content-Type": 'text/xml; charset="utf-8"',
         "SOAPAction": '"%s#%s"' % (service_type, action)},
        timeout,
    )
    return body


def _upnp_external_ip(base_url, control_url, service_type, timeout=4.0):
    """Ask the gateway for its WAN address. Returns None if unavailable."""
    body = _soap_call(base_url, control_url, service_type,
                      "GetExternalIPAddress", [], timeout)
    if not body:
        return None
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1] == "NewExternalIPAddress" and elem.text:
            candidate = elem.text.strip()
            if candidate and candidate != "0.0.0.0":
                return candidate
    return None


_UPNP_ERRORS = {
    "713": "router already has a conflicting mapping",
    "718": "router refused: conflicts with an existing mapping",
    "725": "router only accepts permanent mappings",
    "732": "router rejected our internal address",
    "402": "router rejected the arguments",
}


def try_upnp(internal_port, external_port=None, lifetime=3600,
             description="Call of Acaristan"):
    """Attempt a UPnP IGD mapping. Never raises."""
    external_port = external_port or internal_port
    try:
        locations = _ssdp_discover(timeout=3.0)
    except Exception as exc:
        return ForwardResult(False, error="SSDP failed: %s" % exc)
    if not locations:
        return ForwardResult(False, error="no UPnP gateway on the LAN")

    last_error = "gateway exposed no WAN service"
    for base_url in locations:
        try:
            _status, body = _http_exchange(base_url, "GET")
        except Exception as exc:
            last_error = "device description failed: %s" % exc
            continue
        if not body:
            continue
        control_url, service_type = _find_wan_service(body)
        if not control_url:
            continue
        # The description goes inside a SOAP element, so it must be escaped.
        esc = (description.replace("&", "&amp;").replace("<", "&lt;")
               .replace(">", "&gt;").replace('"', "&quot;"))
        args = [
            ("NewRemoteHost", ""),
            ("NewExternalPort", str(external_port)),
            ("NewProtocol", "TCP"),
            ("NewInternalPort", str(internal_port)),
            ("NewInternalClient", _local_ip()),
            ("NewEnabled", "1"),
            ("NewPortMappingDescription", esc),
            ("NewLeaseDuration", str(lifetime)),
        ]
        try:
            response = _soap_call(base_url, control_url, service_type,
                                  "AddPortMapping", args)
        except Exception as exc:
            last_error = "SOAP failed: %s" % exc
            continue
        if response is None:
            last_error = "no response from gateway"
            continue
        text = response.decode("utf-8", "replace")
        if "AddPortMappingResponse" in text:
            ext_ip = None
            try:
                ext_ip = _upnp_external_ip(base_url, control_url, service_type)
            except Exception:
                pass
            return ForwardResult(True, method="upnp", external_ip=ext_ip)
        for code, meaning in _UPNP_ERRORS.items():
            if code in text:
                return ForwardResult(False, error=meaning)
        last_error = "gateway returned an error"
    return ForwardResult(False, error=last_error)


def open_port(internal_port, external_port=None, lifetime=3600,
              description="Call of Acaristan"):
    """Forward a port to this machine. Tries UPnP, then NAT-PMP.

    Returns a ForwardResult; never raises. On total failure the result
    carries ``guidance`` telling the player exactly what to do by hand,
    because plenty of routers have UPnP switched off.
    """
    external_port = external_port or internal_port
    upnp = try_upnp(internal_port, external_port, lifetime, description)
    if upnp.ok:
        return upnp
    pmp = try_natpmp(internal_port, lifetime)
    if pmp.ok:
        return pmp
    return ForwardResult(
        False,
        error="; ".join(x for x in (upnp.error, pmp.error) if x),
        guidance=("Log into your router and forward TCP port %d to %s, then "
                  "share your public IP. Or run tools/mp_host.py --relay."
                  % (external_port, _local_ip())),
    )


# ── STUN: what is my public address? ─────────────────────────────
#
# Even when port forwarding is impossible, the host still needs to know
# its PUBLIC ip so it can display it (and so the player can check whether
# the address they are about to share looks right). A STUN binding request
# is a 20-byte UDP packet to a well-known server that replies with the
# source address it saw. No third-party dependency, no account, no data
# beyond the query itself.

STUN_MAGIC = 0x2112A442
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101

# Public STUN servers. These are the standard ones published for this
# purpose; a failure here is never fatal, we just report "unknown".
STUN_SERVERS = (
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
)


def _stun_probe(host, port, timeout=2.0):
    """Send one binding request. Returns the observed public IP or None."""
    try:
        addr = socket.gethostbyname(host)
    except OSError:
        return None
    # Transaction ID: any value will do; it only guards against matching a
    # stale reply. The header is 20 bytes: type(2) length(2) cookie(4)
    # txid(12). The trailing 12 zero bytes are the FINGERPRINT/attribute
    # area -- a short packet is silently ignored by STUN servers, so the
    # full 20 must be sent or we get no reply at all.
    packet = (struct.pack("!HHI", STUN_BINDING_REQUEST, 0, STUN_MAGIC)
              + struct.pack("!HH", int(time.time()) & 0xFFFF, 0x1234)
              + b"\x00" * 8)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(timeout)
        sock.sendto(packet, (addr, port))
        data, _src = sock.recvfrom(2048)
    except (OSError, socket.timeout):
        return None
    finally:
        sock.close()
    if len(data) < 20:
        return None
    msg_type, msg_len, magic = struct.unpack("!HHI", data[:8])
    if magic != STUN_MAGIC or msg_type != STUN_BINDING_RESPONSE:
        return None
    # Walk the attribute list looking for XOR-MAPPED-ADDRESS (0x0020).
    offset = 20
    while offset + 4 <= len(data):
        attr_type, attr_len = struct.unpack("!HH", data[offset:offset + 4])
        value = data[offset + 4:offset + 4 + attr_len]
        offset += 4 + attr_len
        # Attributes are padded to a 4-byte boundary.
        offset += (4 - (attr_len % 4)) % 4
        if attr_type == 0x0020 and len(value) >= 8:
            # Family is in byte 1; 0x01 means IPv4.
            if value[1] == 0x01:
                xport = struct.unpack("!H", value[2:4])[0] ^ (STUN_MAGIC >> 16)
                xaddr = struct.unpack("!I", value[4:8])[0] ^ STUN_MAGIC
                return (socket.inet_ntoa(struct.pack("!I", xaddr)), xport)
    return None


def public_ip(timeout=2.0):
    """Best-effort public IP. Returns None if no STUN server answers.

    Deliberately never raises and never blocks for long: the caller is
    usually a UI thread that must keep drawing.
    """
    for host, port in STUN_SERVERS:
        result = _stun_probe(host, port, timeout)
        if result:
            return result[0]
    return None


def share_address(port, forwarded=False):
    """The address a friend should type, and whether it is public.

    Returns (address_string, is_public). When we know a public IP we
    prefer it, because that is what a friend on the internet needs. When
    the port was not forwarded, the honest answer is the LAN address and
    is_public=False -- sharing a public IP that cannot reach us would be
    worse than useless.
    """
    if forwarded:
        ext = public_ip()
        if ext:
            return ("%s:%d" % (ext, port), True)
    return ("%s:%d" % (_local_ip(), port), False)

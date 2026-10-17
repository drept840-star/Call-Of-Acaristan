"""Fast stdlib-only tunnel regression tests (no pygame or internet required)."""
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from net import tcp_tunnel as tt


class TunnelTests(unittest.TestCase):
    def test_endpoint_validation(self):
        self.assertEqual(tt.parse_endpoint('\x1b[32mINFO\x1b[0m listening at bore.pub:12345'), ('bore.pub', 12345))
        self.assertEqual(tt.parse_endpoint('Forwarding tcp://host.example:3456'), ('host.example', 3456))
        for log in ('https://foo.trycloudflare.com', 'tcp://host:0', 'tcp://host:65536', 'tcp://host:123456', 'INFO connected to server remote_port=1234'):
            self.assertIsNone(tt.parse_endpoint(log))

    def test_preference_and_fallback(self):
        with patch.object(tt, 'start_bore_tunnel', return_value=(('bore.pub', 12345), None, '')), patch.object(tt, 'start_ngrok_tunnel') as ng:
            self.assertEqual(tt.start_tunnel(27017), (('bore.pub', 12345), None, 'bore'))
            ng.assert_not_called()
        with patch.object(tt, 'start_bore_tunnel', return_value=(None, None, 'bore failed')), patch.object(tt, 'start_ngrok_tunnel', return_value=(None, None, 'ngrok failed')):
            self.assertEqual(tt.start_tunnel(27017), (None, None, 'bore failed; ngrok failed'))

    def test_lookup_bundle_outside_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / 'assets/bin' / ('bore.exe' if os.name == 'nt' else 'bore')
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b'fake test binary')
            exe.chmod(0o755)
            with patch.object(sys, '_MEIPASS', folder, create=True):
                self.assertEqual(tt.find_bore(), str(exe))

    def test_silent_process_timeout(self):
        proc = tt._popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            then = time.monotonic()
            endpoint, _, _ = tt._await_endpoint(proc, .15, None)
            self.assertIsNone(endpoint)
            self.assertLess(time.monotonic() - then, 1.5)
            self.assertIn(proc, tt._PROCESSES)
        finally:
            tt.stop_process(proc)
        self.assertIsNotNone(proc.poll())
        self.assertNotIn(proc, tt._PROCESSES)

    def test_cancel_stops_pending_start_promptly(self):
        proc = tt._popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        try:
            then = time.monotonic()
            endpoint, _, _ = tt._await_endpoint(proc, 20, None, cancelled=lambda: True)
            self.assertIsNone(endpoint)
            self.assertLess(time.monotonic() - then, 1.0)
        finally:
            tt.stop_process(proc)
        with patch.object(tt, 'start_bore_tunnel', return_value=(None, None, 'tunnel start cancelled')), \
                patch.object(tt, 'start_ngrok_tunnel') as ng:
            self.assertEqual(tt.start_tunnel(27017, cancelled=lambda: True),
                             (None, None, 'tunnel start cancelled'))
            ng.assert_not_called()

    def test_atexit_stops_child(self):
        code = "from net import tcp_tunnel as tt; import sys; p=tt._popen([sys.executable,'-c','import time; time.sleep(30)']); print(p.pid, flush=True)"
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=5, check=True)
        if os.name != 'nt':
            pid = int(result.stdout.strip())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)


if __name__ == '__main__':
    unittest.main()

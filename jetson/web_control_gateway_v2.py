#!/usr/bin/env python3
"""Stable manual-control gateway. It translates JSON commands to official TCP frames."""
import base64, hashlib, json, mimetypes, os, socket, struct, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'web'
ARTIFACTS = Path(os.environ.get('GARBAGE_ARTIFACTS', str(ROOT.parent / 'artifacts')))
BACKEND_HOST, BACKEND_PORT = os.environ.get('ROBOT_TCP_HOST', '127.0.0.1'), int(os.environ.get('ROBOT_TCP_PORT', '6000'))
LISTEN_PORT = int(os.environ.get('WEB_CONTROL_PORT', '8080'))

def frame(kind, data=''):
    # The official protocol counts DATA hex characters, not decoded bytes.
    body = '01' + kind + f'{len(data) + 2:02X}' + data
    checksum = sum(int(body[i:i + 2], 16) for i in range(0, len(body), 2)) & 255
    return f'${body}{checksum:02X}#\n'.encode('ascii')

def value_hex(value):
    value = max(-100, min(100, int(value)))
    return f'{(value if value >= 0 else value + 256) & 255:02X}'

def joystick(x, y): return frame('10', value_hex(x) + value_hex(y))
def direction(value): return frame('15', f'{max(0, min(7, int(value))):02X}')

class Backend:
    def __init__(self):
        self.sock = None; self.lock = threading.Lock(); self.connected = False; self.last = time.monotonic(); self.stop_event = threading.Event()
        threading.Thread(target=self.watchdog, daemon=True).start()
    def ensure(self):
        if self.sock: return True
        try:
            self.sock = socket.create_connection((BACKEND_HOST, BACKEND_PORT), 1.5); self.sock.settimeout(None); self.connected = True
            print(f'[gateway] connected TCP {BACKEND_HOST}:{BACKEND_PORT}', flush=True); return True
        except OSError as exc:
            self.connected = False; print(f'[gateway] TCP unavailable: {exc}', flush=True); return False
    def send(self, packet):
        with self.lock:
            if not self.ensure(): return False
            try: self.sock.sendall(packet); self.last = time.monotonic(); return True
            except OSError: self.close(); return False
    def stop(self): self.send(joystick(0, 0)); self.send(direction(7))
    def close(self):
        try:
            if self.sock: self.sock.close()
        except OSError: pass
        self.sock = None; self.connected = False
    def watchdog(self):
        while not self.stop_event.wait(.2):
            if self.sock and time.monotonic() - self.last > 1:
                self.stop(); self.last = time.monotonic()

BACKEND = Backend()

def read_exact(sock, count):
    data = b''
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part: raise ConnectionError('closed')
        data += part
    return data

def read_ws(sock):
    first, second = read_exact(sock, 2); opcode = first & 15; length = second & 127
    if length == 126: length = struct.unpack('!H', read_exact(sock, 2))[0]
    elif length == 127: length = struct.unpack('!Q', read_exact(sock, 8))[0]
    mask = read_exact(sock, 4) if second & 128 else b''; data = bytearray(read_exact(sock, length))
    for i in range(length):
        if mask: data[i] ^= mask[i % 4]
    return opcode, bytes(data)

def send_ws(sock, text):
    data = text.encode('utf-8'); size = len(data)
    if size < 126: header = bytes((129, size))
    elif size < 65536: header = bytes((129, 126)) + struct.pack('!H', size)
    else: header = bytes((129, 127)) + struct.pack('!Q', size)
    sock.sendall(header + data)

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, fmt, *args): print('[http] ' + fmt % args, flush=True)
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/ws' and self.headers.get('Upgrade', '').lower() == 'websocket': return self.websocket()
        if path == '/api/status': return self.json_response({'ok': True, 'backend_connected': BACKEND.connected})
        if path == '/api/yolo/latest':
            try: return self.json_response(json.loads((ARTIFACTS / 'detections.json').read_text(encoding='utf-8')))
            except Exception: return self.json_response({'ok': False, 'detections': []})
        if path.startswith('/artifacts/'):
            base, file = ARTIFACTS.resolve(), (ARTIFACTS / path[11:]).resolve()
        else:
            base, file = ROOT.resolve(), (ROOT / ('index.html' if path in ('', '/') else path[1:])).resolve()
        if (base not in file.parents and file != base) or not file.is_file(): return self.send_error(404)
        data = file.read_bytes(); self.send_response(200); self.send_header('Content-Type', mimetypes.guess_type(str(file))[0] or 'application/octet-stream'); self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)
    def json_response(self, value):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8'); self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)
    def websocket(self):
        key = self.headers.get('Sec-WebSocket-Key', ''); accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101, 'Switching Protocols'); self.send_header('Upgrade', 'websocket'); self.send_header('Connection', 'Upgrade'); self.send_header('Sec-WebSocket-Accept', accept); self.end_headers()
        sock = self.connection; sock.settimeout(30); send_ws(sock, json.dumps({'state': '已连接', 'backend': BACKEND.connected}, ensure_ascii=False))
        try:
            while True:
                opcode, data = read_ws(sock)
                if opcode == 8: break
                if opcode == 9: sock.sendall(b'\x8A\x00'); continue
                if opcode != 1: continue
                msg, kind = json.loads(data.decode('utf-8')), None
                kind = msg.get('type')
                if kind == 'joystick': ok = BACKEND.send(joystick(msg.get('x', 0), msg.get('y', 0)))
                elif kind == 'direction': ok = BACKEND.send(direction(msg.get('value', 7)))
                elif kind == 'speed': ok = BACKEND.send(frame('16', f'{max(0,min(100,int(msg.get("xy",30)))):02X}{max(0,min(100,int(msg.get("z",30)))):02X}'))
                elif kind == 'stop': ok = BACKEND.send(joystick(0, 0)) and BACKEND.send(direction(7))
                elif kind == 'heartbeat': ok = True
                else: ok = False
                send_ws(sock, json.dumps({'state': '已发送' if ok else '小车 TCP 未连接', 'backend': BACKEND.connected}, ensure_ascii=False))
        except (ConnectionError, OSError, ValueError, json.JSONDecodeError): pass
        finally: BACKEND.stop()

def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True); server = ThreadingHTTPServer(('0.0.0.0', LISTEN_PORT), Handler)
    print(f'[gateway] http://0.0.0.0:{LISTEN_PORT} -> {BACKEND_HOST}:{BACKEND_PORT}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: BACKEND.stop_event.set(); BACKEND.stop(); BACKEND.close(); server.server_close()

if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Robust PWA gateway: calibrated X3 motion, reconnecting WebSocket and low-FPS MJPEG."""
import base64, hashlib, json, mimetypes, os, socket, struct, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import cv2
except Exception:
    cv2 = None

ROOT = Path(__file__).resolve().parent.parent / 'web'
ARTIFACTS = Path(os.environ.get('GARBAGE_ARTIFACTS', str(ROOT.parent / 'artifacts')))
BACKEND_HOST = os.environ.get('ROBOT_TCP_HOST', '127.0.0.1')
BACKEND_PORT = int(os.environ.get('ROBOT_TCP_PORT', '6000'))
LISTEN_PORT = int(os.environ.get('WEB_CONTROL_PORT', '8080'))
CAMERA_SOURCE = os.environ.get('CAMERA_SOURCE', '/dev/video0')
CAMERA_FPS = max(1, min(10, int(os.environ.get('CAMERA_FPS', '5'))))


def frame(kind, data=''):
    body = '01' + kind + f'{len(data) + 2:02X}' + data
    checksum = sum(int(body[i:i + 2], 16) for i in range(0, len(body), 2)) & 255
    return f'${body}{checksum:02X}#\n'.encode('ascii')


def byte_hex(value):
    value = max(-100, min(100, int(value)))
    return f'{(value if value >= 0 else value + 256) & 255:02X}'


def joystick(x, y):
    return frame('10', byte_hex(x) + byte_hex(y))


def direction(value):
    return frame('15', f'{max(0, min(7, int(value))):02X}')


def set_speed(xy, z):
    xy = max(0, min(100, int(xy)))
    z = max(0, min(100, int(z)))
    return frame('16', f'{xy:02X}{z:02X}')


def button_frames(action, speed):
    """Calibrated for this X3: TYPE=10 for translation, TYPE=15 only for rotation."""
    speed = max(5, min(100, int(speed)))
    vectors = {
        'forward': (0, speed),
        'back': (0, -speed),
        'left': (-speed, 0),
        'right': (speed, 0),
    }
    if action in vectors:
        x, y = vectors[action]
        return [joystick(x, y)]
    if action == 'left_rotate':
        return [set_speed(speed, speed), direction(5)]
    if action == 'right_rotate':
        return [set_speed(speed, speed), direction(6)]
    return [joystick(0, 0), direction(7)]


class Backend:
    def __init__(self):
        self.sock = None
        self.lock = threading.RLock()
        self.connected = False
        self.last_command = time.monotonic()
        self.stop_event = threading.Event()
        threading.Thread(target=self.watchdog, daemon=True).start()

    def ensure(self):
        if self.sock:
            return True
        try:
            sock = socket.create_connection((BACKEND_HOST, BACKEND_PORT), 1.5)
            sock.settimeout(None)
            self.sock = sock
            self.connected = True
            print(f'[gateway] TCP connected {BACKEND_HOST}:{BACKEND_PORT}', flush=True)
            return True
        except OSError as exc:
            self.connected = False
            print(f'[gateway] TCP unavailable: {exc}', flush=True)
            return False

    def send(self, packet):
        with self.lock:
            if not self.ensure():
                return False
            try:
                self.sock.sendall(packet)
                self.last_command = time.monotonic()
                return True
            except OSError:
                self.close()
                return False

    def send_many(self, packets):
        ok = True
        for packet in packets:
            ok = self.send(packet) and ok
        return ok

    def safe_stop(self):
        self.send_many([joystick(0, 0), direction(7)])

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None
        self.connected = False

    def watchdog(self):
        while not self.stop_event.wait(.2):
            if self.sock and time.monotonic() - self.last_command > 1.2:
                self.safe_stop()
                self.last_command = time.monotonic()


BACKEND = Backend()


class CameraHub:
    def __init__(self):
        self.condition = threading.Condition()
        self.latest = None
        self.version = 0
        self.stop_event = threading.Event()
        threading.Thread(target=self.capture_loop, daemon=True).start()

    def capture_loop(self):
        if cv2 is None:
            print('[camera] cv2 unavailable', flush=True)
            return
        while not self.stop_event.is_set():
            cap = cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            if not cap.isOpened():
                print(f'[camera] cannot open {CAMERA_SOURCE}; retrying', flush=True)
                cap.release()
                self.stop_event.wait(3)
                continue
            print(f'[camera] opened {CAMERA_SOURCE} at {CAMERA_FPS} FPS', flush=True)
            while not self.stop_event.is_set():
                ok, image = cap.read()
                if not ok:
                    break
                ok, encoded = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if ok:
                    with self.condition:
                        self.latest = encoded.tobytes()
                        self.version += 1
                        self.condition.notify_all()
                self.stop_event.wait(1.0 / CAMERA_FPS)
            cap.release()

    def stream(self, handler):
        handler.send_response(200)
        handler.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        handler.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        handler.send_header('Connection', 'close')
        handler.end_headers()
        seen = -1
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.version != seen, timeout=3)
                    if self.latest is None or self.version == seen:
                        continue
                    data, seen = self.latest, self.version
                handler.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data + b'\r\n')
                handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


CAMERA = CameraHub()


def read_exact(sock, count):
    data = b''
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise ConnectionError('closed')
        data += part
    return data


def read_ws(sock):
    first, second = read_exact(sock, 2)
    opcode = first & 15
    length = second & 127
    if length == 126:
        length = struct.unpack('!H', read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack('!Q', read_exact(sock, 8))[0]
    mask = read_exact(sock, 4) if second & 128 else b''
    data = bytearray(read_exact(sock, length))
    if mask:
        for i in range(length):
            data[i] ^= mask[i % 4]
    return opcode, bytes(data)


def send_ws(sock, text):
    data = text.encode('utf-8')
    size = len(data)
    if size < 126:
        header = bytes((129, size))
    elif size < 65536:
        header = bytes((129, 126)) + struct.pack('!H', size)
    else:
        header = bytes((129, 127)) + struct.pack('!Q', size)
    sock.sendall(header + data)


def send_ws_control(sock, opcode):
    sock.sendall(bytes((128 | opcode, 0)))


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        print('[http] ' + fmt % args, flush=True)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/ws' and self.headers.get('Upgrade', '').lower() == 'websocket':
            return self.websocket()
        if path == '/camera.mjpeg':
            return CAMERA.stream(self)
        if path == '/api/status':
            return self.json_response({'ok': True, 'backend_connected': BACKEND.connected, 'camera_source': CAMERA_SOURCE, 'camera_fps': CAMERA_FPS})
        if path == '/api/yolo/latest':
            try:
                return self.json_response(json.loads((ARTIFACTS / 'detections.json').read_text(encoding='utf-8')))
            except Exception:
                return self.json_response({'ok': False, 'detections': []})
        if path.startswith('/artifacts/'):
            base, file = ARTIFACTS.resolve(), (ARTIFACTS / path[11:]).resolve()
        else:
            base, file = ROOT.resolve(), (ROOT / ('index.html' if path in ('', '/') else path[1:])).resolve()
        if (base not in file.parents and file != base) or not file.is_file():
            return self.send_error(404)
        data = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, value):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def websocket(self):
        key = self.headers.get('Sec-WebSocket-Key', '')
        accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept)
        self.end_headers()
        sock = self.connection
        sock.settimeout(15)
        send_ws(sock, json.dumps({'state': '已连接', 'backend': BACKEND.connected}, ensure_ascii=False))
        try:
            while True:
                try:
                    opcode, data = read_ws(sock)
                except socket.timeout:
                    send_ws_control(sock, 9)
                    continue
                if opcode == 8:
                    break
                if opcode == 9:
                    send_ws_control(sock, 10)
                    continue
                if opcode == 10:
                    continue
                if opcode != 1:
                    continue
                msg = json.loads(data.decode('utf-8'))
                kind = msg.get('type')
                if kind == 'joystick':
                    ok = BACKEND.send(joystick(msg.get('x', 0), msg.get('y', 0)))
                elif kind == 'button':
                    ok = BACKEND.send_many(button_frames(msg.get('action', 'stop'), msg.get('speed', 30)))
                elif kind == 'speed':
                    ok = BACKEND.send(set_speed(msg.get('xy', 30), msg.get('z', 30)))
                elif kind == 'stop':
                    ok = BACKEND.send_many([joystick(0, 0), direction(7)])
                elif kind == 'heartbeat':
                    ok = True
                else:
                    ok = False
                send_ws(sock, json.dumps({'state': '已发送' if ok else '小车 TCP 未连接', 'backend': BACKEND.connected}, ensure_ascii=False))
        except (ConnectionError, OSError, ValueError, json.JSONDecodeError):
            pass
        finally:
            BACKEND.safe_stop()


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('0.0.0.0', LISTEN_PORT), Handler)
    server.daemon_threads = True
    print(f'[gateway] http://0.0.0.0:{LISTEN_PORT} -> TCP {BACKEND_HOST}:{BACKEND_PORT}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        CAMERA.stop_event.set()
        BACKEND.stop_event.set()
        BACKEND.safe_stop()
        BACKEND.close()
        server.server_close()


if __name__ == '__main__':
    main()

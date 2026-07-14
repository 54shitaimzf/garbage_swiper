#!/usr/bin/env python3
"""Multi-client TCP proxy that sits in front of Rosmaster TCP:6000.

Accepts multiple simultaneous clients on :6001 and forwards all traffic
to/from the real Rosmaster on :6000.  This lets the APP and ROS2 bridge
both send commands concurrently.

Usage: python3 tcp_proxy.py [backend_host] [listen_port] [backend_port]
"""

import socket
import threading
import sys
import time


class MultiplexProxy:
    def __init__(self, backend_host="192.168.43.162", backend_port=6000,
                 listen_host="0.0.0.0", listen_port=6001):
        self.backend_host = backend_host
        self.backend_port = backend_port
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.clients = []
        self.lock = threading.Lock()
        self.backend = None
        self.backend_lock = threading.Lock()
        self.running = True

    def _connect_backend(self):
        if self.backend:
            try:
                self.backend.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.backend.close()
            self.backend = None

        attempt = 0
        while self.running:
            attempt += 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((self.backend_host, self.backend_port))
                s.settimeout(None)
                self.backend = s
                print(f"[proxy] connected to Rosmaster {self.backend_host}:{self.backend_port}")
                return True
            except Exception as e:
                wait = min(attempt * 2, 30)
                print(f"[proxy] backend connect attempt {attempt}: {e}, retry in {wait}s")
                time.sleep(wait)
        return False

    def _read_loop(self):
        buf = b""
        while self.running:
            try:
                data = self.backend.recv(4096)
                if not data:
                    print("[proxy] backend disconnected")
                    break
                buf += data
                while b"$" in buf and b"#" in buf:
                    start = buf.index(b"$")
                    end = buf.index(b"#", start) + 1
                    pkt = buf[start:end]
                    buf = buf[end:]
                    self._broadcast(pkt)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[proxy] backend read error: {e}")
                break

        if self.running:
            print("[proxy] backend lost, reconnecting...")
            time.sleep(1)
            if self._connect_backend():
                self._read_loop()

    def _broadcast(self, data):
        with self.lock:
            dead = []
            for client, addr in self.clients:
                try:
                    client.send(data)
                except Exception:
                    dead.append((client, addr))
            for pair in dead:
                self.clients.remove(pair)

    def _forward_from_client(self, client_sock, addr):
        try:
            while self.running:
                data = client_sock.recv(4096)
                if not data:
                    break
                with self.backend_lock:
                    if self.backend:
                        self.backend.send(data)
        except Exception as e:
            print(f"[proxy] client {addr} read error: {e}")
        finally:
            self._remove_client(client_sock, addr)

    def _remove_client(self, sock, addr):
        with self.lock:
            for c, a in self.clients:
                if c is sock:
                    self.clients.remove((c, a))
                    break
        try:
            sock.close()
        except Exception:
            pass
        print(f"[proxy] client {addr} disconnected ({len(self.clients)} remaining)")

    def run(self):
        if not self._connect_backend():
            print("[proxy] FATAL: cannot connect to Rosmaster")
            return 1

        threading.Thread(target=self._read_loop, daemon=True).start()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.listen_host, self.listen_port))
        server.listen(10)
        print(f"[proxy] listening on {self.listen_host}:{self.listen_port}")

        try:
            while self.running:
                client, addr = server.accept()
                print(f"[proxy] client {addr} connected ({len(self.clients)+1} total)")
                with self.lock:
                    self.clients.append((client, addr))
                threading.Thread(target=self._forward_from_client,
                                 args=(client, addr), daemon=True).start()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            server.close()
            if self.backend:
                self.backend.close()
        return 0


if __name__ == "__main__":
    backend_host = sys.argv[1] if len(sys.argv) > 1 else "192.168.43.162"
    listen_port = int(sys.argv[2]) if len(sys.argv) > 2 else 6001
    backend_port = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
    sys.exit(MultiplexProxy(
        backend_host=backend_host,
        listen_port=listen_port,
        backend_port=backend_port
    ).run())

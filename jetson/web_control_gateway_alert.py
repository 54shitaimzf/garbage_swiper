#!/usr/bin/env python3
"""Run the live gateway without visual boxes and with non-blocking audio alerts."""
import json
import math
import queue
import shutil
import struct
import subprocess
import threading
import time
import wave
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import web_control_gateway_overlay as gateway


ALERT_ENABLED = str(__import__('os').environ.get('ALERT_ENABLED', '1')).lower() in ('1', 'true', 'yes', 'on')
ALERT_DEFAULT_CONF = float(__import__('os').environ.get('ALERT_DEFAULT_CONF', '0.80'))
ALERT_COOLDOWN = max(0.5, float(__import__('os').environ.get('ALERT_COOLDOWN', '4.0')))
ALERT_CONFIRM_FRAMES = max(1, int(__import__('os').environ.get('ALERT_CONFIRM_FRAMES', '2')))
ALERT_AUDIO_DIR = Path(__import__('os').environ.get('ALERT_AUDIO_DIR', '/tmp/garbage_swiper_alerts'))
ALERT_SINK = __import__('os').environ.get('ALERT_SINK', '')
try:
    ALERT_THRESHOLDS = json.loads(__import__('os').environ.get('ALERT_THRESHOLDS_JSON', '{}'))
    if not isinstance(ALERT_THRESHOLDS, dict):
        ALERT_THRESHOLDS = {}
except (TypeError, ValueError, json.JSONDecodeError):
    ALERT_THRESHOLDS = {}


class AlertManager:
    """Generate short tones once and play them in a worker thread."""

    CLASS_PATTERNS = {
        'drink_green': (880, 1, 0.18),
        'drink_white': (660, 2, 0.14),
    }
    GENERIC_FREQUENCIES = (523, 659, 784, 988, 1175, 1319)

    def __init__(self):
        self.enabled = ALERT_ENABLED
        self.last_alert = {}
        self.streaks = {}
        self.last_event = None
        self.lock = threading.RLock()
        self.jobs = queue.Queue(maxsize=8)
        self.files = {}
        self.player = shutil.which('paplay') or shutil.which('aplay')
        self._prepare_audio()
        threading.Thread(target=self._worker, daemon=True).start()

    def _write_tone(self, path, frequency, repeats, duration):
        sample_rate = 16000
        gap = int(sample_rate * 0.07)
        samples = []
        for _ in range(repeats):
            count = int(sample_rate * duration)
            for i in range(count):
                envelope = min(1.0, i / max(1, int(sample_rate * 0.01)))
                envelope *= min(1.0, (count - i) / max(1, int(sample_rate * 0.02)))
                samples.append(int(7000 * envelope * math.sin(2 * math.pi * frequency * i / sample_rate)))
            samples.extend([0] * gap)
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(sample_rate)
            stream.writeframes(b''.join(struct.pack('<h', value) for value in samples))

    def _prepare_audio(self):
        if not self.enabled or not self.player:
            print(f'[alert] disabled or no player; enabled={self.enabled}; player={self.player}', flush=True)
            return
        try:
            ALERT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            for class_name, pattern in self.CLASS_PATTERNS.items():
                path = ALERT_AUDIO_DIR / f'{class_name}.wav'
                if not path.is_file():
                    self._write_tone(path, *pattern)
                self.files[class_name] = path
            for class_id, frequency in enumerate(self.GENERIC_FREQUENCIES):
                path = ALERT_AUDIO_DIR / f'class_{class_id}.wav'
                if not path.is_file():
                    self._write_tone(path, frequency, (class_id % 3) + 1, 0.13)
                self.files[str(class_id)] = path
            print(f'[alert] player={self.player}; default_conf={ALERT_DEFAULT_CONF:.2f}; confirm={ALERT_CONFIRM_FRAMES}; cooldown={ALERT_COOLDOWN:.1f}s', flush=True)
        except (OSError, ValueError, TypeError) as exc:
            self.player = None
            print(f'[alert] audio unavailable: {exc}', flush=True)

    @staticmethod
    def _key(item):
        name = str(item.get('class_name', '')).strip()
        return name or str(item.get('class_id', 'object'))

    @staticmethod
    def _confidence(item):
        try:
            return float(item.get('confidence', 0))
        except (TypeError, ValueError):
            return 0.0

    def _threshold(self, item):
        name = str(item.get('class_name', '')).strip()
        class_id = str(item.get('class_id', '')).strip()
        value = ALERT_THRESHOLDS.get(name, ALERT_THRESHOLDS.get(class_id, ALERT_DEFAULT_CONF))
        try:
            return float(value)
        except (TypeError, ValueError):
            return ALERT_DEFAULT_CONF

    def _sound_for(self, item):
        name = str(item.get('class_name', '')).strip()
        class_id = str(item.get('class_id', '')).strip()
        return self.files.get(name) or self.files.get(class_id)

    def process(self, detections):
        if not self.enabled or not self.player:
            return
        now = time.monotonic()
        for item in detections:
            confidence = self._confidence(item)
            key = self._key(item)
            if confidence < self._threshold(item):
                self.streaks[key] = 0
                continue
            self.streaks[key] = self.streaks.get(key, 0) + 1
            if self.streaks[key] < ALERT_CONFIRM_FRAMES:
                continue
            if now - self.last_alert.get(key, 0) < ALERT_COOLDOWN:
                continue
            sound = self._sound_for(item)
            if sound is None:
                continue
            self.last_alert[key] = now
            event = {'class_name': key, 'confidence': round(confidence, 4), 'timestamp': time.time()}
            with self.lock:
                self.last_event = event
            try:
                self.jobs.put_nowait((key, sound))
            except queue.Full:
                pass

    def _worker(self):
        while True:
            key, sound = self.jobs.get()
            try:
                if self.player == 'paplay':
                    command = ['paplay']
                    if ALERT_SINK:
                        command.extend(['--device', ALERT_SINK])
                    command.append(str(sound))
                else:
                    command = ['aplay', '-q', str(sound)]
                subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=False)
            except (OSError, subprocess.SubprocessError) as exc:
                print(f'[alert] play failed for {key}: {exc}', flush=True)
            finally:
                self.jobs.task_done()

    def test(self, class_name='drink_green'):
        if not self.enabled or not self.player:
            return {'ok': False, 'enabled': self.enabled, 'player': self.player}
        sound = self.files.get(class_name) or self.files.get('0')
        try:
            self.jobs.put_nowait((class_name, sound))
            return {'ok': True, 'class_name': class_name, 'player': self.player}
        except queue.Full:
            return {'ok': False, 'error': 'alert_queue_full'}

    def status(self):
        with self.lock:
            return {
                'enabled': self.enabled,
                'player': self.player,
                'default_confidence': ALERT_DEFAULT_CONF,
                'class_thresholds': ALERT_THRESHOLDS,
                'confirm_frames': ALERT_CONFIRM_FRAMES,
                'cooldown_seconds': ALERT_COOLDOWN,
                'last_event': self.last_event,
            }


ALERTS = AlertManager()


# The original gateway draws boxes into the JPEG. Replace that function before
# serving frames; detector results and /api/yolo/latest remain available.
gateway.overlay = lambda image, detections: image
original_infer = gateway.DETECTOR.infer


def infer_with_alert(image):
    detections = original_infer(image)
    ALERTS.process(detections)
    return detections


gateway.DETECTOR.infer = infer_with_alert
original_get = gateway.Handler.do_GET


def get_with_alert(self):
    parsed = urlparse(self.path)
    if parsed.path == '/api/alert/status':
        return self.json_response(ALERTS.status())
    if parsed.path == '/api/alert/test':
        class_name = parse_qs(parsed.query).get('class', ['drink_green'])[0]
        return self.json_response(ALERTS.test(class_name))
    return original_get(self)


gateway.Handler.do_GET = get_with_alert
gateway.main()

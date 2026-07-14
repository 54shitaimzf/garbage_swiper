#!/usr/bin/env python3
"""Live gateway without boxes, using the official Rosmaster buzzer protocol."""
import json
import queue
import threading
import time
from urllib.parse import parse_qs, urlparse

import web_control_gateway_overlay as gateway


import os
ALERT_ENABLED = os.environ.get('ALERT_ENABLED', '1').lower() in ('1', 'true', 'yes', 'on')
ALERT_DEFAULT_CONF = float(os.environ.get('ALERT_DEFAULT_CONF', '0.80'))
ALERT_COOLDOWN = max(0.5, float(os.environ.get('ALERT_COOLDOWN', '4.0')))
ALERT_CONFIRM_FRAMES = max(1, int(os.environ.get('ALERT_CONFIRM_FRAMES', '2')))
try:
    ALERT_THRESHOLDS = json.loads(os.environ.get('ALERT_THRESHOLDS_JSON', '{}'))
    if not isinstance(ALERT_THRESHOLDS, dict):
        ALERT_THRESHOLDS = {}
except (TypeError, ValueError, json.JSONDecodeError):
    ALERT_THRESHOLDS = {}


class BuzzerAlerts:
    """Class-specific, non-blocking alerts through official command 0x13."""

    # Each tuple is (state, delay_units), where delay_units * 10ms is the beep time.
    CLASS_PATTERNS = {
        'drink_green': ((1, 20),),
        'drink_white': ((1, 8), (1, 8)),
    }

    def __init__(self):
        self.enabled = ALERT_ENABLED
        self.cooldowns = {}
        self.streaks = {}
        self.last_event = None
        self.lock = threading.RLock()
        self.jobs = queue.Queue(maxsize=8)
        threading.Thread(target=self._worker, daemon=True).start()
        print(f'[alert] native Rosmaster buzzer; enabled={self.enabled}; default_conf={ALERT_DEFAULT_CONF:.2f}; confirm={ALERT_CONFIRM_FRAMES}; cooldown={ALERT_COOLDOWN:.1f}s', flush=True)

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

    def _pattern(self, class_name, class_id='0'):
        if class_name in self.CLASS_PATTERNS:
            return self.CLASS_PATTERNS[class_name]
        try:
            count = int(class_id) % 3 + 1
        except (TypeError, ValueError):
            count = 1
        return tuple((1, 6 + count * 2) for _ in range(count))

    def _enqueue(self, class_name, pattern, confidence=None):
        event = {'class_name': class_name, 'timestamp': time.time()}
        if confidence is not None:
            event['confidence'] = round(float(confidence), 4)
        with self.lock:
            self.last_event = event
        try:
            self.jobs.put_nowait((class_name, pattern))
        except queue.Full:
            pass

    def process(self, detections):
        if not self.enabled:
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
            if now - self.cooldowns.get(key, 0) < ALERT_COOLDOWN:
                continue
            self.cooldowns[key] = now
            self._enqueue(key, self._pattern(key, item.get('class_id', '0')), confidence)

    def _worker(self):
        while True:
            class_name, pattern = self.jobs.get()
            try:
                for state, delay_units in pattern:
                    # The official server parses command 0x13 as state + 10ms units.
                    packet = gateway.frame('13', f'{max(0, min(1, int(state))):02X}{max(0, min(255, int(delay_units))):02X}')
                    if not gateway.BACKEND.send(packet):
                        print(f'[alert] native buzzer backend unavailable for {class_name}', flush=True)
                        break
                    time.sleep(max(0.08, delay_units * 0.01 + 0.06))
            finally:
                self.jobs.task_done()

    def test(self, class_name='drink_green'):
        if not self.enabled:
            return {'ok': False, 'enabled': False, 'output': 'rosmaster_buzzer'}
        self._enqueue(class_name, self._pattern(class_name), None)
        return {'ok': True, 'class_name': class_name, 'output': 'rosmaster_buzzer'}

    def status(self):
        with self.lock:
            return {
                'enabled': self.enabled,
                'output': 'rosmaster_buzzer',
                'protocol': '0x13',
                'default_confidence': ALERT_DEFAULT_CONF,
                'class_thresholds': ALERT_THRESHOLDS,
                'confirm_frames': ALERT_CONFIRM_FRAMES,
                'cooldown_seconds': ALERT_COOLDOWN,
                'last_event': self.last_event,
            }


ALERTS = BuzzerAlerts()

# Preserve the live detection API but never draw model boxes into the camera JPEG.
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

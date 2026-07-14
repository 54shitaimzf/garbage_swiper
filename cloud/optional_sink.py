"""Non-blocking optional event sinks for local-first operation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


TOPICS = (
    "robot/status",
    "robot/battery",
    "inspection/event",
    "inspection/result",
    "mission/command",
)


class EventSink(Protocol):
    def publish(self, topic: str, payload: dict[str, Any]) -> None: ...

    def close(self) -> None: ...


class NullSink:
    """Default sink: explicitly accepts events but never opens a socket."""

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        if topic not in TOPICS:
            raise ValueError(f"unsupported topic: {topic}")

    def close(self) -> None:
        return None


@dataclass
class MqttSink:
    broker: str
    port: int = 1883
    robot_id: str = "icar-01"
    client: Any = None

    def __post_init__(self) -> None:
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError as exc:
            raise RuntimeError("paho-mqtt is required only when MQTT is enabled") from exc
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.robot_id)
        self.client.connect(self.broker, self.port, 30)
        self.client.loop_start()

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        if topic not in TOPICS:
            raise ValueError(f"unsupported topic: {topic}")
        result = self.client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=0, retain=False)
        if result.rc != 0:
            raise RuntimeError(f"MQTT publish failed: {result.rc}")

    def close(self) -> None:
        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()


def create_sink(enabled: bool | None = None) -> EventSink:
    enabled = (os.getenv("MQTT_ENABLED", "0") == "1") if enabled is None else enabled
    if not enabled:
        return NullSink()
    return MqttSink(
        broker=os.getenv("MQTT_BROKER", "127.0.0.1"),
        port=int(os.getenv("MQTT_PORT", "1883")),
        robot_id=os.getenv("ROBOT_ID", "icar-01"),
    )

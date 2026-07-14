#!/usr/bin/env python3
"""Small MQTT edge bridge skeleton; safe dry-run is the default."""
import argparse
import json
import os
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--robot-id", default=os.getenv("ROBOT_ID", "icar-01"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    topics = ["robot/status", "robot/battery", "inspection/event", "inspection/result", "mission/command"]
    print(json.dumps({"ok": True, "robot_id": args.robot_id, "broker": args.broker,
                      "port": args.port, "topics": topics, "dry_run": args.dry_run,
                      "timestamp": time.time()}, ensure_ascii=False))
    if args.dry_run:
        return
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise SystemExit("paho-mqtt is required for live mode; use --dry-run for smoke test") from exc
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.robot_id)
    client.connect(args.broker, args.port, 30)
    client.loop_forever()


if __name__ == "__main__":
    main()

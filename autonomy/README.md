# Additive autonomy gateway

This is a separate PWA and HTTP service for future ROS2/Nav2 tasks. It does
not modify or proxy the legacy manual gateway on port `8081`.

## Safe first run

```bash
AUTONOMY_MODE=mock python3 -m autonomy.server --host 0.0.0.0 --port 8082
```

Open `http://<car-ip>:8082/` from the phone. Mock mode never sends a motor,
camera, or serial command. It only verifies the API and UI state machine.

## Production constraints

- `maps.json` is the map whitelist. The API accepts IDs, not filesystem paths.
- Routes stay disabled until their waypoints are measured and safety-tested.
- `ros2` mode is intentionally fail-closed when ROS2/Nav2 is unavailable.
- The vendor serial and camera handoff is not performed by this service yet;
  it must be implemented and verified by a separate mode supervisor.
- Leave port `8081` and its existing process unchanged.

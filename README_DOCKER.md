# Docker setup for OffGas

This Docker setup is intentionally **additive**: it does not move the existing project folders and it does not modify `Bridge/bridge.py`.

## What stays where
- `Bridge/` remains the original bridge used on the host machine.
- `offgas_dashboard_linked/` remains the dashboard source folder.
- `dataset_other_garage/` remains the editable dataset folder.
- Docker-specific runtime files are stored under `docker/`.

## URLs
- Node-RED: http://127.0.0.1:1880/admin/#flow/120ca2f2695d22bc
- Dashboard: http://localhost:1880/offgas-dashboard/

## Start
On Windows:
- `scripts\up.bat`

On macOS/Linux:
- `./scripts/up.sh`

## Stop
On Windows:
- `scripts\down.bat`

On macOS/Linux:
- `./scripts/down.sh`

## Dashboard rebuild
If you modify `offgas_dashboard_linked/`, rebuild it before starting or restarting Docker:
- Windows: `scripts\rebuild-dashboard.bat`
- macOS/Linux: `./scripts/rebuild-dashboard.sh`

The Docker stack mounts `offgas_dashboard_linked/dist` directly into Node-RED static hosting, so no extra copy step is needed.

## Bridge
Run the original bridge from the existing `Bridge/` folder exactly as before.
No Bluetooth auto-detection wrapper is used here.

Because Docker publishes Mosquitto on host port `1883`, the bridge can continue to use:
- MQTT host: `127.0.0.1`
- MQTT port: `1883`

## Notes
- Docker Node-RED uses the runtime snapshot stored in `docker/nodered-data/`.
- That snapshot was created from the working local `.node-red` configuration and patched only for Docker-specific paths and MQTT broker host.
- The original project files are left in place.

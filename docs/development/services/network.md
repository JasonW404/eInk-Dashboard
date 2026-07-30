# `inkpi-network`

`inkpi-network` is the sole Raspberry Pi NetworkManager owner. InkPi Cloud
stores desired hotspot state and queues commands; the Pi polls Cloud over
HTTPS, executes only allowlisted operations, and reports actual hotspot state
and connected-client count.

This service is independent of `inkpi-display`. A Pi can therefore continue to
provide network/KVM duties when display ownership moves to an ESP32 device.

## Security and connectivity

- Authentication uses a dedicated `INKPI_NETWORK_TOKEN`, separate from display
  and HostAgent credentials.
- Commands are pulled outbound, so the Pi exposes no new inbound port.
- Hotspot passwords are never written to logs or command-line arguments.
- The Cloud database and Pi environment file are restricted to mode `0600`.

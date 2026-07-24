# User Manual

InkPi exposes its management interface at `http://<pi-address>:8080/` after the
Pi services are installed and running.

The Web application provides:

- an overview with the same 800×480 image consumed by the physical display;
- TODO management, ordering, completion, and eInk visibility controls;
- device and refresh status;
- hotspot settings and the Wi-Fi QR preview when the hotspot is active.

Use the [Installation and Deployment](deployment.md) guide to install InkPi on
the Raspberry Pi, configure protected environment files, and verify the three
device services.

The physical display refreshes independently from the browser. If the Web UI is
available but the panel does not update, check `inkpi-display.service` before
restarting the API.

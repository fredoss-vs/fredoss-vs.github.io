#!/bin/bash
wayfire &
sleep 10
WAYLAND_DISPLAY=wayland-1 chromium \
  --ozone-platform=wayland \
  --disable-gpu \
  --disable-gpu-compositing \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-pinch \
  http://localhost:8080

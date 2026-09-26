# ESP32 firmware

PlatformIO project (`framework = arduino`). Sketch entrypoint is
`src/thermostat.ino` — drop `thermostat.h` / `led_pulse.h` in `src/`
alongside it (flat layout, same as the old Arduino sketch folder).

Build/upload from VS Code with the PlatformIO extension's toolbar,
or from a terminal in this folder:

    pio run           # build
    pio run -t upload # build + flash
    pio device monitor

# Raspberry Pi Zero 2 W profile

The `pi0w` branch and `ghcr.io/chreece/linux-voice-assistant:pi0w` image are
for **Raspberry Pi Zero 2 W running a 64-bit OS** (`uname -m` reports
`aarch64`). The existing `pi02w` image tag remains a compatibility alias.
The original single-core Raspberry Pi Zero / Zero W uses ARMv6 and cannot
run this ARM64 image. A 32-bit OS on a Zero 2 W cannot run it either.

## What is different

- mpv's forward read-ahead limit is 8 MiB per player, instead of upstream's
  16 MiB, with 5 seconds of read-ahead instead of 20 seconds.
- mpv stays in idle mode between files; terminal and video handling are
  disabled.
- glibc allocator arenas are limited with `MALLOC_ARENA_MAX=2` to reduce
  per-thread heap fragmentation. An explicit container environment value
  can override this limit.
- The image retains upstream's multi-stage build, which leaves compilers
  and development packages out of the runtime, and also omits `vim`.
- The image is published for `linux/arm64`; no compilation is required on
  the Pi when updating it.

The 0.8-second audio buffer, upstream playback-completion drain handling,
and `audio-stream-silence` remain enabled. The last setting supplies silence
while a file is loaded; it does **not** keep a PulseAudio/PipeWire stream
open after the file ends. Keeping mpv in idle mode does not change that.

These are resource limits, not a guaranteed latency improvement. The
microphone pipeline, wake-word detection, 1024-sample input block size,
media playback, and stop-word behavior are retained. Hardware latency and
memory consumption need to be measured on the satellite.

## Runtime settings

- Keep one active wake word when possible.
- Use `AUDIO_INPUT_CHANNELS=1` unless the microphone requires more channels,
  such as a reference channel for acoustic echo cancellation.
- If the microphone board already performs DSP/noise suppression, leave
  LVA software AGC/noise suppression disabled to avoid duplicate CPU work.
  Keep these features enabled when the microphone needs them.
- Keep debug logging off during normal operation.

These settings are recommendations; the image does not overwrite stored
Home Assistant preferences or force mono input.

## Updating

Point the satellite's Compose service and its permission-fixing service at
the same `ghcr.io/chreece/linux-voice-assistant:pi0w` image. Both tags remain
moving tags, so an existing `pi02w` deployment can also continue pulling
updates.

Download the published image with `docker compose pull`. To replace the
running containers with it, use `docker compose up -d`. The combined
command is `docker compose up -d --pull always`.

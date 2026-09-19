# Raspberry Pi Zero 2 W profile

This branch is intentionally separate from `main` and is aimed at 64-bit
Raspberry Pi Zero 2 W satellites.

## What is different

- libmpv is kept in idle mode so it stays resident between short sounds.
- mpv terminal and video handling are disabled.
- mpv cache is reduced from 32 MiB / 20 s to 8 MiB / 5 s.
- `audio-stream-silence` remains enabled so PulseAudio/PipeWire stays warm.
- glibc allocator arenas are limited with `MALLOC_ARENA_MAX=2`.
- the image is built only for `linux/arm64` and published as:
  `ghcr.io/chreece/linux-voice-assistant:pi02w`.

These changes target the long-idle wake-sound delay and memory pressure seen on
512 MB Pi Zero 2 W systems without changing wake-word detection or the
1024-sample input block size.

## Recommended runtime settings

For the smoothest Pi Zero 2 W experience:

- keep one active wake word when possible;
- use `AUDIO_INPUT_CHANNELS=1` unless a second channel is required for AEC;
- if the microphone board already performs DSP/noise suppression, leave LVA
  software AGC/noise suppression disabled to avoid duplicate CPU work;
- keep debug logging off for normal operation.

Do not force these settings when the hardware needs them. In particular,
software noise suppression can still be useful with simpler microphone boards.

# Mic + System Audio Mixing Feature Plan

## Goal
Add an optional mode that mixes system audio (WASAPI loopback) with a microphone capture stream and feeds the mixed audio into the existing transcription pipeline. Default behavior stays loopback-only.

## UX and Config
- Config (new):
  - `audio.mix_mic` (bool, default false) — enable mic+loopback mixing.
  - `audio.mic_device` (string|null) — microphone name/id; null selects the default capture device.
  - `audio.mic_gain` (float, default 1.0) — gain applied to mic before mixing.
  - `audio.loopback_gain` (float, default 1.0) — gain applied to loopback before mixing.
- Behavior:
  - If the mic is missing/unopenable, log a warning and fall back to loopback-only (never hard-fail recording).
  - Device selection mirrors current default-speaker logic for picking a default mic when `mic_device` is unset.
- CLI:
  - Add `--mix-mic`, `--mic-device "<name>"`; extend `list-devices` to show playback+capture devices and indicate defaults.
- GUI:
  - Toggle “Include microphone”; dropdown for mic device; status/log shows selected playback device, mic device (or default), gains, and whether mixing is active. No per-source meters.

## Technical Approach
- Device discovery:
  - Extend device enumeration to include capture devices and identify the default mic.
  - Match `mic_device` by case-insensitive exact name; if not found, log and fall back to default mic.
- Stream setup:
  - Keep existing loopback stream for playback device.
  - Open mic stream from selected/default capture device.
  - If sample rate/channels differ, resample/convert mic to loopback format before mixing (prefer float32 path).
- Mixing:
  - Convert both sources to float32.
  - Apply per-source gains (`loopback_gain`, `mic_gain`).
  - Align by trimming to the shorter buffer per chunk to avoid drift.
  - Mix via normalized sum (e.g., average or divide by max amplitude) to avoid clipping.
- Queue integration:
  - Keep a single recording thread; mix inline in `record_loop()` and enqueue mixed frames to the existing queue so `Transcriber.process_audio()` stays unchanged.
- Fallbacks:
  - On mic open/enumeration/resample failure, log a warning and continue with loopback-only.
  - Keep recording alive; note fallback in CLI/GUI logs.
- Logging:
  - Chosen playback device and mic device (and whether default was used).
  - Gains in effect.
  - Any fallback to loopback-only and the reason.

## Expected Code Touchpoints
- `src/scribe/utils/config.py`: add defaults, validation, and getters for `mix_mic`, `mic_device`, gains.
- `src/scribe/core/recorder.py`: device enumeration for capture devices; default mic selection; mic stream open/resample; mix with loopback; enqueue mixed frames; fallback handling; logging.
- `src/scribe/cli.py`: CLI flags and `list-devices` output updates.
- `src/scribe/gui/app_pro.py`: toggle/dropdown wiring; status/log updates for device choices and mix state.
- Docs/version: `README.md`, `AGENTS.md`, `pyproject.toml` version bump when feature ships.

## Risks and Mitigations
- Sample rate/channel mismatch: resample mic to loopback format.
- Latency/drift: use consistent small buffers; align on min length per chunk; monitor drift via debug logs.
- Clipping: per-source gain plus normalized mix to keep headroom.
- Device permission/availability: degrade to loopback-only with clear log messaging.

## Implementation Steps
1) Config: add new fields/defaults and accessors.
2) Device discovery: capture device enumeration, default mic detection, CLI `list-devices` update.
3) Recorder: open mic stream alongside loopback; resample if needed; apply gains; mix and enqueue; fallback on mic failure.
4) CLI/GUI: add mix toggle and mic selection; surface device choices/mix state in logs/status.
5) Logging: ensure clear messages for selected devices, gains, and fallbacks.
6) Docs/version: document usage/config; update AGENTS with lesson; bump version when merged.
7) Sanity checks: import test; short recording smoke test covering mixed and fallback paths.

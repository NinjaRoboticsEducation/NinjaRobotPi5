# Phase 0 baseline report

- Date: 2026-07-25
- Historical source: `Nilcreator/NinjaClawBot`
- Historical branch: `clawbotV3_01`
- Historical commit: `1aa6700d403dff65d2a53ad6fda9718b60723cb7`
- Physical hardware accessed: No

## Original imported source trees

| Driver | Historical Git tree |
| --- | --- |
| `pi5buzzer` | `ea5c5fbd7616efbc901739e8a491189832350dae` |
| `pi5servo` | `50885fefa98ed0247398fe94cdad84fbf361df8c` |
| `pi5disp` | `ab24de90cfdb4410b51071c596c5b1c4ba6a9749` |
| `pi5camera` | `c273265cc542252b3ad4b271bd3d6083adabbebc` |
| `pi5mic` | `3cd8bd1cbb98127fb4b9b10fb49aac1b03c3cc68` |
| `pi5vl53l0x` | `85ca66166a298d434df31d392b0e7ebd204a985b` |

The file-level SHA-256 manifest is stored in
`immutable_driver_baseline.json` and verified by
`scripts/verify_immutable_drivers.py`.

This report records the unmodified import state. On 2026-07-25 the project
owner later authorized focused repairs to the copied standalone libraries.
Approved repaired hashes are stored separately in
`authorized_driver_changes.json`; this original baseline is never regenerated.

## Package contract inventory

| Package | Metadata version | Primary public surface | CLI | Tests |
| --- | --- | --- | --- | ---: |
| `pi5buzzer` | 0.1.0 | `Buzzer`, `MusicBuzzer` | `pi5buzzer` | 65 |
| `pi5servo` | 1.0.0 (`__version__` is 0.1.0) | `Servo`, `ServoGroup`, calibration and parsing APIs | `pi5servo` | 132 |
| `pi5disp` | 0.1.0 | `ST7789V`, `ConfigManager` | `pi5disp` | 63 |
| `pi5camera` | 0.2.0 | lazy capture, enrollment, recognition, and face-store APIs | `pi5camera` | 23 |
| `pi5mic` | 0.1.0 | device, recording, listener, VAD, wake-word, and STT APIs | `pi5mic` | 90 |
| `pi5vl53l0x` | 0.1.0 | `VL53L0X` | `pi5vl53l0x` | 62 |

Inherited assets include `pi5disp/display.json` and
`pi5disp/src/pi5disp/fonts/NotoSans-Regular.ttf`. OpenClaw-specific modules
inside `pi5mic` remain on disk but are not approved V4 runtime dependencies.

## Validation results

### Root governance gate

| Check | Result |
| --- | --- |
| Immutable manifest verification | PASS — 221 files across 6 drivers |
| V4-owned script compilation | PASS |
| Ruff check for `scripts` and `tests` | PASS |
| Ruff format check for `scripts` and `tests` | PASS — 2 files |
| Root pytest | PASS — 3 tests |
| `git diff --check` | PASS |

### Copied-driver baseline

| Package | Tests | Native Ruff check | Native Ruff format |
| --- | ---: | --- | --- |
| `pi5buzzer` | 65 passed | PASS | PASS — 12 files |
| `pi5servo` | 132 passed | PASS | PASS — 38 files |
| `pi5disp` | 63 passed | PASS | PASS — 25 files |
| `pi5vl53l0x` | 62 passed | PASS | PASS — 12 files |
| `pi5camera` | 23 passed | PASS | PASS — 37 files |
| `pi5mic` | 90 passed | PASS | PASS — 64 files |
| **Total** | **435 passed** | **PASS** | **PASS — 188 files** |

`pi5mic` emitted one inherited warning: Python reports that `audioop` is
deprecated and scheduled for removal in Python 3.13. The package already
declares `audioop-lts` for Python 3.13 and remains immutable.

The copied packages were tested in isolated Python 3.11 environments. Frozen
mode protected inherited lockfiles; `pi5buzzer`, which has no tracked lockfile,
was tested without uv project discovery. Ruff 0.15.5 is pinned at the V4 root
because it is the validated historical tool version. No physical device was
accessed.

## 2026-07-26 exit reconciliation

The original import inventory above remains historical evidence. Before closing
Phase 0, the currently authorized managed-driver state was revalidated without
editing any driver:

| Check | Result |
| --- | --- |
| Immutable manifest verification | PASS — 222 files and 23 authorized repairs |
| Root governance | PASS — 7 tests |
| `pi5buzzer` | PASS — 65 tests |
| `pi5servo` | PASS — 134 tests |
| `pi5disp` | PASS — 65 tests |
| `pi5camera` | PASS — 24 tests |
| `pi5mic` | PASS — 90 tests, one inherited `audioop` warning |
| `pi5vl53l0x` | PASS — 71 tests |
| Current package-test total | PASS — 447 tests |
| Ruff lint and formatting | PASS for root and every managed library |
| Compilation and `git diff --check` | PASS |

The project owner also confirmed the current V4 wiring: servos on GPIO12 and
GPIO13, passive buzzer on GPIO27, and the 240×320 ST7789V display using DC
GPIO4, reset GPIO5, backlight GPIO6, rotation 90°, and brightness 75%. These
values are V4-owned configuration and do not modify driver-local defaults.

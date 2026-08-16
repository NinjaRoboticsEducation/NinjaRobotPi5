# Third-Party Notices

NinjaRobotPi5 is distributed under the root MIT license. Runtime dependencies
and optional services retain their own licenses and terms. This notice is an
engineering inventory, not a replacement for the license files shipped by
those projects.

## Phase 8 voice and remote-access dependencies

| Component | Purpose | License or terms | Source |
|---|---|---|---|
| openWakeWord | Local wake-phrase inference | Apache-2.0 for code; separately distributed upstream pretrained models may use CC BY-NC-SA 4.0 | <https://github.com/dscripka/openWakeWord> |
| ONNX Runtime | Executes the approved ONNX wake model | MIT | <https://github.com/microsoft/onnxruntime> |
| pyngrok | Python lifecycle wrapper for the ngrok agent | MIT | <https://github.com/alexdlaird/pyngrok> |
| ngrok agent/service | Optional remote HTTPS tunnel | ngrok terms of service and account limits; not covered by the NinjaRobotPi5 MIT license | <https://ngrok.com/docs/agent> |
| python-qrcode | Generates onboarding QR images | BSD-3-Clause | <https://github.com/lincolnloop/python-qrcode> |
| cryptography | Local CA, certificate, and cryptographic primitives | Apache-2.0 OR BSD-3-Clause | <https://github.com/pyca/cryptography> |
| FastAPI / Starlette | Local HTTPS application and WebSocket boundary | MIT / BSD-3-Clause | <https://github.com/fastapi/fastapi> |
| Uvicorn | Local ASGI HTTPS server | BSD-3-Clause | <https://github.com/encode/uvicorn> |
| HTTPX | Bounded cloud-provider HTTP client | BSD-3-Clause | <https://github.com/encode/httpx> |
| Pydantic | Strict runtime and configuration contracts | MIT | <https://github.com/pydantic/pydantic> |
| jsonschema | MCP/config schema validation | MIT | <https://github.com/python-jsonschema/jsonschema> |
| MCP Python SDK | Model Context Protocol client contracts | MIT | <https://github.com/modelcontextprotocol/python-sdk> |
| Pillow | Face, camera, and QR image processing | HPND | <https://github.com/python-pillow/Pillow> |
| Click | IDE command-line interface | BSD-3-Clause | <https://github.com/pallets/click> |
| Blessed | Terminal interactive interface | MIT | <https://github.com/jquast/blessed> |

## Installation toolchain

The optional Raspberry Pi installer retrieves these projects from their
official upstream distribution points. Reviewed versions or commits are pinned
in `scripts/install-versions.env`; each project retains its own terms.

| Component | Purpose | License or terms | Source |
|---|---|---|---|
| uv | Python/runtime and locked dependency management | Apache-2.0 OR MIT | <https://github.com/astral-sh/uv> |
| Ollama | Local model runtime; downloaded models retain their own licenses | MIT for the runtime; model-specific terms | <https://github.com/ollama/ollama> |
| whisper.cpp | Local speech-to-text runtime | MIT | <https://github.com/ggml-org/whisper.cpp> |

`uv.lock` is the exact transitive Python dependency inventory for this release.
Each installed distribution retains its own license metadata and files. The
table above covers all direct Phase 8 agent/IDE dependencies; the managed
driver projects retain their own lockfiles and license records.

The release process must retain the license metadata installed with every
Python distribution and must review the final locked dependency set before
publishing a release artifact.

The packaged `melspectrogram.onnx` and `embedding_model.onnx` runtime assets
come from the openWakeWord v0.5.1 release and retain the Apache License 2.0
terms. The packaged `silero_vad.onnx` asset retains the Silero project's MIT
terms. Exact source, hashes, and sizes are recorded in
`docs/validation/phase-8-openwakeword-assets.json`.

## Approved NinjaRobot wake model

`ninjarobot_pi5_ide/assets/hey_Ninja.onnx` is a custom model supplied and
approved by the NinjaRobotPi5 project owner for redistribution with this
project under the root MIT license. It is not represented as one of
openWakeWord's bundled pretrained models.

- Wake phrase: **Hey Ninja**
- Size: 206,276 bytes
- SHA-256: `12c87f97ea41b08a356631dc1162af455aa30ac27ff6235963a31d0f5e39016a`
- Approval date: 2026-08-13

The model must not be replaced merely because another file has the same name.
Any replacement requires a new provenance record, checksum, license review,
false-trigger test set, Raspberry Pi validation result, and owner approval.

## Managed hardware libraries

The six managed `pi5*` libraries retain the license files in their respective
root directories. Their immutable import hashes and authorized repairs remain
governed by `docs/validation/immutable_driver_baseline.json` and
`docs/validation/authorized_driver_changes.json`.

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
| Zstandard (zstd) | OS decompression tool required by the pinned Ollama installer | BSD-3-Clause OR GPL-2.0 | <https://github.com/facebook/zstd> |

The F05 refinement records exact installer-script and base speech-model hashes in
`scripts/install-versions.env`. Source evidence and limits are recorded in
[the installer provenance review](docs/validation/refinement_installer_provenance_260908.md).
This is not a claim that all OS packages or downstream binary downloads are pinned
by this repository.

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

## Local developer wiki

The bundled [LLMWikiTemplate](ninjarobot_pi5_wiki/README.md), package version
0.2.1, is distributed under its [MIT license](ninjarobot_pi5_wiki/LICENSE),
copyright 2026 Ninja Robotics Educations. Its separate dependency inventory and
locked versions are in `ninjarobot_pi5_wiki/pyproject.toml` and `uv.lock` in that
folder. These development dependencies are not added to the robot runtime.

The repository knowledge-validation workflow uses the MIT-licensed
[actions/checkout](https://github.com/actions/checkout) and
[astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) actions, pinned to
full source revisions in `.github/workflows/wiki-validation.yml`. The uv executable
is pinned to 0.12.5, matching the local validation environment. No runtime service
or robot dependency was added.

## Refinement Phase 3: optional local speech

Piper is an external, opt-in executable in a separate environment. It is not
vendored into the robot packages or installed by the normal robot startup.
The root MIT license does not replace the following component licenses.

| Component | Purpose | License/provenance |
| --- | --- | --- |
| Piper TTS 1.8.0 | Local speech generation | GPL-3.0-or-later; [upstream source](https://github.com/OHF-Voice/piper1-gpl/tree/v1.8.0), [package metadata](https://pypi.org/project/piper-tts/1.8.0/). |
| ONNX Runtime, NumPy, FlatBuffers, packaging, pathvalidate, protobuf | Piper's isolated dependencies | Respect each installed distribution's license files: respectively MIT, BSD-3-Clause, Apache-2.0, Apache-2.0/BSD-2-Clause, MIT, BSD-3-Clause. Versions and hashes are in [local-speech.txt](requirements/local-speech.txt). |
| en_US-ljspeech-high | Optional 114 MB English voice | Model card identifies the LJ Speech dataset as public domain. Retain [the upstream card](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/en/en_US/ljspeech/high/MODEL_CARD) and review it for your distribution. |
| PipeWire / WirePlumber | OS-owned audio routing and Bluetooth session management | External OS components, MIT; not bundled or reconfigured by this feature. [PipeWire source](https://gitlab.freedesktop.org/pipewire/pipewire), [WirePlumber source](https://gitlab.freedesktop.org/pipewire/wireplumber). |

The optional engine requirements were resolved for Python 3.11, Linux ARM64, with
all transitive versions and content hashes pinned. The voice helper pins upstream
revision `1162a9173d0ce503555aed757976b7a9912eae4c` and separately verifies the model,
configuration and model-card hashes before publishing downloaded files. Existing
files are not overwritten. The source revision is not a promise of future upstream
availability. No engine or model download was executed during implementation.

Mandarin capability accepts an operator-supplied compatible Piper model. The
[Huayan upstream card](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/zh/zh_CN/huayan/medium/MODEL_CARD)
labels its dataset license unknown; no Chinese model is bundled, automatically
installed, or represented as cleared for redistribution. Japanese speech is not
implemented. Speech synthesis is local; the chosen conversation provider retains
its separate data-handling terms and charges.

# Installer source review — 8 September 2026

This record supports F05. No installer was executed, no model was downloaded,
and no live system or boot configuration changed during the review.

## Reviewed inputs

The active values live in `scripts/install-versions.env`. The installer checks
the following SHA-256 values (content fingerprints) before using a downloaded
script or speech model. Existing speech-model files are checked too; a mismatch
fails without replacing the operator's file.

| Input | Fixed upstream source | SHA-256 |
| --- | --- | --- |
| uv installer 0.12.5 | [Official versioned installer](https://astral.sh/uv/0.12.5/install.sh) | `504511fbbbd811aeaba6738abc79408956b6c7da0ca35437b3dcc24a41efc111` |
| Ollama installer for v0.32.5 | [Official script at commit eec8e0b9458b8a01be0c216a9cc53eefde24ef50](https://raw.githubusercontent.com/ollama/ollama/eec8e0b9458b8a01be0c216a9cc53eefde24ef50/scripts/install.sh) | `25f64b810b947145095956533e1bdf56eacea2673c55a7e586be4515fc882c9f` |
| Multilingual base Whisper model, 147,951,465 bytes | [Upstream model at revision 5359861c739e955e79d9a303bcbc70fb988958b1](https://huggingface.co/ggerganov/whisper.cpp/blob/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.bin) | `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe` |

The two installer hashes were calculated from retrieved script bytes. The model
hash and size came from the upstream large-file metadata at that fixed revision;
the model itself was not downloaded for this review. Ollama's tag was resolved to
the listed commit, and the commit-addressed script matched the recorded hash.

The uv script selects version 0.12.5 artifacts and supports the existing option
that avoids changing shell PATH. The Ollama script requires privilege, replaces
its own runtime files, downloads the selected version and configures its own
service. These remain part of the explicit hardware installation path, never
tests or the development profile. The script requires `zstd` for newer compressed
archives, so it was added to the existing OS package list. The fixed whisper.cpp
source commit remains unchanged.

## Limits and maintenance

These checks protect the recorded installer and model bytes. They do not make
the entire operating system reproducible: OS packages, binaries downloaded by
upstream installers, uv download overrides and the optional ngrok agent retain
their existing upstream distribution contracts. Do not describe this as a fully
verified system image. Replacing the whole installation/update mechanism remains
outside this refinement. No new Python dependency was added.

A future version update must review the upstream source, license and actual
artifact, change its fixed version/revision and hash together, and run installer
preview and checksum-failure tests. Never replace a hash merely to silence a
failure. See the existing root third-party notice for upstream licenses; uv,
Ollama and whisper.cpp remain under their upstream licenses and zstd uses its
upstream BSD/GPL licensing alternatives.

## Safe validation

Run the installer's hardware and development previews. Run the doctor with the
chosen interpreter. Fixture tests verify that an incorrect hash refuses the file
without modifying it and that the development profile targets `.venv-dev`, leaving
the `.venv` sentinel unchanged. No communication, movement, capture or power test
is required for these checks. A later real installation still requires review of
its privileged operations and retention of existing configuration/backups.

# Known Limits and Compatibility

This first release keeps the canonical system deliberately small.

- Search is deterministic token-based keyword search with conversational stop-word filtering, minimum term coverage, and a small explicit equivalence list for common engineering terms such as wiring/connection and diagram/pinout. There is no embedding service or semantic index, so vocabulary outside that reviewed list may still require a second query.
- Built-in normalization covers UTF-8 Markdown, text, HTML, text-bearing PDFs, and single-frame PNG/JPEG images. Image metadata and sanitized renditions use Pillow. Optional image OCR requires a separately installed Tesseract 5 executable and language data.
- OCR can miss, reorder, or invent characters. Visual understanding depends on an image-capable coding-tool session or a human description. The workflow must not infer layout or appearance when it cannot view the image.
- Scanned PDFs, SVG, animated images, TIFF, HEIC, audio, video, archives, and office documents are not ingested yet.
- Markdown link parsing covers the template's standard link form, not every extension supported by every Markdown renderer.
- Structural lint can prove that references and citations are connected. The optional page-level semantic review improves source-support, contradiction, limitation, claim-strength, and visual-evidence checking, but an AI review still cannot prove objective truth.
- Trust changes, merges, deprecations, and prose edits still need human judgment and an approved plan.
- Atomic replacement depends on the staging folder and `wiki/` remaining on the same filesystem. A recoverable full-bundle backup is retained after each successful plan.
- Publishing and remote-model privacy decisions are outside this local template. Nothing is published automatically.
- Source-version lint is offline. It detects local hash and revision mismatches, but it cannot discover a changed remote website until the local snapshot is refreshed.

The local suite was validated on macOS with CPython 3.13 and uv 0.11 on 2026-08-22. GitHub Actions is configured to exercise Python 3.11 and 3.13 on Linux, macOS, and Windows; those remote jobs begin running once this folder is placed in a GitHub repository.

Antigravity compatibility targets its current `.agents/rules/`, `.agents/workflows/`, and `.agents/skills/` workspace conventions as checked on 2026-08-22. Antigravity's UI controls whether a workspace rule is Always On, manually selected, model-selected, or glob-selected; the template does not silently change the user's editor settings.

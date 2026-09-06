# Using the Wiki with Google Antigravity

Google Antigravity can use the same canonical skills as Codex. The template adds one workspace rule and five optional slash-command workflows so the wiki functions are easy to discover in Antigravity IDE.

## Open the project

1. Open Antigravity IDE.
2. Add this repository folder as an Antigravity workspace or project folder.
3. Open a terminal in the repository and run:

   ```bash
   uv sync --all-extras
   uv run llmwiki doctor
   uv run llmwiki lint
   ```

4. Open **Customizations → Rules** and confirm that `.agents/rules/llm-wiki.md` is available. Set it to **Always On** if Antigravity has not already activated it for the workspace.

The rule points to `AGENTS.md`, so Antigravity receives the same safety and content rules as the other supported tools. Do not copy those rules into a global `GEMINI.md`; they are specific to this wiki.

## Run a wiki function

Type `/` in the Antigravity agent panel and select a workflow:

| Command | Purpose |
|---|---|
| `/wiki-ingest` | Register or reprocess evidence and prepare a reviewed change plan |
| `/wiki-query` | Answer from existing wiki evidence without writing files |
| `/wiki-lint` | Check OKF structure, links, citations, sources, and indexes |
| `/wiki-review` | Review one page for source support, contradictions, limitations, claim strength, and visual evidence |
| `/wiki-maintain` | Refresh, rename, merge, deprecate, or rebuild safely |

For image sources, `/wiki-ingest` uses the same safe registration, optional OCR, source-hash, and reviewed asset workflow as every other editor. Antigravity should visually inspect an image only when the current session exposes that capability. Otherwise it must report the limitation and avoid guessing layout or appearance.

Example:

```text
/wiki-ingest Discover the new text and PNG/JPEG sources under raw/. Normalize them, report OCR and visual-access limitations, prepare version 2 plans with every source hash and sanitized asset summary, and stop before apply.
```

You can add the subject after the command in the same prompt. For example:

```text
/wiki-ingest raw/articles/example.md
```

```text
/wiki-query What does this wiki say about the main topic?
```

Antigravity also discovers the five skill packages directly from `.agents/skills/`. A normal-language request such as “check the health of this wiki” can therefore select `wiki-lint` without a slash command.

For lightweight semantic review, keep the task to one page:

```text
/wiki-review Review wiki/concepts/example.md against its cited sources. Check support, contradictions, limitations, claim strength, and visual evidence. Use concern or incomplete instead of guessing, and show any plan before apply.
```

Normal `/wiki-lint` keeps semantic gaps as warnings, including gaps on sourced drafts. Ask it to run `uv run llmwiki lint --strict` only when you want the higher-confidence release gate for every sourced page. Use `uv run llmwiki stats` to see review coverage without asking Antigravity to review the whole wiki at once.

## Review and permissions

Use Antigravity's review-driven mode for this repository. Its interface may show an implementation plan or code diff, but that is separate from the wiki's own `.llmwiki/plans/` contract. Semantic wiki edits still need a valid `llmwiki plan diff` and explicit approval before `llmwiki plan apply --approve`.

Do not grant broad global permissions just to use the template. The normal commands operate inside the project. Keep web browsing, external actions, and commands outside the workspace set to ask unless you intentionally need them.

## Troubleshooting discovery

- Reopen the workspace after adding or changing skills and workflows.
- Confirm that the workspace root is the folder containing `llmwiki.yaml`.
- Check that `.agents/rules/`, `.agents/workflows/`, and `.agents/skills/` are visible in the file tree.
- Run `uv run llmwiki doctor` if the slash workflow finds the files but cannot run the CLI.
- Antigravity still supports the older singular `.agent/` path, but this template uses the current `.agents/` location only.

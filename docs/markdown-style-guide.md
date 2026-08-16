# NinjaRobotPi5 documentation style guide

Use this guide for public and developer-facing Markdown in this repository.
Prioritize plain language, short sections, and instructions that can be followed
without prior robotics experience.

## Document structure

1. Start with one `#` title.
2. Follow with a short purpose statement.
3. Add a compact contents list only for long documents.
4. Organize tasks under descriptive `##` and `###` headings.
5. End procedural documents with validation and troubleshooting links.

## Formatting rules

- Leave one blank line around headings, lists, tables, quotes, and code blocks.
- Use sentence case for headings.
- Use numbered lists for ordered procedures and bullets for unordered choices.
- Put commands in fenced `bash` blocks and configuration in the matching
  language block, such as `toml`, `json`, or `ini`.
- Introduce every command with its purpose and state the expected result.
- Use tables only when readers need to compare several exact fields.
- Prefer repository-relative links and meaningful link text.
- Wrap filenames, commands, configuration keys, pins, and literal values in
  backticks.
- Use GitHub alerts sparingly: `NOTE`, `TIP`, `IMPORTANT`, `WARNING`, and
  `CAUTION`.
- Do not use raw HTML for normal layout or decorative emoji in headings.
- Keep lines reasonably short when editing, without reflowing URLs or tables.

## Beginner instructions

- Define an acronym or hardware term the first time it appears.
- State where a command must be run.
- Separate commands that change the OS from commands that only inspect it.
- Mark actuator, camera, microphone, network-exposure, and power risks before
  the risky step.
- Never include a real API key, token, password, private path, or captured media.
- Give a safe rollback or retry step for operations that edit system files.

## Example

### Check the installation

From the repository root, run the installer in read-only check mode:

```bash
./install.sh --check
```

Expected result: each prerequisite is reported as ready. A failed check includes
the corrective next step and does not change the Raspberry Pi.

# Gemini free-tier and tool-calling stability implementation plan

Make Google Gemini (`gemini-3.8-flash`, `gemini-3.5-flash`, and related models)
reliable during conversational and tool-calling turns on NinjaRobotPi5 by
handling Google AI Studio Prepay `HTTP 402` errors clearly, retrying transient
`HTTP 503` capacity spikes with paced backoff, avoiding redundant clock tool
round-trips, and completing turns gracefully when a post-tool summarization
request fails.

Date: 14 November 2026. Status: researched implementation proposal. No runtime
code changes or hardware acceptance tests have been performed yet.

## Contents

- [Scope and acceptance contract](#scope-and-acceptance-contract)
- [Evidence and root-cause findings](#evidence-and-root-cause-findings)
- [Target tool-calling workflow](#target-tool-calling-workflow)
- [Phased implementation plan](#phased-implementation-plan)
- [Validation commands](#validation-commands)
- [Manual Raspberry Pi 5 acceptance](#manual-raspberry-pi-5-acceptance)
- [Documentation and rollback](#documentation-and-rollback)

## Scope and acceptance contract

Implement all changes inside `ninjarobot_pi5_agent` and project documentation
while preserving the mandatory hardware boundary:

```text
user/model -> ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5* driver -> device
```

1. `ninjarobot_pi5_agent` continues to translate provider-neutral `ModelRequest`
   and `ModelTurn` objects without importing any `pi5*` library or accessing
   GPIO, I2C, SPI, PWM, camera, microphone, serial, or power interfaces.
2. When Google returns `HTTP 402` (`Payment Required` / `RESOURCE_EXHAUSTED`),
   `checked_json()` in `cloud_common.py` raises a non-retried
   `CloudUnavailableError` that includes the safe provider error status and an
   actionable hint to check Google AI Studio Prepay credits or use an unbilled
   Free Tier project, without echoing raw response bodies or secrets.
3. When Google returns a transient server-side capacity error (`HTTP 503`,
   `HTTP 502`, or `HTTP 504`), `checked_json()` raises a retriable error and
   `GeminiProvider` retries the pending HTTP request up to
   `max_rate_limit_retries` times with exponential backoff and bounded jitter
   before any visible text delta is streamed.
4. Retrying a failed Gemini HTTP request never re-executes a local `robot.*`,
   `memory.*`, `information.*`, or `mcp.*` tool.
5. `GeminiProvider` enforces a short minimum interval (`min_request_interval_seconds`,
   default `0.35` seconds) between consecutive outbound generation requests on
   the same provider instance so back-to-back `Turn 1` (tool proposal) and
   `Turn 2` (tool result summarization) requests do not burst within a few
   milliseconds on Free Tier quotas.
6. `PromptComposer` in `prompts.py` instructs the model to use the fresh host
   clock reading already injected in `runtime_state.system_time` for ordinary
   current-time, date, and relative-scheduling questions, reserving the
   `system.time.get` tool for cases where a fresh timestamp is needed after a
   previous step.
7. If one or more local tools have already executed during a chat turn
   (`completed_tool_calls > 0`) and the follow-up model summarization request
   (`model_turn_number >= 2`) still fails with `CloudProviderError` or
   `OllamaUnavailableError` after all provider retries are exhausted,
   `AgentLoop` persists and returns a deterministic, honest summary of the
   completed tool results instead of crashing the turn with an unhandled
   exception.
8. Public CLI commands, `config.toml` schemas, IPC payloads, tool schemas,
   confirmation rules (`CONFIRM` / `CANCEL`), motion arming (`/arm` / `/disarm`),
   and safety latches remain backward-compatible.

Non-goals: modifying `ninjarobot_pi5_ide`, editing any managed `pi5*` driver,
changing Google OAuth (which remains removed in favor of API keys), or
automatically retrying physical robot actions.

Hardware risk level: none for Phases 1 and 3; safety-positive for Phase 2
because deterministic post-tool completion prevents operators from re-sending a
movement prompt when only the final cloud text summary failed.

## Evidence and root-cause findings

### Provenance and wiki retrieval

Inspected repository checkout: `b68d3de6b0ea7a06faf826d0949886920aebff64`.
`git status --short` was clean prior to creating this plan.

In the development sandbox, `python3 scripts/wiki.py search` and
`python3 scripts/wiki.py source status` could not spawn the `llmwiki` binary
(`Operation not permitted`). Following the project knowledge workflow in
`AGENTS.md`, no packages were installed and the local wiki pages, raw source
manuals, `project-knowledge.json`, and Python implementation were inspected
directly.

| Evidence source | Provenance and status | Key finding |
| --- | --- | --- |
| [Project knowledge map](../ninjarobot_pi5_wiki/project-knowledge.json) | Reviewed checkout `f3923e082a48669dbc4d1961a8e080415cbb964f` (`2026-11-09-02`) | Maps `gemini_provider.py`, `cloud_common.py`, `cloud_registry.py`, `model_selection.py`, `agent_loop.py`, and `prompts.py` |
| [Wiki overview](../ninjarobot_pi5_wiki/wiki/overview.md) and [Architecture](../ninjarobot_pi5_wiki/wiki/concepts/architecture.md) | `status: draft`, AI semantic review `passed` (`2026-11-09`), no human verification claimed | Documents the `user/model -> ninjarobot_pi5_agent -> ninjarobot_pi5_ide -> pi5*` boundary |
| [DevelopmentGuide.md (2026-11-09-02)](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-09-02/DevelopmentGuide.md) | Registered source `src-20261109-developmentguide` | Lines 2022–2056 document `LLMProvider`, Gemini `generateContent` / `streamGenerateContent`, thought signatures, `HTTP 429` two-retry behavior, and `HTTP 400` category redaction |
| [InstallationGuide.md (2026-11-09-02)](../ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-09-02/InstallationGuide.md) | Registered source `src-20261109-installationguide` | Lines 3232–3281 document `ninjarobot-agent provider set-api-key gemini`, `429` retries, and `INVALID_ARGUMENT`; does not yet document `HTTP 402` or `HTTP 503` |
| [DevelopmentLog.md (2026-11-09-02)](../ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-11-09-02/DevelopmentLog.md) | Registered source `src-20261109-developmentlog` | Lines 1714–1745 record the 13 August 2026 Gemini 3 tool-continuation and `429` quota-retry update |

### Fact 1 — Why `HTTP 402` happened after setting a Google AI Studio API key

1. **Google AI Studio Prepay billing and project-level tiers:**
   According to Google's official Gemini API billing and troubleshooting
   documentation (`ai.google.dev/gemini-api/docs/billing` and
   `ai.google.dev/gemini-api/docs/troubleshooting`), Google AI Studio uses a
   **Prepay** credit wallet for paid projects and returns **HTTP `402 Payment
   Required`** (`status: "RESOURCE_EXHAUSTED"`, message: *"Your prepayment
   credits are depleted"*) whenever a paid project's prepaid balance reaches
   `$0`.
2. **No automatic downgrade from Paid Tier to Free Tier:**
   In Google AI Studio, billing status belongs to the **Google Cloud Project**,
   not the individual API key. Once a project is linked to a billing account
   with a `$0` Prepay balance, every API key generated inside that project
   returns `HTTP 402`—it does not fall back to the Free Tier automatically.
   Using the `$0` Free Tier requires generating an API key inside a project that
   has **no billing account linked** (where the project plan badge shows
   **Free**) and selecting a Free-Tier-eligible Flash model (such as
   `gemini-3.8-flash` or `gemini-3.5-flash`).
3. **Why `model select` and `provider health` succeeded before chat failed:**
   In [gemini_provider.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/gemini_provider.py),
   both `list_models()` and `health()` only call `GET /v1beta/models?pageSize=1000`.
   Google's `GET /models` endpoint does not check Prepay balance or generation
   tier eligibility, so model selection succeeds and marks Gemini `READY`. The
   `HTTP 402` error only occurs when `stream()` or `generate()` calls
   `POST /v1beta/models/<model>:streamGenerateContent` (or `:generateContent`).
4. **Why the error message was opaque:**
   In [cloud_common.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py),
   `checked_json()` handles `401/403`, `429`, and `400` specifically, but falls
   through to a generic `CloudUnavailableError("Gemini request failed with HTTP 402")`
   for status `402`. Then, because `allow_provider_fallback` is `True` on Turn 1,
   `ModelManager` in [model_selection.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/model_selection.py)
   wraps that error in `ModelSelectionError: model providers failed before tool
   execution: gemini: Gemini request failed with HTTP 402`.

### Fact 2 — Why `HTTP 503` happens during Free-Tier tool calling

1. **Google's `HTTP 503 UNAVAILABLE` behavior on the Free Tier:**
   According to `ai.google.dev/gemini-api/docs/troubleshooting`, `HTTP 503
   UNAVAILABLE` (*"This model is currently experiencing high demand"*) indicates
   a temporary server-side capacity spike. Free Tier traffic has lower queue
   priority than Paid Tier traffic, and Google's official troubleshooting guide
   explicitly instructs clients to retry `503 UNAVAILABLE` using exponential
   backoff with jitter.
2. **How NinjaRobotPi5 executes a tool call across two rapid model turns:**
   In [agent_loop.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py),
   each user prompt that triggers a tool call executes at least two model turns
   inside `AgentLoop._chat()`:
   - **Turn 1 (`model_turn_number == 1`, `completed_tool_calls == 0`):** Sends
     the system prompt (`IMMUTABLE_SAFETY_PROMPT`, `IDENTITY_PROMPT`, live
     `runtime_state` JSON, and `memory_context`), conversation history, and all
     ~30+ tool schemas (`robot.*`, `memory.*`, `notes.*`, `calendar.*`,
     `research.*`, `briefing.*`, `tasks.*`, `project_help.*`, `command_help.*`,
     `system.time.get`, and enabled `mcp.*`). Gemini responds with a
     `functionCall`.
   - **Local tool execution:** Read-only local tools (`system.time.get`,
     `memory.profile.get`, `robot.status`) finish in **under 5 milliseconds** on
     the Raspberry Pi 5.
   - **Turn 2 (`model_turn_number == 2`, `completed_tool_calls >= 1`):** Within
     milliseconds of Turn 1 closing, `AgentLoop` sends a second full
     `streamGenerateContent` request containing the entire system prompt, all
     tool schemas, the replayed `functionCall` (with `thoughtSignature`), and
     the `functionResponse`.
3. **Four specific code bottlenecks in `ninjarobot_pi5_agent`:**
   - **Bottleneck A — No retry on `HTTP 503`:** `checked_json()` in
     [cloud_common.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py)
     only raises `CloudRateLimitError` on `HTTP 429`. When Gemini returns
     `HTTP 503`, `checked_json()` raises a plain `CloudUnavailableError`,
     bypassing `GeminiProvider`'s retry loop completely.
   - **Bottleneck B — Zero inter-request pacing:** `GeminiProvider` in
     [gemini_provider.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/gemini_provider.py)
     sends Turn 2 immediately (<10 ms after Turn 1), creating a back-to-back
     multi-thousand-token burst that frequently trips Free Tier capacity limits.
   - **Bottleneck C — Redundant clock tool round-trip:** `PromptComposer.compose()`
     in [prompts.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py)
     already injects `runtime_state = {**runtime_state, "system_time": system_time_snapshot()}`
     into the system prompt on every turn. However, line 182 of `prompts.py`
     says: *"Prefer system.time.get when a fresh clock read is needed."* This
     causes Gemini to make a 2-turn tool call (`system.time.get`) even when the
     fresh host clock timestamp is already present in the Turn 1 system prompt.
   - **Bottleneck D — Hard failure on Turn 2 after the tool already succeeded:**
     On Turn 2 (`model_turn_number >= 2`), `allow_provider_fallback` is `False`
     ([agent_loop.py](../ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py)).
     If Gemini returns `503` on Turn 2, `ModelManager` raises
     `CloudUnavailableError: Gemini request failed with HTTP 503` directly and
     aborts the entire chat turn—even though the local tool on Turn 1 **already
     succeeded** and its result was already saved to SQLite.

## Target tool-calling workflow

The refined workflow adds four defense layers so Free-Tier Gemini tool calling
runs smoothly from start to finish:

```text
User Prompt
  │
  ▼
[Layer 3: Single-Turn Context First]
  PromptComposer provides fresh runtime_state.system_time + memory_context.
  • If the user only asks for current time/date/status already in runtime_state,
    Gemini answers in 1 turn (0 tool calls, 50% fewer API requests).
  • If an action or lookup tool is needed, proceed to Turn 1.
  │
  ▼
[Layer 1: Pre-Output Retry on 429 + 503/502/504]
  Turn 1 POST :streamGenerateContent
  • On HTTP 429 or 503/502/504 before any streamed text:
    retry up to 3 times (1s -> 2s -> 4s + jitter, or Retry-After).
  • On HTTP 402: fail immediately with clear Google AI Studio Prepay/Free-Tier hint.
  │
  ▼
[Local Tool Execution]
  PolicyEngine -> ToolRegistry -> IDE / MCP executes tool once and persists result.
  │
  ▼
[Layer 2: Inter-Request Pacing]
  GeminiProvider waits until min_request_interval_seconds (0.35s default) has
  elapsed since Turn 1 finished, avoiding millisecond back-to-back bursts.
  │
  ▼
[Layer 1 + Layer 4: Turn 2 Summarization with Graceful Post-Tool Completion]
  Turn 2 POST :streamGenerateContent (with replayed call ID + thoughtSignature)
  • Layer 1 retries transient 429/503/502/504 up to 3 times before streaming text.
  • Layer 4: If Turn 2 still fails after all retries AND completed_tool_calls > 0,
    AgentLoop formats a deterministic summary from the completed ToolExecutionResult,
    saves it to ConversationStore, and returns a clean AgentReply without crashing.
```

## Phased implementation plan

### Phase 1 — Transient `HTTP 503` retry, `HTTP 402` diagnostics, and request pacing

- **Objective:** Make `checked_json()` and `GeminiProvider` retry transient
  `HTTP 503` / `502` / `504` responses with exponential backoff and jitter,
  space out back-to-back requests by at least `0.35` seconds, and report a clear,
  secret-safe explanation on `HTTP 402`.
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/gemini_provider.py`
  - `ninjarobot_pi5_agent/tests/test_gemini_provider.py`
- **Compatibility contract:**
  - `CloudRateLimitError` and any new transient subclass remain subclasses of
    `CloudUnavailableError` (which is a subclass of `CloudProviderError`), so
    existing `except CloudProviderError` and `ModelManager` fallback logic
    continue to work unchanged.
  - `GeminiConfig` remains backward-compatible: `max_rate_limit_retries`
    defaults to `3` (with `le=5`) and `min_request_interval_seconds` defaults to
    `0.35` (`ge=0.0, le=5.0`).
- **Hardware risk level:** None (cloud HTTP client layer only).

#### Step 1.1 — Update `checked_json()` in `cloud_common.py`

In `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py`, add
`CloudTransientError` (or extend `CloudRateLimitError` with a `reason` message)
for HTTP `502`, `503`, and `504`, and add explicit `HTTP 402` handling that
includes `_safe_error_status(response)` without leaking the response body:

```python
class CloudRateLimitError(CloudUnavailableError):
    """The provider requested a bounded retry after rate limiting or transient overload."""

    def __init__(
        self,
        provider: str,
        retry_after_seconds: float | None,
        *,
        status_code: int = 429,
        error_status: str | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        self.status_code = status_code
        self.error_status = error_status
        detail = ""
        if retry_after_seconds is not None:
            detail = f"; retry after {retry_after_seconds:g} seconds"
        if status_code in {502, 503, 504}:
            status_suffix = f" ({error_status})" if error_status else ""
            message = (
                f"{provider} service is temporarily overloaded or unavailable "
                f"(HTTP {status_code}{status_suffix}){detail}"
            )
        else:
            message = f"{provider} rate limit or account quota was reached{detail}"
        super().__init__(message)
```

And inside `checked_json()` in `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/cloud_common.py`:

```python
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if response.status_code in {401, 403}:
            raise CloudAuthenticationError(
                f"{provider} rejected the configured credentials"
            ) from exc
        if response.status_code == 402:
            status = _safe_error_status(response, default="PAYMENT_REQUIRED")
            raise CloudUnavailableError(
                f"{provider} request failed with HTTP 402 ({status}): "
                "billing or prepayment credits are depleted; check your Google AI Studio "
                "Prepay balance or use an API key from an unbilled Free Tier project"
            ) from exc
        if response.status_code == 429:
            raise CloudRateLimitError(
                provider,
                _retry_after_seconds(response),
                status_code=429,
            ) from exc
        if response.status_code in {502, 503, 504}:
            raise CloudRateLimitError(
                provider,
                _retry_after_seconds(response),
                status_code=response.status_code,
                error_status=_safe_error_status(response, default="UNAVAILABLE"),
            ) from exc
        if response.status_code == 400:
            raise CloudUnavailableError(
                f"{provider} rejected the request ({_safe_error_status(response)})"
            ) from exc
        raise CloudUnavailableError(
            f"{provider} request failed with HTTP {response.status_code}"
        ) from exc
```

Update `_safe_error_status()` to accept an optional `default: str = "BAD_REQUEST"`
parameter so it works cleanly for `400`, `402`, and `503` responses:

```python
def _safe_error_status(response: httpx.Response, *, default: str = "BAD_REQUEST") -> str:
    """Return only a provider error category, never its potentially sensitive text."""
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return default
    if not isinstance(payload, dict):
        return default
    error = payload.get("error")
    if not isinstance(error, dict):
        return default
    status = error.get("status")
    if isinstance(status, str) and re.fullmatch(r"[A-Z_]{1,64}", status):
        return status
    return default
```

#### Step 1.2 — Add inter-request pacing and jittered backoff in `gemini_provider.py`

In `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/gemini_provider.py`, update
`GeminiConfig` and `GeminiProvider`:

```python
import random
import time


class GeminiConfig(BaseModel):
    """Validated Gemini adapter configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model: str = "gemini-2.5-flash"
    base_url: HttpUrl = HttpUrl("https://generativelanguage.googleapis.com/v1beta")
    project_id: str | None = None
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)
    max_rate_limit_retries: int = Field(default=3, ge=0, le=5)
    max_rate_limit_retry_delay_seconds: float = Field(default=10.0, ge=0.1, le=30.0)
    min_request_interval_seconds: float = Field(default=0.35, ge=0.0, le=5.0)
```

In `GeminiProvider.__init__()`, track `self._last_request_completed_at: float | None = None`,
and add `_pace_request()` plus jitter in `_wait_rate_limit_retry()`:

```python
    async def _pace_request(self) -> None:
        """Enforce a small gap between back-to-back turns (such as tool continuation)."""
        if (
            self.config.min_request_interval_seconds <= 0
            or self._last_request_completed_at is None
        ):
            return
        elapsed = time.monotonic() - self._last_request_completed_at
        remaining = self.config.min_request_interval_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _mark_request_completed(self) -> None:
        self._last_request_completed_at = time.monotonic()

    async def _wait_rate_limit_retry(self, error: CloudRateLimitError, attempt: int) -> None:
        delay = error.retry_after_seconds
        if delay is None:
            # Exponential backoff (1s, 2s, 4s...) with deterministic-safe bounded jitter
            base_delay = float(2**attempt)
            jitter = random.uniform(0.0, min(0.25, base_delay * 0.1))
            delay = base_delay + jitter
        await asyncio.sleep(min(delay, self.config.max_rate_limit_retry_delay_seconds))
```

Call `await self._pace_request()` before each `POST` in `stream()` and
`_generate_with_retry()`, and call `self._mark_request_completed()` in a
`finally` block around the HTTP request. Also ensure `stream()` only retries
`CloudRateLimitError` when `not text and not calls` (before any output has been
emitted to the caller).

#### Phase 1 validation gate and rollback

- **Validation gate:** Run the full `AGENTS.md` check suite plus new tests in
  `ninjarobot_pi5_agent/tests/test_gemini_provider.py` verifying:
  1. `HTTP 503` on Turn 1 or Turn 2 (`generate` and `stream`) retries and
     succeeds when a subsequent attempt returns `200`.
  2. `HTTP 503` after `max_rate_limit_retries` raises `CloudRateLimitError`
     mentioning `HTTP 503 (UNAVAILABLE)`.
  3. `HTTP 402` fails immediately without retry and reports the Prepay/Free-Tier
     guidance.
  4. Back-to-back calls respect `min_request_interval_seconds`.
- **Rollback:** Revert `cloud_common.py`, `gemini_provider.py`, and
  `test_gemini_provider.py` together.

---

### Phase 2 — Single-turn clock fast path and post-tool graceful completion

- **Objective:**
  1. Avoid unnecessary `system.time.get` tool calls when the fresh host clock
     is already present in `runtime_state.system_time`.
  2. Ensure `AgentLoop._chat()` never crashes with an unhandled cloud error
     after a local tool has already executed (`completed_tool_calls > 0`).
- **Target files:**
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py`
  - `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py`
  - `ninjarobot_pi5_agent/tests/test_prompts.py`
  - `ninjarobot_pi5_agent/tests/test_agent_loop.py`
- **Compatibility contract:**
  - `system.time.get` remains registered and callable whenever the model or a
    recipe explicitly invokes it.
  - All tool policy checks, confirmation requirements, camera grants, and motion
    arming rules remain untouched.
  - Post-tool graceful completion only activates when `completed_tool_calls > 0`
    and `self._model_turn()` raises `CloudProviderError` or
    `OllamaUnavailableError` (or `ModelSelectionError` wrapping them).
- **Hardware risk level:** None / safety-positive (prevents users from
  re-running a physical movement command when Turn 1 already moved the robot
  and Turn 2's cloud summary failed with `503`).

#### Step 2.1 — Update `PromptComposer` clock guidance in `prompts.py`

In `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/prompts.py` (lines 180–183),
replace the instruction that nudges the model to call `system.time.get` on
every clock question with guidance to use the already-injected
`runtime_state.system_time` directly:

```python
                    "system_time is a fresh reading of the Agent host clock captured for "
                    "this turn, not model knowledge. Use runtime_state.system_time directly "
                    "to answer current time/date questions and for now/today/tomorrow "
                    "relative scheduling without calling system.time.get, unless you need "
                    "a new timestamp after executing another tool. "
```

#### Step 2.2 — Add post-tool graceful completion in `agent_loop.py`

In `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py`, track the
results of tools executed during the current user request
(`executed_results: list[ToolExecutionResult] = []`). If `self._model_turn()`
raises `CloudProviderError`, `OllamaUnavailableError`, or `ModelSelectionError`
when `completed_tool_calls > 0`, synthesize a concise deterministic reply from
`executed_results`, persist it to `self._store`, stream it to `on_text_delta`,
and return a normal `AgentReply`:

```python
def _format_post_tool_fallback_reply(
    results: Sequence[ToolExecutionResult],
) -> str:
    """Build a safe, deterministic reply when the model is unavailable after tool execution."""
    summaries: list[str] = []
    for item in results:
        if item.status is ToolExecutionStatus.SUCCEEDED:
            if isinstance(item.data, dict) and item.data:
                compact = json.dumps(item.data, ensure_ascii=False, sort_keys=True)
                if len(compact) > 400:
                    compact = compact[:397] + "..."
                summaries.append(f"{item.tool_name} succeeded: {compact}.")
            else:
                summaries.append(f"{item.tool_name} succeeded.")
        else:
            reason = item.error or item.status.value
            summaries.append(f"{item.tool_name} {item.status.value}: {reason}")
    joined = " ".join(summaries)
    return (
        f"Completed tool action ({joined}) "
        "The AI model was temporarily busy while formatting a follow-up summary, "
        "so this result is reported directly. Do not repeat a physical action if it "
        "already completed."
    )[:4000]
```

And inside `AgentLoop._chat()` in `ninjarobot_pi5_agent/src/ninjarobot_pi5_agent/agent_loop.py`:

```python
            log_lifecycle("thinking", reason="model_requested")
            try:
                turn = await self._model_turn(
                    request,
                    on_text_delta=on_text_delta,
                    session_id=session_id,
                )
            except (CloudProviderError, OllamaUnavailableError, ModelSelectionError) as exc:
                if not executed_results:
                    raise
                fallback_text = _format_post_tool_fallback_reply(executed_results)
                await self._events.publish(
                    AgentEventType.ERROR,
                    "Model provider was unavailable after tool execution; returning direct tool result.",
                    session_id=session_id,
                    correlation_id=request_id,
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
                return await self._direct_reply(
                    session_id=session_id,
                    text=fallback_text,
                    tool_calls=completed_tool_calls,
                    on_text_delta=on_text_delta,
                    model_turns=model_turn_number,
                )
```

*(Update `_direct_reply()` to accept `model_turns: int = 0` so the returned
`AgentReply` accurately records how many model turns were attempted.)*

#### Phase 2 validation gate and rollback

- **Validation gate:** Full `AGENTS.md` check suite plus unit tests in
  `test_prompts.py` and `test_agent_loop.py` verifying:
  1. The composed system prompt instructs the model to use
     `runtime_state.system_time` directly.
  2. When Turn 1 calls a tool (for example `robot.status` or `system.time.get`),
     the tool succeeds, and Turn 2 fails with `CloudUnavailableError` (`503`),
     `AgentLoop.chat()` returns a valid `AgentReply` containing the completed
     tool result, persists the assistant message in `ConversationStore`, and
     does not raise an unhandled exception.
  3. When Turn 1 itself fails before any tool executes (`completed_tool_calls == 0`),
     the error is still raised as before.
- **Rollback:** Revert `prompts.py`, `agent_loop.py`, `test_prompts.py`, and
  `test_agent_loop.py` together.

---

### Phase 3 — Documentation, operator configuration guide, and wiki update

- **Objective:** Document Google AI Studio Free-Tier vs. Prepay project rules,
  `HTTP 402` and `HTTP 503` handling, automatic `fallback_providers = ["ollama"]`
  configuration, and the refined tool-calling workflow in `README.md` and a new
  wiki source revision (`2026-11-14`).
- **Target files:**
  - `README.md`
  - `ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-14/InstallationGuide.md`
  - `ninjarobot_pi5_wiki/raw/articles/ninjarobotpi5/2026-11-14/DevelopmentGuide.md`
  - `ninjarobot_pi5_wiki/raw/notes/ninjarobotpi5/2026-11-14/DevelopmentLog.md`
  - `ninjarobot_pi5_wiki/project-knowledge.json` and affected `ninjarobot_pi5_wiki/wiki/` pages (applied only after showing the semantic diff and obtaining explicit owner approval)
- **Hardware risk level:** None.

#### Operator configuration example to include in `InstallationGuide.md`

Show operators how to configure Google AI Studio Free Tier alongside automatic
local Ollama failover in `~/.config/ninjarobot_pi5/config.toml`:

```toml
[agent]
default_provider = "gemini"
fallback_providers = ["ollama"]

[providers.gemini]
kind = "gemini"
model = "gemini-3.8-flash"
enabled = true
auth_method = "api_key"
api_key_env = "GEMINI_API_KEY"

[providers.ollama]
kind = "ollama"
model = "qwen3:4b"
enabled = true
base_url = "http://127.0.0.1:11434"
```

## Validation commands

Run the standard repository validation gate from the repository root after each
implementation phase:

1. Verify that no managed `pi5*` driver files were modified:

   ```bash
   uv run --frozen python scripts/verify_immutable_drivers.py
   uv run --frozen python scripts/verify_workspace_driver_sources.py
   ```

   Expected result: all baseline and authorized managed driver hashes pass.

2. Compile all Python sources and run linting, formatting, and static type checks:

   ```bash
   uv run --frozen python -m compileall -q ninjarobot_pi5_agent/src ninjarobot_pi5_ide/src scripts tests
   uv run --frozen ruff check .
   uv run --frozen ruff format --check .
   uv run --frozen mypy ninjarobot_pi5_ide/src ninjarobot_pi5_agent/src
   ```

   Expected result: zero syntax, lint, formatting, or type errors.

3. Run the unit and integration test suites and check diff formatting:

   ```bash
   uv run --frozen pytest -q
   git diff --check
   ```

   Expected result: all tests pass and `git diff --check` produces no output.

4. After Phase 3 documentation updates, run the wiki verification checks:

   ```bash
   python3 scripts/wiki.py check
   python3 scripts/wiki.py lint
   ```

   Expected result: source hashes, implementation fingerprints, and wiki links
   pass verification.

## Manual Raspberry Pi 5 acceptance

Because live Gemini API calls require an active Google AI Studio account and
internet access on the Raspberry Pi 5, run these beginner-friendly manual checks
on the Pi after the software gates pass.

### 1. Safe smoke test (no hardware movement)

1. Activate the virtual environment on the Raspberry Pi 5:

   ```bash
   cd "$HOME/NinjaRobotPi5"
   source .venv/bin/activate
   ```

2. Verify the Gemini provider health and selected model:

   ```bash
   ninjarobot-agent provider health gemini
   ninjarobot-agent model list --provider gemini
   ```

   Expected result: `status` is `ready` for your selected Flash model
   (`gemini-3.8-flash` or `gemini-3.5-flash`).

3. Start chat in simulation mode and ask for the current time and robot status:

   ```bash
   ninjarobot-agent chat
   ```

   Enter:
   - `What time is it right now?`
   - `Check the robot status.`

   Expected result:
   - The time question is answered directly in a single turn using
     `runtime_state.system_time`.
   - The status question executes `robot.status` and returns a clean summary
     without `HTTP 503` errors.
   - Rollback: switch back to local Ollama at any time with
     `ninjarobot-agent model select qwen3:4b --provider ollama --route local`.

### 2. Device communication test (non-moving display/buzzer/sensor)

1. With real hardware enabled (`ninjarobot-agent service start --real` or web UI),
   keep AI motion **disarmed** (`/disarm`).
2. Prompt the agent: `Show a happy face on the display.`
3. Expected result: `robot.behavior.execute_expression` runs once, displays the
   happy face, and returns a completion reply without `503` failure.
4. Rollback: run `/stop` in chat or press **Emergency Stop** in the web UI.

### 3. Actuator-moving test (opt-in, raised wheels required)

> [!WARNING]
> Place the robot on a stable stand with its wheels raised clear of the desk or
> floor, and keep a hand near the power switch before arming motion.

1. Arm AI motion explicitly in chat:

   ```text
   /arm
   ```

2. Prompt the agent to center a calibrated servo or run a short movement
   behavior.
3. Expected result: the movement executes once and the agent returns its final
   summary (or the direct tool completion summary if the cloud model is
   momentarily busy on Turn 2). It must never repeat the movement automatically.
4. Disarm motion immediately afterward:

   ```text
   /disarm
   ```

### 4. Power-risk test

No power-off, boot configuration, `systemd`, or `sudoers` behavior is modified
by this plan. No live power-off test is required.

## Documentation and rollback

- **Documentation impact:** Updates `README.md`, `InstallationGuide.md`,
  `DevelopmentGuide.md`, `DevelopmentLog.md`, and the compiled wiki pages for
  architecture and features. Originals under `ninjarobot_pi5_wiki/raw/` are
  never edited in place; a new `2026-11-14` folder is created and registered.
- **Full rollback procedure:** If any regression is observed on the Raspberry
  Pi 5, revert the Phase 1–2 commits in `ninjarobot_pi5_agent` or switch the
  active provider to local Ollama:

  ```bash
  ninjarobot-agent model select qwen3:4b --provider ollama --route local
  ```

"""Provider-neutral model catalog, acceptance evidence, and active selection."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ninjarobot_pi5_ide import load_robot_config, save_robot_config

from .benchmark import BenchmarkReport
from .cloud_common import CloudProviderError
from .models import (
    ModelRequest,
    ModelStreamEvent,
    ModelTurn,
    ProviderCapabilities,
    ProviderHealth,
    ProviderHealthStatus,
)
from .ollama import OllamaUnavailableError
from .providers import LLMProvider

ProviderFactory = Callable[[str], LLMProvider]
CatalogLoader = Callable[[], Awaitable[tuple["ModelCatalogEntry", ...]]]
SelectionWriter = Callable[[str, str], None]


class ModelSelectionError(RuntimeError):
    """Raised when a requested provider or model cannot be selected safely."""


class ModelCatalogEntry(BaseModel):
    """Provider-neutral metadata shown by CLI model selection."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    size_bytes: Annotated[int, Field(ge=0)] | None = None
    parameter_size: str | None = None
    quantization: str | None = None
    family: str | None = None
    modified_at: str | None = None
    current: bool = False
    accepted: bool = False


@dataclass(frozen=True, slots=True)
class ProviderRegistration:
    """One provider implementation registered for current or future selection."""

    provider_id: str
    factory: ProviderFactory
    catalog: CatalogLoader
    default_model: str = ""


class BenchmarkRegistry:
    """Read bounded benchmark reports without trusting filenames."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory).expanduser()

    def accepted(self, model: str) -> bool:
        """Return true when any valid report accepts this exact model name."""
        if not self._directory.is_dir():
            return False
        for path in sorted(self._directory.glob("*.json")):
            try:
                if path.is_symlink() or path.stat().st_size > 1_048_576:
                    continue
                report = BenchmarkReport.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if report.model == model and report.accepted:
                return True
        return False


class ModelManager:
    """Delegate the provider protocol while supporting safe idle-time replacement."""

    def __init__(
        self,
        *,
        active_provider_id: str,
        active_model: str,
        active_provider: LLMProvider,
        registrations: tuple[ProviderRegistration, ...],
        benchmarks: BenchmarkRegistry,
        selection_writer: SelectionWriter,
        fallback_provider_ids: tuple[str, ...] = (),
    ) -> None:
        registrations_by_id = {
            registration.provider_id: registration for registration in registrations
        }
        if len(registrations_by_id) != len(registrations):
            raise ValueError("provider registration IDs must be unique")
        if active_provider_id not in registrations_by_id:
            raise ValueError("active provider must have a registration")
        self._provider_id = active_provider_id
        self._model = active_model
        self._provider = active_provider
        self._registrations = registrations_by_id
        self._benchmarks = benchmarks
        self._selection_writer = selection_writer
        unknown_fallbacks = sorted(set(fallback_provider_ids) - set(registrations_by_id))
        if unknown_fallbacks:
            raise ValueError(
                "unknown fallback provider registrations: " + ", ".join(unknown_fallbacks)
            )
        self._fallback_provider_ids = fallback_provider_ids
        self._closed = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Describe the currently selected provider."""
        return self._provider.capabilities

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model(self) -> str:
        return self._model

    @property
    def accepted(self) -> bool:
        return self._benchmarks.accepted(self._model)

    async def generate(self, request: ModelRequest) -> ModelTurn:
        self._ensure_open()
        try:
            return await self._provider.generate(request)
        except (CloudProviderError, OllamaUnavailableError):
            if not request.allow_provider_fallback:
                raise
        for provider_id in self._fallback_provider_ids:
            registration = self._registrations[provider_id]
            candidate = registration.factory(registration.default_model)
            try:
                return await candidate.generate(request)
            except (CloudProviderError, OllamaUnavailableError):
                continue
            finally:
                await candidate.close()
        raise ModelSelectionError("every configured provider failed before tool execution")

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        self._ensure_open()
        emitted_public_output = False
        try:
            async for event in self._provider.stream(request):
                if event.event.value == "text_delta" and event.text:
                    emitted_public_output = True
                yield event
            return
        except (CloudProviderError, OllamaUnavailableError):
            if not request.allow_provider_fallback or emitted_public_output:
                raise
        for provider_id in self._fallback_provider_ids:
            registration = self._registrations[provider_id]
            candidate = registration.factory(registration.default_model)
            emitted_candidate_output = False
            try:
                async for event in candidate.stream(request):
                    if event.event.value == "text_delta" and event.text:
                        emitted_candidate_output = True
                    yield event
                return
            except (CloudProviderError, OllamaUnavailableError):
                if emitted_candidate_output:
                    raise
            finally:
                await candidate.close()
        raise ModelSelectionError("every configured provider failed before tool execution")

    async def health(self) -> ProviderHealth:
        self._ensure_open()
        return await self._provider.health()

    async def catalog(self, provider_id: str | None = None) -> tuple[ModelCatalogEntry, ...]:
        """List registered-provider models without loading them."""
        self._ensure_open()
        provider_ids = (
            (provider_id,) if provider_id is not None else tuple(sorted(self._registrations))
        )
        entries: list[ModelCatalogEntry] = []
        for identifier in provider_ids:
            try:
                registration = self._registrations[identifier]
            except KeyError as exc:
                raise ModelSelectionError(f"unknown model provider: {identifier}") from exc
            try:
                catalog_entries = await registration.catalog()
            except (CloudProviderError, KeyError, ValueError):
                if provider_id is not None:
                    raise
                continue
            for entry in catalog_entries:
                entries.append(
                    entry.model_copy(
                        update={
                            "current": (
                                identifier == self._provider_id and entry.name == self._model
                            ),
                            "accepted": self._benchmarks.accepted(entry.name),
                        }
                    )
                )
        return tuple(entries)

    async def select(self, provider_id: str, model: str) -> ModelCatalogEntry:
        """Health-check, persist, and atomically replace the active provider."""
        self._ensure_open()
        if provider_id == self._provider_id and model == self._model:
            return self._selection_entry()
        entries = await self.catalog(provider_id)
        selected = next((entry for entry in entries if entry.name == model), None)
        if selected is None:
            raise ModelSelectionError(
                f"model '{model}' is not installed for provider '{provider_id}'"
            )
        registration = self._registrations[provider_id]
        candidate = registration.factory(model)
        try:
            health = await candidate.health()
            if health.status is not ProviderHealthStatus.READY:
                raise ModelSelectionError(health.detail or "selected model is not ready")
            self._selection_writer(provider_id, model)
        except BaseException:
            await candidate.close()
            raise
        previous = self._provider
        self._provider = candidate
        self._provider_id = provider_id
        self._model = model
        await previous.close()
        return selected.model_copy(update={"current": True})

    def selection(self) -> dict[str, object]:
        """Return safe current-selection metadata."""
        return {
            "provider": self._provider_id,
            "model": self._model,
            "accepted": self.accepted,
        }

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._provider.close()

    def _selection_entry(self) -> ModelCatalogEntry:
        return ModelCatalogEntry(
            provider=self._provider_id,
            name=self._model,
            current=True,
            accepted=self.accepted,
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("model manager is closed")


def persist_model_selection(
    config_path: str | Path,
    provider_id: str,
    model: str,
) -> None:
    """Atomically update only the selected provider and model."""
    config = load_robot_config(config_path)
    try:
        provider = config.providers[provider_id]
    except KeyError as exc:
        raise ModelSelectionError(f"unknown configured provider: {provider_id}") from exc
    if not provider.enabled:
        raise ModelSelectionError(f"configured provider is disabled: {provider_id}")
    updated_providers = dict(config.providers)
    updated_providers[provider_id] = provider.model_copy(update={"model": model})
    updated = config.model_copy(
        update={
            "agent": config.agent.model_copy(update={"default_provider": provider_id}),
            "providers": updated_providers,
        }
    )
    save_robot_config(updated, config_path, overwrite=True)

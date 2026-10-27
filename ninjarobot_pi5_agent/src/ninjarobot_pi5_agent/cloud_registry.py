"""Configuration-driven registry for Ollama and supported cloud providers."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from pydantic import HttpUrl

from ninjarobot_pi5_ide import load_robot_config

from .anthropic_provider import AnthropicConfig, AnthropicProvider
from .cloud_common import APIKeyCredential, CredentialSource
from .gemini_provider import GeminiConfig, GeminiProvider
from .model_selection import ModelCatalogEntry, ProviderRegistration
from .ollama import (
    DEFAULT_OLLAMA_API_KEY_ENV,
    DEFAULT_OLLAMA_CLOUD_URL,
    DEFAULT_OLLAMA_LOCAL_URL,
    OllamaConfig,
    OllamaProvider,
)
from .openai_provider import OpenAIConfig, OpenAIProvider
from .providers import LLMProvider
from .secrets import SecretStore


class ConfiguredProviderRegistry:
    """Build providers lazily from the latest owner configuration."""

    def __init__(
        self,
        config_path: str | Path,
        secrets: SecretStore,
        *,
        ollama_base_url_override: str | None = None,
    ) -> None:
        self._config_path = Path(config_path).expanduser()
        self._secrets = secrets
        self._ollama_base_url_override = ollama_base_url_override

    def create(self, provider_id: str, model: str) -> LLMProvider:
        config = load_robot_config(self._config_path)
        try:
            provider = config.providers[provider_id]
        except KeyError as exc:
            raise ValueError(f"unknown configured provider: {provider_id}") from exc
        if not provider.enabled:
            raise ValueError(f"configured provider is disabled: {provider_id}")
        if provider.kind == "ollama":
            api_key_env = provider.api_key_env or DEFAULT_OLLAMA_API_KEY_ENV
            has_api_key = self._secrets.contains(api_key_env)
            if self._ollama_base_url_override:
                base_url = self._ollama_base_url_override
            elif has_api_key and (
                provider.base_url is None or provider.base_url == DEFAULT_OLLAMA_LOCAL_URL
            ):
                base_url = DEFAULT_OLLAMA_CLOUD_URL
            else:
                base_url = provider.base_url or DEFAULT_OLLAMA_LOCAL_URL
            ollama_credentials: CredentialSource | None = (
                APIKeyCredential(
                    self._secrets,
                    api_key_env,
                    "Authorization",
                    "Bearer ",
                )
                if has_api_key or base_url == DEFAULT_OLLAMA_CLOUD_URL
                else None
            )
            return OllamaProvider(
                OllamaConfig(
                    model=model,
                    base_url=base_url,
                ),
                credentials=ollama_credentials,
            )
        credentials = self._credentials(provider_id)
        if provider.kind == "openai":
            return OpenAIProvider(
                OpenAIConfig(
                    model=model,
                    base_url=HttpUrl(provider.base_url or "https://api.openai.com/v1"),
                ),
                credentials,
            )
        if provider.kind == "gemini":
            return GeminiProvider(
                GeminiConfig(
                    model=model,
                    base_url=HttpUrl(
                        provider.base_url or "https://generativelanguage.googleapis.com/v1beta"
                    ),
                    project_id=provider.project_id,
                ),
                credentials,
            )
        if provider.kind == "anthropic":
            return AnthropicProvider(
                AnthropicConfig(
                    model=model,
                    base_url=HttpUrl(provider.base_url or "https://api.anthropic.com/v1"),
                ),
                credentials,
            )
        raise ValueError(f"unsupported provider kind: {provider.kind}")

    def registrations(self) -> tuple[ProviderRegistration, ...]:
        config = load_robot_config(self._config_path)
        return tuple(
            ProviderRegistration(
                provider_id=provider_id,
                default_model=provider.model,
                factory=partial(self.create, provider_id),
                catalog=partial(self.catalog, provider_id),
            )
            for provider_id, provider in sorted(config.providers.items())
            if provider.enabled
        )

    async def catalog(self, provider_id: str) -> tuple[ModelCatalogEntry, ...]:
        config = load_robot_config(self._config_path)
        try:
            selected_model = config.providers[provider_id].model
        except KeyError as exc:
            raise ValueError(f"unknown configured provider: {provider_id}") from exc
        provider = self.create(provider_id, selected_model)
        try:
            if isinstance(provider, OllamaProvider):
                entries = tuple(
                    ModelCatalogEntry(
                        provider=provider_id,
                        name=model.name,
                        size_bytes=model.size_bytes,
                        parameter_size=model.parameter_size,
                        quantization=model.quantization,
                        family=model.family,
                        modified_at=model.modified_at,
                    )
                    for model in await provider.list_models()
                )
            elif isinstance(
                provider,
                (OpenAIProvider, GeminiProvider, AnthropicProvider),
            ):
                entries = tuple(
                    entry.model_copy(update={"provider": provider_id})
                    for entry in await provider.list_models()
                )
            else:
                raise TypeError(f"provider catalog is not implemented: {type(provider).__name__}")
            return entries
        finally:
            await provider.close()

    def credential_status(self, provider_id: str) -> dict[str, object]:
        config = load_robot_config(self._config_path)
        if provider_id not in config.providers:
            raise ValueError(f"unknown configured provider: {provider_id}")
        return self._credentials(provider_id).status()

    def _credentials(self, provider_id: str) -> CredentialSource:
        config = load_robot_config(self._config_path)
        provider = config.providers[provider_id]
        if provider.auth_method == "api_key":
            api_key_env = provider.api_key_env or (
                DEFAULT_OLLAMA_API_KEY_ENV if provider.kind == "ollama" else None
            )
            if api_key_env is None:
                raise ValueError(f"{provider_id} API-key environment name is not configured")
            if provider.kind in {"ollama", "openai"}:
                return APIKeyCredential(
                    self._secrets,
                    api_key_env,
                    "Authorization",
                    "Bearer ",
                )
            if provider.kind == "gemini":
                return APIKeyCredential(
                    self._secrets,
                    api_key_env,
                    "x-goog-api-key",
                )
            if provider.kind == "anthropic":
                return APIKeyCredential(
                    self._secrets,
                    api_key_env,
                    "x-api-key",
                )
        raise ValueError(f"{provider.kind} does not have an API-key credential mapping")

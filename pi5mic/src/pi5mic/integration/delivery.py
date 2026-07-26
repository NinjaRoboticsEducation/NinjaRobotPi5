"""Delivery-policy helpers for pi5mic."""

from __future__ import annotations

from pi5mic.errors import ConfigError

SUPPORTED_DELIVERY_MODES = (
    "local_only",
    "local_plus_explicit_channel_target",
)


def format_reply_target(
    reply_channel: str | None,
    reply_to: str | None,
    *,
    reply_account: str | None = None,
) -> str | None:
    """Return a short reply-target label when one is fully configured."""
    channel = (reply_channel or "").strip()
    target = (reply_to or "").strip()
    if not channel or not target:
        return None

    display = f"{channel}:{target}"
    account = (reply_account or "").strip()
    if account:
        display += f" (account {account})"
    return display


def validate_delivery_config(
    *,
    delivery_mode: str,
    reply_channel: str | None,
    reply_to: str | None,
) -> None:
    """Validate the selected delivery mode and any required target fields."""
    if delivery_mode not in SUPPORTED_DELIVERY_MODES:
        raise ConfigError(f"Unsupported delivery mode: {delivery_mode}")

    if delivery_mode != "local_plus_explicit_channel_target":
        return

    if not (reply_channel or "").strip():
        raise ConfigError(
            "Delivery mode 'local_plus_explicit_channel_target' requires reply_channel."
        )
    if not (reply_to or "").strip():
        raise ConfigError("Delivery mode 'local_plus_explicit_channel_target' requires reply_to.")


def describe_delivery_mode(
    delivery_mode: str,
    *,
    reply_channel: str | None = None,
    reply_to: str | None = None,
    reply_account: str | None = None,
) -> str:
    """Return a short human-readable delivery summary."""
    if delivery_mode == "local_only":
        return "local only"
    if delivery_mode == "local_plus_explicit_channel_target":
        target = (
            format_reply_target(
                reply_channel,
                reply_to,
                reply_account=reply_account,
            )
            or f"{reply_channel or '?'}:{reply_to or '?'}"
        )
        return f"local + explicit channel target ({target})"
    return delivery_mode

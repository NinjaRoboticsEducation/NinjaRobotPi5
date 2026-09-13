"""Optional, silent colour variations at existing conversational expression hooks."""

from hashlib import sha256

from .behavior_models import FaceOperation

# Same face, meaning, duration and brightness ceiling. No state/privacy/warning
# cues, named definitions, sounds or movement are varied.
VARIED_FACES = frozenset({"happy", "laughing", "exciting", "shy"})


def vary_face(source: FaceOperation, *, enabled: bool, request_id: str) -> FaceOperation:
    """Select once by a non-private request token; unchanged source is fallback."""
    if not enabled or source.expression not in VARIED_FACES:
        return source
    # Only the reviewed standard palette is varied. Custom assets stay exact.
    palette = {"happy": ("#FFD700", "#EFC700"), "shy": ("#FF69B4", "#EF59A4")}
    original, accent = palette.get(source.expression, ("#00BFFF", "#00AEDF"))
    if source.foreground != "#FFFFFF" or source.accent != original:
        return source
    choice = sha256(f"{source.expression}:{request_id}".encode()).digest()[0] % 2
    if choice == 0:
        return source
    return source.model_copy(update={"foreground": "#E8F4FF", "accent": accent})

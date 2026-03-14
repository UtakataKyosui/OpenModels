from __future__ import annotations

from .adapter import AdapterError, BackendAdapter
from .drizzle import DRIZZLE_PG_ADAPTER


ADAPTERS: dict[str, BackendAdapter] = {
    DRIZZLE_PG_ADAPTER.key: DRIZZLE_PG_ADAPTER,
}


def get_adapter(target: str) -> BackendAdapter:
    try:
        return ADAPTERS[target]
    except KeyError as exc:
        supported = ", ".join(sorted(ADAPTERS))
        raise AdapterError(
            f"Unknown adapter target '{target}'. Supported targets: {supported}."
        ) from exc


def list_adapters() -> list[BackendAdapter]:
    return [ADAPTERS[key] for key in sorted(ADAPTERS)]

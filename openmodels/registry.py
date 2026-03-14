from __future__ import annotations

from .adapter import AdapterError, BackendAdapter
from .drizzle import DRIZZLE_PG_ADAPTER
from .seaorm import SEAORM_RUST_ADAPTER


ADAPTERS: dict[str, BackendAdapter] = {
    DRIZZLE_PG_ADAPTER.key: DRIZZLE_PG_ADAPTER,
    SEAORM_RUST_ADAPTER.key: SEAORM_RUST_ADAPTER,
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

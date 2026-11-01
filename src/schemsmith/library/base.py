"""Module registry: parametric builders with docs, ports and simulator scenarios."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from schemsmith.build import Builder
from schemsmith.core import Region

Vec3 = tuple[int, int, int]


@dataclass
class Param:
    """One module parameter."""

    name: str
    kind: type
    default: Any
    help: str
    minimum: int | None = None
    maximum: int | None = None
    choices: tuple[str, ...] | None = None

    def coerce(self, value: Any) -> Any:
        """Convert and range-check a value (CLI strings included)."""
        try:
            if self.kind is bool:
                v: Any = (
                    value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
                )
            else:
                v = self.kind(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{self.name}: expected {self.kind.__name__}, got {value!r}") from exc
        if self.minimum is not None and v < self.minimum:
            raise ValueError(f"{self.name} must be >= {self.minimum}")
        if self.maximum is not None and v > self.maximum:
            raise ValueError(f"{self.name} must be <= {self.maximum}")
        if self.choices is not None and v not in self.choices:
            raise ValueError(f"{self.name} must be one of {', '.join(self.choices)}")
        return v


@dataclass
class Module:
    """A parametric structure."""

    name: str
    category: str
    summary: str
    params: list[Param]
    builder: Callable[..., Builder]
    ports: Callable[..., dict[str, Vec3]] = field(default=lambda **_: {})
    scenario: Callable[..., dict[str, Any]] | None = None
    notes: str = ""

    def resolve(self, **params: Any) -> dict[str, Any]:
        """Defaults plus given params, validated."""
        known = {p.name: p for p in self.params}
        unknown = set(params) - set(known)
        if unknown:
            raise ValueError(
                f"{self.name}: unknown parameter(s) {', '.join(sorted(unknown))}; "
                f"known: {', '.join(known) or 'none'}"
            )
        out = {p.name: p.default for p in self.params}
        for k, v in params.items():
            out[k] = known[k].coerce(v)
        return out

    def build_shifted(self, **params: Any) -> tuple[Region, Vec3]:
        """Build the module; returns the region and the shift applied to builder coordinates
        (non-zero when parts, e.g. a roof overhang, reach below 0)."""
        values = self.resolve(**params)
        b = self.builder(**values)
        region = b.to_region(name=self.name)
        return region, b.origin_shift

    def build(self, **params: Any) -> Region:
        """Build the module as a region whose minimum corner is (0, 0, 0)."""
        return self.build_shifted(**params)[0]

    def get_ports(self, **params: Any) -> dict[str, Vec3]:
        """Named positions (inputs, outputs) inside the built region."""
        _, (dx, dy, dz) = self.build_shifted(**params)
        return {
            k: (x + dx, y + dy, z + dz)
            for k, (x, y, z) in self.ports(**self.resolve(**params)).items()
        }

    def get_scenario(self, **params: Any) -> dict[str, Any] | None:
        """A simulator script proving the module works, with expectations."""
        if self.scenario is None:
            return None
        return self.scenario(**self.resolve(**params))


MODULES: dict[str, Module] = {}


def register(module: Module) -> Module:
    """Add a module to the catalogue."""
    if module.name in MODULES:
        raise ValueError(f"duplicate module {module.name}")
    MODULES[module.name] = module
    return module


def get_module(name: str) -> Module:
    """Look up a module by name."""
    try:
        return MODULES[name]
    except KeyError:
        raise KeyError(
            f"unknown module {name!r}; available: {', '.join(sorted(MODULES))}"
        ) from None


def base_floor(b: Builder, width: int, length: int, block: str = "minecraft:stone") -> None:
    """A floor layer at y=0 from (0,0) to (width-1, length-1)."""
    b.floor((0, 0), (width - 1, length - 1), 0, block)

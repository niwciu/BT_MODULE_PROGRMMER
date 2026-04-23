from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class FieldKind(str, Enum):
    TEXT = "text"
    COMBO = "combo"
    READONLY = "readonly"


@dataclass(frozen=True)
class ComboOption:
    value: str
    label: str


@dataclass(frozen=True)
class PortConfig:
    baudrate: int
    bytesize: int = 8
    stopbits: float = 1.0
    parity: str = "N"
    timeout: float = 1.0


@dataclass(frozen=True)
class SettingField:
    key: str
    label: str
    kind: FieldKind
    options: tuple[ComboOption, ...] = ()
    placeholder: str = ""
    read_only: bool = False
    helper_text: str = ""
    validator: Callable[[str], None] | None = None


@dataclass
class ConnectionResult:
    detected_config: PortConfig
    matched_baud: int
    probe_response: str
    notes: list[str] = field(default_factory=list)

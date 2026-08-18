from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SystemHealth:
    status: Literal["ok"] = "ok"
    service: Literal["accountant-api"] = "accountant-api"

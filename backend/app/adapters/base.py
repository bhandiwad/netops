"""Hexagonal Port & Adapter Interfaces for Southbound OEM & Northbound ITSM Systems.

For non-telecom engineers:
Every external telecom tool (DWDM controllers like Ciena/Nokia, OTDR test heads
like VIAVI/EXFO, GIS databases like Lepton, BSS systems like Comviva, and ticketing
systems like Jira/ServiceNow) plugs into the platform through these typed interfaces.
Domain logic in `correlation/`, `routing/`, and `spatial/` NEVER constructs vendor
HTTP URLs directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shared.sor_codec import OtdrTrace


class OtdrTraceAdapter(ABC):
    """Port for retrieving binary Telcordia SR-4731 `.sor` traces for a fiber cable."""

    @abstractmethod
    async def fetch_sor_bytes(self, cable_id: str) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    async def fetch_and_parse_sor(self, cable_id: str) -> tuple[OtdrTrace, int] | None:
        raise NotImplementedError


class NorthboundActionAdapter(ABC):
    """Port for executing human-approved remediation actions on ITSM or SDN controllers."""

    @abstractmethod
    async def execute(self, action: dict[str, Any], approved_by: str) -> dict[str, Any]:
        raise NotImplementedError

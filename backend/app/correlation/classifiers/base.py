"""Pluggable `HypothesisClassifier` Strategy Registry.

How non-telecom engineers add a new root-cause classifier:
1. Create a new file in `backend/app/correlation/classifiers/my_classifier.py`.
2. Subclass `HypothesisClassifier` and decorate it with `@register_classifier`.
3. Implement `async def evaluate(self, cluster: CausalCluster, ctx: CorrelationContext) -> RootCauseHypothesis | None`.
4. Import your module in `classifiers/__init__.py`.

The correlation pipeline automatically runs all registered classifiers against each
independent `CausalCluster` and selects the highest-confidence hypothesis!
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Type

from ...adapters.base import OtdrTraceAdapter
from ...schemas.models import CausalCluster, RootCauseHypothesis


@dataclass
class CorrelationContext:
    """Read-only snapshot of normalized inventory & southbound adapters passed to classifiers."""

    inventory: dict[str, Any]
    otdr_adapter: OtdrTraceAdapter


class HypothesisClassifier(ABC):
    """Strategy interface for evaluating a causal alarm cluster."""

    classifier_id: str = "base"
    priority: int = 50  # Higher priority breaks ties when confidence is equal

    @abstractmethod
    async def evaluate(
        self,
        cluster: CausalCluster,
        ctx: CorrelationContext,
    ) -> RootCauseHypothesis | None:
        raise NotImplementedError


CLASSIFIER_REGISTRY: list[HypothesisClassifier] = []


def register_classifier(cls: Type[HypothesisClassifier]) -> Type[HypothesisClassifier]:
    instance = cls()
    if not any(c.classifier_id == instance.classifier_id for c in CLASSIFIER_REGISTRY):
        CLASSIFIER_REGISTRY.append(instance)
        CLASSIFIER_REGISTRY.sort(key=lambda c: c.priority, reverse=True)
    return cls


def normalize_problem_code(code: str) -> str:
    """Normalize multi-vendor TMF642/SNMP problem codes (`DYING-GASP` == `DYING_GASP`)."""
    return (code or "").upper().replace("-", "_").replace(" ", "_")


async def evaluate_cluster_hypotheses(
    cluster: CausalCluster,
    ctx: CorrelationContext,
) -> RootCauseHypothesis:
    candidates: list[RootCauseHypothesis] = []
    for clf in CLASSIFIER_REGISTRY:
        hyp = await clf.evaluate(cluster, ctx)
        if hyp is not None:
            candidates.append(hyp)

    if not candidates:
        lead = cluster.alarms[0]
        node_obj = ctx.inventory.get("nodes", {}).get(lead.node_id) or {}
        return RootCauseHypothesis(
            classifier_id="generic_correlated_fallback",
            root_cause_type="GENERIC_CORRELATED_NETWORK_FAULT",
            root_cause_resource=cluster.anchor_resource_id,
            title=f"Correlated Network Fault on {cluster.anchor_resource_id} ({len(cluster.alarms)} Alarms)",
            confidence=0.70,
            summary=(
                f"Correlated {len(cluster.alarms)} alarm(s) anchored on {cluster.anchor_resource_id}: "
                f"{lead.specific_problem} ({lead.probable_cause})."
            ),
            fault_location={
                "lat": float(node_obj.get("lat", 0.0)),
                "lon": float(node_obj.get("lon", 0.0)),
                "dispatch_verdict": "INVESTIGATE ANCHOR RESOURCE TELEMETRY",
            },
            suppress_default_splice_dispatch=True,
        )

    candidates.sort(key=lambda h: h.confidence, reverse=True)
    return candidates[0]

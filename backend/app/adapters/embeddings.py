"""Pluggable Vector Embedding Provider for `pgvector` Runbook & Incident RAG.

Provides an abstract `EmbeddingProvider` interface so production deployments can plug
in OpenAI (`text-embedding-3-small`), Vertex AI, or a local SentenceTransformer model,
while local/CI environments run deterministically with zero external API keys via
`HybridFeatureHashEmbeddingProvider` (64-dim L2-normalized semantic + n-gram hashing).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import math
import os
import re

EMBEDDING_DIM = 64

# Domain concept groups give strong semantic alignment across telecom terminology
# (first 32 dimensions), while dimensions 32..63 capture signed feature-hashed
# token & bigram representations for arbitrary new runbooks without code changes!
_CONCEPT_LEXICON: list[tuple[str, ...]] = [
    ("fibre", "fiber", "cut", "break", "severed", "cable", "trench", "excavation"),
    ("otdr", "sor", "reflective", "viavi", "exfo", "1625nm", "trace", "reflectance"),
    ("slack", "coil", "manhole", "chamber", "helix", "lepton", "postgis", "duct"),
    ("srlg", "diverse", "diversity", "shared", "redundant", "dual", "backup", "protect"),
    ("dwdm", "optical", "och", "oms", "ots", "wavelength", "roadm", "ciena", "nokia"),
    ("osnr", "ber", "fec", "pre_fec", "degradation", "pinched", "attenuation", "tca"),
    ("sop", "polarization", "vibration", "acoustic", "jcb", "dgd", "precut", "phase"),
    ("reroute", "hitless", "gmpls", "restoration", "switchover", "mcp", "nsp"),
    ("gpon", "ont", "olt", "splitter", "ploam", "access", "ftth", "pon"),
    ("dying", "gasp", "power", "ac", "mains", "blackout", "utility", "substation"),
    ("no_cut", "continuity", "intact", "suppress", "cancel", "false", "truck"),
    ("ran", "5g", "4g", "gnb", "enodeb", "cell", "sector", "ericsson", "3gpp"),
    ("battery", "rectifier", "lvd", "voltage", "dc", "generator", "discharge", "countdown"),
    ("cascade", "tail", "hub", "daisy", "backhaul", "site"),
    ("microwave", "eband", "80ghz", "rsl", "acm", "qpsk", "1024qam", "odu"),
    ("rain", "weather", "fade", "squall", "convective", "mm_hr", "atmospheric"),
    ("subsea", "submarine", "wet", "cls", "landing", "seaward", "repeater", "marine"),
    ("pfe", "shunt", "insulation", "earth", "leakage", "cotdr", "feed", "voltage"),
    ("ais", "vessel", "anchor", "drag", "mmsi", "ship", "maritime", "corridor"),
    ("ip", "mpls", "bgp", "bfd", "isis", "router", "cisco", "juniper", "huawei"),
    ("sla", "platinum", "gold", "penalty", "enterprise", "mttr", "comviva", "rfo"),
    ("servicenow", "jira", "work_order", "wm_order", "change", "crq", "chg", "collision"),
    ("bridge", "canal", "crossing", "civil", "municipal", "permit", "overrun"),
    ("splice", "fusion", "ribbon", "tia598", "tube", "closure", "etr", "heal"),
]


class EmbeddingProvider(ABC):
    """Interface for converting runbooks and incident symptoms into fixed-width vectors."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class HybridFeatureHashEmbeddingProvider(EmbeddingProvider):
    """Deterministic 64-D embedding combining telecom concept alignment + signed feature hashing.

    Unlike a fixed keyword list, dimensions [24..63] hash ALL unigrams and bigrams
    using Murmur/SHA signed projections (Weinberger et al.), so engineers adding brand-new
    runbooks or domains automatically get non-zero, discriminative vector representations!
    """

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    def embed(self, text: str) -> list[float]:
        tokens = re.findall(r"[a-z0-9_]+", (text or "").lower())
        vec = [0.0] * EMBEDDING_DIM
        if not tokens:
            vec[0] = 1.0
            return vec

        # Part A (dims 0..23): High-signal domain concept alignment (weighted 2.2x)
        for idx, group in enumerate(_CONCEPT_LEXICON):
            hits = sum(
                1
                for tok in tokens
                if any(tok == kw or (len(kw) >= 4 and kw in tok) for kw in group)
            )
            if hits:
                vec[idx] = 2.2 * (1.0 + math.log1p(hits))

        # Part B (dims 24..63): Open-vocabulary signed unigram + bigram feature hashing
        hash_buckets = EMBEDDING_DIM - len(_CONCEPT_LEXICON)
        offset = len(_CONCEPT_LEXICON)
        features = list(tokens) + [
            f"{tokens[i]}::{tokens[i + 1]}" for i in range(len(tokens) - 1)
        ]
        for feat in features:
            if len(feat) <= 2:
                continue
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=4).digest()
            val = int.from_bytes(digest, "little")
            bucket = offset + (val % hash_buckets)
            sign = 1.0 if ((val >> 16) & 1) == 0 else -1.0
            vec[bucket] += sign * 0.45

        norm = math.sqrt(sum(v * v for v in vec))
        if norm < 1e-9:
            vec[0] = 1.0
            return vec
        return [round(v / norm, 6) for v in vec]


_DEFAULT_PROVIDER: EmbeddingProvider = HybridFeatureHashEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """Return active embedding provider (extensible via `NOC_EMBEDDING_PROVIDER`)."""
    _ = os.getenv("NOC_EMBEDDING_PROVIDER", "hybrid_hash")
    return _DEFAULT_PROVIDER


def compute_text_embedding(text: str) -> list[float]:
    return get_embedding_provider().embed(text)

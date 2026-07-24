"""Duplicate detection — flags, never deletes.

Two signals:
  * exact  — identical bytes of the *original* file (sha256).
  * near   — high Jaccard similarity of OCR'd text shingles, catching
             re-scans of the same document that are not byte-identical.

Documents are grouped: every doc gets a ``duplicate_group`` id (or None) and
a relationship label so the index can surface them for human review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _shingles(tokens: list[str], k: int = 5) -> set[str]:
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass
class DupDoc:
    id: str
    sha256: str
    text: str


def find_duplicates(docs: list[DupDoc], near_threshold: float = 0.80):
    """Return ``{doc_id: {"group": int|None, "kind": str, "matches": [ids]}}``."""
    n = len(docs)
    shingle_sets = [_shingles(_tokens(d.text)) for d in docs]

    # Union-find over duplicate relationships.
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    kinds: dict[int, str] = {}
    match_ids: dict[int, set[str]] = {i: set() for i in range(n)}

    for i in range(n):
        for j in range(i + 1, n):
            exact = docs[i].sha256 == docs[j].sha256 and docs[i].sha256 != ""
            sim = _jaccard(shingle_sets[i], shingle_sets[j])
            if exact or sim >= near_threshold:
                union(i, j)
                label = "exact" if exact else "near"
                kinds[i] = "exact" if exact else kinds.get(i, "near")
                kinds[j] = "exact" if exact else kinds.get(j, "near")
                match_ids[i].add(docs[j].id)
                match_ids[j].add(docs[i].id)

    # Assign stable group numbers only to roots that actually have members > 1.
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    result: dict[str, dict] = {}
    group_no = 0
    root_to_no: dict[int, int] = {}
    for root, members in groups.items():
        if len(members) > 1:
            group_no += 1
            root_to_no[root] = group_no

    for i in range(n):
        root = find(i)
        gid = root_to_no.get(root)
        result[docs[i].id] = {
            "group": gid,
            "kind": kinds.get(i, "") if gid else "",
            "matches": sorted(match_ids[i]),
        }
    return result

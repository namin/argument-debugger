
# -*- coding: utf-8 -*-
"""
AF semantics utilities: grounded extension, status helpers.

All stdlib.
"""

from __future__ import annotations
from typing import Set, Tuple, Dict

def grounded_extension(nodes: Set[str], attacks: Set[Tuple[str, str]]) -> Set[str]:
    attackers_of: Dict[str, Set[str]] = {n: set() for n in nodes}
    for a, b in attacks:
        attackers_of[b].add(a)

    def defended_by(E: Set[str], x: str) -> bool:
        for a in attackers_of.get(x, set()):
            if not any((y, a) in attacks for y in E):
                return False
        return True

    E: Set[str] = set()
    changed = True
    while changed:
        changed = False
        newE = set(E)
        for x in nodes:
            if defended_by(E, x) and x not in E:
                newE.add(x); changed = True
        E = newE
    return E

def status(nodes: Set[str], attacks: Set[Tuple[str, str]], target: str) -> str:
    E = grounded_extension(nodes, attacks)
    return "Accepted" if target in E else "Not accepted"

def attackers_of(attacks: Set[Tuple[str, str]], x: str):
    return {a for (a, b) in attacks if b == x}

def unattacked(attacks: Set[Tuple[str, str]], S: Set[str]):
    def has_attacker(n: str) -> bool:
        return any((a, n) in attacks for (a, _) in attacks)
    return {u for u in S if not has_attacker(u)}

#!/usr/bin/env python3
"""
baf.py — Minimal Bipolar Argumentation Framework (BAF) core

A unified, principled data model to hold both SUPPORT and ATTACK relations
so that structure extractors (e.g., ad.py) and AF solvers (e.g., af_clingo.py)
can interoperate.

Main ideas
----------
- Keep a single graph with nodes (claims or argument blocks), SUPPORT edges,
  and ATTACK edges (optionally typed: rebut/undercut/undermine).
- When you want Dung-style semantics, *collapse* the BAF to a plain AF:
    supported attack:  x ⇒ y  &  y → z   ⇒   x → z
    secondary attack:  x → y  &  y ⇒ z   ⇒   x → z
  (⇒ support, → attack)
- Provenance and confidence are tracked per edge (e.g., "exp", "heu", "llm", "struct").

This module is intentionally lightweight and dependency-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, List, Optional, Iterable
import re

# ----------------------
# Data structures
# ----------------------

@dataclass
class NodeInfo:
    """Information about a node in the BAF."""
    text: str
    type: str = "claim"  # 'claim' | 'premise' | 'intermediate' | 'conclusion' | 'argument'
    meta: Dict = field(default_factory=dict)


@dataclass
class BAF:
    """
    Bipolar Argumentation Framework.
    Nodes are identified by string IDs (unique within a BAF).
    """
    nodes: Dict[str, NodeInfo] = field(default_factory=dict)
    # Support edges: (from, to)
    support: Set[Tuple[str, str]] = field(default_factory=set)
    # Attack edges: (from, to, kind) where kind in {'attack','rebut','undercut','undermine'}
    attack: Set[Tuple[str, str, str]] = field(default_factory=set)
    # Equivalence classes of node IDs
    equiv: List[Set[str]] = field(default_factory=list)

    # Provenance & confidence
    prov_support: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)   # tags per support edge
    prov_attack: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)    # tags per attack (ignores kind)
    score_support: Dict[Tuple[str, str], float] = field(default_factory=dict)      # optional confidence in [0,1]
    score_attack: Dict[Tuple[str, str], float] = field(default_factory=dict)       # optional confidence in [0,1]

    # ---------- Node and edge management ----------

    def add_node(self, node_id: str, text: str, type: str = "claim", **meta) -> None:
        if node_id in self.nodes:
            # merge meta and keep original text if identical; else store alt_texts
            n = self.nodes[node_id]
            if text and text != n.text:
                n.meta.setdefault("alt_texts", []).append(text)
            n.meta.update(meta)
            if type and n.type != type:
                n.meta.setdefault("alt_types", []).append(type)
        else:
            self.nodes[node_id] = NodeInfo(text=text or "", type=type or "claim", meta=dict(meta))

    def add_support(self, u: str, v: str, tags: Optional[Iterable[str]] = None, score: Optional[float] = None) -> None:
        self.support.add((u, v))
        if tags:
            self.prov_support.setdefault((u, v), [])
            for t in tags:
                if t not in self.prov_support[(u, v)]:
                    self.prov_support[(u, v)].append(t)
        if score is not None:
            self.score_support[(u, v)] = float(score)

    def add_attack(self, u: str, v: str, kind: str = "attack",
                   tags: Optional[Iterable[str]] = None, score: Optional[float] = None) -> None:
        kind = kind or "attack"
        self.attack.add((u, v, kind))
        k = (u, v)
        if tags:
            self.prov_attack.setdefault(k, [])
            for t in tags:
                if t not in self.prov_attack[k]:
                    self.prov_attack[k].append(t)
        if score is not None:
            self.score_attack[k] = float(score)

    # ---------- Utilities ----------

    def merge(self, other: "BAF", rename_conflicts: bool = False, prefix: str = "X") -> "BAF":
        """
        Merge `other` into self in-place. If node ID conflicts and texts differ,
        either rename the incoming node (if rename_conflicts), or keep both texts
        in alt_texts.
        """
        # Nodes
        for nid, info in other.nodes.items():
            if nid not in self.nodes:
                self.nodes[nid] = NodeInfo(text=info.text, type=info.type, meta=dict(info.meta))
            else:
                my = self.nodes[nid]
                if info.text and info.text != my.text:
                    if rename_conflicts:
                        new_id = self._fresh_id(prefix, nid)
                        self.nodes[new_id] = NodeInfo(text=info.text, type=info.type, meta=dict(info.meta))
                        # remap edges referencing nid -> new_id for other's edges
                        self._remap_incoming_from_other(other, old_id=nid, new_id=new_id)
                        continue
                    else:
                        my.meta.setdefault("alt_texts", []).append(info.text)
                # merge meta
                for k, v in info.meta.items():
                    if k not in my.meta:
                        my.meta[k] = v

        # Edges
        for (u, v) in other.support:
            self.add_support(u, v, tags=other.prov_support.get((u, v)), score=other.score_support.get((u, v)))
        for (u, v, kind) in other.attack:
            self.add_attack(u, v, kind=kind, tags=other.prov_attack.get((u, v)), score=other.score_attack.get((u, v)))

        # Equivalences
        self.equiv.extend([set(S) for S in other.equiv])
        return self

    def _fresh_id(self, prefix: str, base: str) -> str:
        i = 1
        while True:
            cand = f"{prefix}{i}.{base}"
            if cand not in self.nodes:
                return cand
            i += 1

    def _remap_incoming_from_other(self, other: "BAF", old_id: str, new_id: str):
        # Update edges inside `other` that reference 'old_id' to 'new_id' (used only during merge)
        supp = set()
        for (u, v) in other.support:
            if u == old_id: u = new_id
            if v == old_id: v = new_id
            supp.add((u, v))
        other.support = supp

        att = set()
        for (u, v, k) in other.attack:
            if u == old_id: u = new_id
            if v == old_id: v = new_id
            att.add((u, v, k))
        other.attack = att

        # Provenance remap
        def remap_dict(d):
            out = {}
            for (u, v), tags in d.items():
                uu = new_id if u == old_id else u
                vv = new_id if v == old_id else v
                out[(uu, vv)] = tags
            return out
        other.prov_support = remap_dict(other.prov_support)
        other.prov_attack = remap_dict(other.prov_attack)
        other.score_support = remap_dict(other.score_support)
        other.score_attack = remap_dict(other.score_attack)

    # ---------- Equivalence compression ----------

    def compress_equivalences(self) -> Dict[str, str]:
        """
        Compress equivalence classes into a representative ID.
        Returns a mapping rep_of: old_id -> rep_id.
        """
        rep_of = {nid: nid for nid in self.nodes}
        # Union-find like simple approach
        for group in self.equiv:
            if not group: continue
            rep = sorted(group)[0]
            for nid in group:
                rep_of[nid] = rep

        # Rebuild nodes & edges
        new_nodes: Dict[str, NodeInfo] = {}
        for nid, info in self.nodes.items():
            rep = rep_of[nid]
            if rep not in new_nodes:
                new_nodes[rep] = NodeInfo(text=info.text, type=info.type, meta=dict(info.meta))
            else:
                # merge metadata/texts
                if info.text and info.text != new_nodes[rep].text:
                    new_nodes[rep].meta.setdefault("alt_texts", []).append(info.text)
                for k, v in info.meta.items():
                    if k not in new_nodes[rep].meta:
                        new_nodes[rep].meta[k] = v
        self.nodes = new_nodes

        def remap_pairs(pairs: Iterable[Tuple[str, str]]) -> Set[Tuple[str, str]]:
            out = set()
            for (u, v) in pairs:
                out.add((rep_of.get(u, u), rep_of.get(v, v)))
            return out

        def remap_triples(triples: Iterable[Tuple[str, str, str]]) -> Set[Tuple[str, str, str]]:
            out = set()
            for (u, v, k) in triples:
                out.add((rep_of.get(u, u), rep_of.get(v, v), k))
            return out

        self.support = remap_pairs(self.support)
        self.attack = remap_triples(self.attack)

        # Remap provenance
        self.prov_support = { (rep_of.get(u,u), rep_of.get(v,v)): tags
                              for (u,v), tags in self.prov_support.items() }
        self.prov_attack  = { (rep_of.get(u,u), rep_of.get(v,v)): tags
                              for (u,v), tags in self.prov_attack.items() }
        self.score_support = { (rep_of.get(u,u), rep_of.get(v,v)): sc
                               for (u,v), sc in self.score_support.items() }
        self.score_attack  = { (rep_of.get(u,u), rep_of.get(v,v)): sc
                               for (u,v), sc in self.score_attack.items() }
        return rep_of

    # ---------- Collapse to AF ----------

    @staticmethod
    def _sanitize_atom(s: str) -> str:
        """Portable, deterministic atom name from an ID (no external deps)."""
        s0 = s.strip().lower()
        s1 = re.sub(r"[^a-z0-9_]+", "_", s0)
        if not re.match(r"^[a-z]", s1):
            s1 = "n_" + s1
        s1 = re.sub(r"__+", "_", s1).strip("_")
        return s1 or "n"

    def collapse_to_af(self,
                       include_supported: bool = True,
                       include_secondary: bool = True) -> Tuple[List[str], Set[Tuple[str, str]], Dict[str, str], Dict[str, str]]:
        """
        Compute the AF (atoms, attacks) induced by this BAF.
        Returns (atoms, attacks, id2atom, atom2id).
        """
        # Work on a copy so we can safely compress equivalences if present
        # (Users may call compress_equivalences() explicitly instead.)
        # For now, just derive attacks.
        base_attacks: Set[Tuple[str, str]] = set((u, v) for (u, v, _k) in self.attack)
        supp = set(self.support)

        # Derive supported/secondary attacks until fixpoint
        if include_supported or include_secondary:
            changed = True
            while changed:
                changed = False
                new_edges: Set[Tuple[str, str]] = set()

                if include_supported:
                    # supported: x ⇒ y and y → z  => x → z
                    # For each support (x,y), find all attacks (y,z)
                    by_src_support: Dict[str, Set[str]] = {}
                    for (x, y) in supp:
                        by_src_support.setdefault(x, set()).add(y)
                    by_src_attack: Dict[str, Set[str]] = {}
                    for (y, z) in base_attacks:
                        by_src_attack.setdefault(y, set()).add(z)
                    for x, ys in by_src_support.items():
                        for y in ys:
                            for z in by_src_attack.get(y, set()):
                                if (x, z) not in base_attacks:
                                    new_edges.add((x, z))

                if include_secondary:
                    # secondary: x → y and y ⇒ z  => x → z
                    by_src_attack2: Dict[str, Set[str]] = {}
                    for (x, y) in base_attacks:
                        by_src_attack2.setdefault(x, set()).add(y)
                    by_src_support2: Dict[str, Set[str]] = {}
                    for (y, z) in supp:
                        by_src_support2.setdefault(y, set()).add(z)
                    for x, ys in by_src_attack2.items():
                        for y in ys:
                            for z in by_src_support2.get(y, set()):
                                if (x, z) not in base_attacks:
                                    new_edges.add((x, z))

                if new_edges:
                    base_attacks |= new_edges
                    changed = True

        # Prepare atoms/mapping
        ids = sorted(self.nodes.keys())
        id2atom: Dict[str, str] = {}
        used: Set[str] = set()
        for i in ids:
            a = self._sanitize_atom(i)
            k = a; j = 1
            while k in used:
                j += 1; k = f"{a}_{j}"
            id2atom[i] = k; used.add(k)
        atom2id = {v: k for k, v in id2atom.items()}
        atoms = [id2atom[i] for i in ids]

        attacks_atoms = set((id2atom[u], id2atom[v]) for (u, v) in base_attacks if u in id2atom and v in id2atom)
        return atoms, attacks_atoms, id2atom, atom2id

    # ---------- Export helpers ----------

    def to_apx(self,
               include_supported: bool = True,
               include_secondary: bool = True) -> str:
        atoms, attacks, id2atom, _ = self.collapse_to_af(include_supported=include_supported,
                                                         include_secondary=include_secondary)
        lines = []
        lines.append("% APX from BAF")
        lines.append("% Nodes: ID == APX atom :: text")
        for nid, atom in id2atom.items():
            txt = (self.nodes.get(nid).text or "").replace('"', '\\"').replace("\n", " ")
            lines.append(f'%   {nid} == {atom} :: {txt[:72]}')
        for _, atom in sorted(id2atom.items(), key=lambda kv: kv[1]):
            lines.append(f"arg({atom}).")
        lines.append("% Attacks (collapsed)")
        for (u, v) in sorted(attacks):
            lines.append(f"att({u},{v}).")
        return "\n".join(lines) + "\n"

    def to_dot(self,
               show_implied: bool = True,
               include_supported: bool = True,
               include_secondary: bool = True) -> str:
        """Simple DOT for debugging (support edges dashed; attacks solid)."""
        atoms, attacks, id2atom, _ = self.collapse_to_af(include_supported=include_supported,
                                                         include_secondary=include_secondary)
        # Compute base attacks to distinguish implied vs base
        base_att = set((u, v) for (u, v, _k) in self.attack)
        base_att_atoms = set((id2atom[u], id2atom[v]) for (u, v) in base_att if u in id2atom and v in id2atom)
        supp_atoms = set((id2atom[u], id2atom[v]) for (u, v) in self.support if u in id2atom and v in id2atom)

        out = []
        out.append("digraph BAF {")
        out.append('  rankdir=LR;')
        out.append('  node [shape=box, style="rounded,filled", fillcolor="#f8f9fb"];')
        for nid, atom in id2atom.items():
            label = nid.replace('"','\\"')
            out.append(f'  "{atom}" [label="{label}\\n({atom})"];')
        # support
        for (u,v) in sorted(supp_atoms):
            out.append(f'  "{u}" -> "{v}" [style="dashed", color="#4ae39b"];')
        # attacks
        for (u,v) in sorted(attacks):
            base = (u,v) in base_att_atoms
            if base or show_implied:
                color = "#ff6b6b" if base else "#ffb3b3"
                out.append(f'  "{u}" -> "{v}" [color="{color}", penwidth="{2 if base else 1.5}"];')
        out.append("}")
        return "\n".join(out)

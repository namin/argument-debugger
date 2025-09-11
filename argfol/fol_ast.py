
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Union, Dict, Optional, Iterable

# -------- Terms --------
@dataclass(frozen=True)
class Var:
    name: str  # logical variable (TPTP requires variables start with uppercase)

@dataclass(frozen=True)
class Const:
    name: str  # constant symbol (lowercase in TPTP by convention)

@dataclass(frozen=True)
class Func:
    name: str
    args: List['Term']

Term = Union[Var, Const, Func]

# -------- Atoms --------
@dataclass(frozen=True)
class Pred:
    name: str
    args: List[Term]

@dataclass(frozen=True)
class Eq:
    left: Term
    right: Term

Atom = Union[Pred, Eq]

# -------- Formulas --------
class Formula:  # opaque base for type hints
    pass

@dataclass(frozen=True)
class Not(Formula):
    phi: Formula

@dataclass(frozen=True)
class And(Formula):
    left: Formula
    right: Formula

@dataclass(frozen=True)
class Or(Formula):
    left: Formula
    right: Formula

@dataclass(frozen=True)
class Implies(Formula):
    left: Formula
    right: Formula

@dataclass(frozen=True)
class Iff(Formula):
    left: Formula
    right: Formula

@dataclass(frozen=True)
class Forall(Formula):
    vars: List[Var]
    body: Formula

@dataclass(frozen=True)
class Exists(Formula):
    vars: List[Var]
    body: Formula

@dataclass(frozen=True)
class AtomF(Formula):
    atom: Atom

# Helper constructors
def pred(name: str, *args: Term) -> Pred:
    return Pred(name, list(args))

def func(name: str, *args: Term) -> Func:
    return Func(name, list(args))

def eq(l: Term, r: Term) -> Eq:
    return Eq(l, r)

def A(atom: Atom) -> AtomF:
    return AtomF(atom)

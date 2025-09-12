
from typing import Set, Tuple, Dict

def grounded_extension(nodes: Set[str], attacks: Set[Tuple[str,str]]) -> Set[str]:
    attackers_of={n:set() for n in nodes}
    for a,b in attacks:
        attackers_of[b].add(a)
    def defended(E, x):
        for a in attackers_of.get(x,set()):
            if not any((y,a) in attacks for y in E):
                return False
        return True
    E=set(); changed=True
    while changed:
        changed=False; new=set(E)
        for x in nodes:
            if defended(E,x) and x not in E:
                new.add(x); changed=True
        E=new
    return E

def status(nodes: Set[str], attacks: Set[Tuple[str,str]], target: str) -> str:
    return "Accepted" if target in grounded_extension(nodes, attacks) else "Not accepted"

def attackers_of(attacks: Set[Tuple[str,str]], x: str):
    return {a for (a,b) in attacks if b==x}

def unattacked(attacks: Set[Tuple[str,str]], S: Set[str]):
    def has_attacker(n): return any((a,n) in attacks for (a,_) in attacks)
    return {u for u in S if not has_attacker(u)}

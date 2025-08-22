#!/usr/bin/env python3
"""
Debate Frontier Analyzer - Extends ad.py to detect unexplored areas in debates
Identifies structural gaps, undefended positions, and asymmetric development
"""

import json
import clingo
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Literal
from google import genai
from google.genai import types
import os
from pydantic import BaseModel, Field
from ad import init_llm_client  # Import from ad.py

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ClaimModel(BaseModel):
    id: str = Field(description="Claim identifier (e.g., c1, c2)")
    content: str = Field(description="The actual claim text")
    type: str = Field(description="Type: premise, intermediate, conclusion, evidence, or assertion")

class RelationModel(BaseModel):
    from_claim: str = Field(description="Source claim ID")
    to_claim: str = Field(description="Target claim ID")
    relation_type: str = Field(description="Type: supports, attacks, or contradicts")
    strength: Optional[str] = Field(default="medium", description="Strength: weak, medium, or strong")

class ArgumentStructure(BaseModel):
    """Structured output for debate parsing"""
    claims: List[ClaimModel] = Field(description="All claims in the argument")
    relations: List[RelationModel] = Field(description="How claims relate to each other")
    main_claim: Optional[str] = Field(description="The central claim being debated")
    
# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Claim:
    id: str
    content: str
    type: str
    depth: int = 0  # How many levels from main claim

@dataclass
class Relation:
    from_claim: str
    to_claim: str
    relation_type: str  # supports, attacks, contradicts
    strength: str = "medium"

@dataclass 
class Frontier:
    type: Literal["undefended_attack", "asymmetric", "missing_evidence", 
                  "unexplored_implication", "logical_gap", "orphaned_claim"]
    location: str  # Claim ID or relation
    description: str
    suggestion: str
    priority: Literal["high", "medium", "low"]

@dataclass
class Debate:
    claims: List[Claim]
    relations: List[Relation]
    main_claim: Optional[str]
    frontiers: List[Frontier] = field(default_factory=list)

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

llm_model = "gemini-2.0-flash-exp"
llm_config = types.GenerateContentConfig(
    temperature=0.1,
    response_mime_type="application/json",
    response_schema=ArgumentStructure
)

# ============================================================================
# DEBATE PARSER
# ============================================================================

class DebateParser:
    def __init__(self):
        self.client = init_llm_client()
    
    def parse_debate(self, text: str) -> Debate:
        """Parse natural language debate into structured format"""
        
        prompt = f"""
        Analyze this debate/argument and extract its structure.
        
        For each claim, identify:
        - A unique ID (c1, c2, etc.)
        - The claim content
        - Type: premise (starting point), conclusion (what's being argued), 
                evidence (supporting data), assertion (unsupported claim)
        
        For relations between claims:
        - Identify which claims support, attack, or contradict others
        - Rate strength as weak/medium/strong
        
        Identify the main claim being debated (usually what the argument is about).
        
        Debate text:
        {text}
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
        )
        
        # Parse structured response
        data = ArgumentStructure.model_validate_json(response.text)
        
        # Convert to internal representation
        claims = [Claim(c.id, c.content, c.type) for c in data.claims]
        relations = [Relation(r.from_claim, r.to_claim, r.relation_type, r.strength) 
                    for r in data.relations]
        
        return Debate(claims, relations, data.main_claim)

# ============================================================================
# FRONTIER DETECTION
# ============================================================================

def build_frontier_asp(debate: Debate) -> str:
    """Build ASP program with frontier detection rules"""
    
    program = "% Claims\n"
    for claim in debate.claims:
        program += f'claim("{claim.id}").\n'
        program += f'claim_type("{claim.id}", "{claim.type}").\n'
        if debate.main_claim == claim.id:
            program += f'main_claim("{claim.id}").\n'
    
    program += "\n% Relations\n"
    for rel in debate.relations:
        if rel.relation_type == "supports":
            program += f'supports("{rel.from_claim}", "{rel.to_claim}").\n'
        elif rel.relation_type == "attacks":
            program += f'attacks("{rel.from_claim}", "{rel.to_claim}").\n'
        elif rel.relation_type == "contradicts":
            program += f'contradicts("{rel.from_claim}", "{rel.to_claim}").\n'
    
    program += """
    
% ============================================================================
% FRONTIER DETECTION RULES
% ============================================================================

% Undefended attack: Attack is not countered
undefended_attack(Target, Attacker) :-
    attacks(Attacker, Target),
    not attacks(_, Attacker),
    not supports(_, Attacker).

% Orphaned claim: Not connected to debate structure
orphaned_claim(C) :-
    claim(C),
    not supports(C, _),
    not attacks(C, _),
    not supports(_, C),
    not attacks(_, C).

% Missing evidence: Assertion or evidence claim without support
missing_evidence(C) :-
    claim(C),
    claim_type(C, "assertion"),
    not supports(_, C).

missing_evidence(C) :-
    claim(C),
    claim_type(C, "evidence"),
    not supports(_, C).

% Critical unsupported: Claim supporting main claim lacks support
critical_unsupported(C) :-
    supports(C, Main),
    main_claim(Main),
    not supports(_, C).

% Asymmetric development - count support depth
support_depth(C, D) :-
    claim(C),
    D = #count{X : supports_trans(X, C)}.

attack_depth(C, D) :-
    claim(C),
    D = #count{X : attack_chain(X, C)}.

asymmetric(C) :-
    main_claim(C),
    support_depth(C, SD),
    attack_depth(C, AD),
    |SD - AD| > 1.

% Transitive support
supports_trans(X, Y) :- supports(X, Y).
supports_trans(X, Z) :- supports(X, Y), supports_trans(Y, Z).

% Attack chains
attack_chain(X, Y) :- attacks(X, Y).
attack_chain(X, Z) :- attacks(X, Y), supports(Y, Z).

% One-sided branch: Only pro or con developed
one_sided_pro(C) :-
    main_claim(C),
    supports(_, C),
    not attacks(_, C).

one_sided_con(C) :-
    main_claim(C),
    attacks(_, C),
    not supports(_, C).

#show undefended_attack/2.
#show orphaned_claim/1.
#show missing_evidence/1.
#show critical_unsupported/1.
#show asymmetric/1.
#show one_sided_pro/1.
#show one_sided_con/1.
    """
    
    return program

def detect_frontiers(debate: Debate, debug: bool = False) -> List[Frontier]:
    """Detect exploration frontiers using ASP"""
    
    asp_program = build_frontier_asp(debate)
    
    if debug:
        print("\n=== ASP PROGRAM ===")
        print(asp_program)
        print("==================\n")
    
    # Solve with clingo
    control = clingo.Control(["--warn=none"])
    control.add("base", [], asp_program)
    control.ground([("base", [])])
    
    frontiers = []
    
    with control.solve(yield_=True) as handle:
        for model in handle:
            if debug:
                print("Model atoms:", [str(atom) for atom in model.symbols(shown=True)])
            for atom in model.symbols(shown=True):
                frontier = parse_frontier_atom(atom, debate)
                if frontier:
                    frontiers.append(frontier)
            break  # Only need first model
    
    return prioritize_frontiers(frontiers)

def parse_frontier_atom(atom, debate: Debate) -> Optional[Frontier]:
    """Convert ASP atom to Frontier object"""
    
    if atom.name == "undefended_attack":
        target = str(atom.arguments[0]).strip('"')
        attacker = str(atom.arguments[1]).strip('"')
        
        # Find claim contents
        target_claim = next((c for c in debate.claims if c.id == target), None)
        attacker_claim = next((c for c in debate.claims if c.id == attacker), None)
        
        return Frontier(
            type="undefended_attack",
            location=target,
            description=f"'{attacker_claim.content[:50]}...' attacks this but is unaddressed",
            suggestion="Defend against this criticism or acknowledge its validity",
            priority="high"
        )
    
    elif atom.name == "orphaned_claim":
        claim_id = str(atom.arguments[0]).strip('"')
        claim = next((c for c in debate.claims if c.id == claim_id), None)
        
        return Frontier(
            type="orphaned_claim",
            location=claim_id,
            description=f"'{claim.content[:50]}...' is disconnected from the debate",
            suggestion="Connect this claim to the main argument or remove it",
            priority="low"
        )
    
    elif atom.name == "missing_evidence":
        claim_id = str(atom.arguments[0]).strip('"')
        claim = next((c for c in debate.claims if c.id == claim_id), None)
        
        return Frontier(
            type="missing_evidence",
            location=claim_id,
            description=f"'{claim.content[:50]}...' needs supporting evidence",
            suggestion="Provide data, studies, or examples to support this claim",
            priority="medium"
        )
    
    elif atom.name == "critical_unsupported":
        claim_id = str(atom.arguments[0]).strip('"')
        claim = next((c for c in debate.claims if c.id == claim_id), None)
        
        return Frontier(
            type="missing_evidence",
            location=claim_id,
            description=f"Key claim '{claim.content[:50]}...' lacks support",
            suggestion="This directly supports your main point - strengthen it with evidence",
            priority="high"
        )
    
    elif atom.name == "asymmetric":
        claim_id = str(atom.arguments[0]).strip('"')
        
        return Frontier(
            type="asymmetric",
            location=claim_id,
            description="One side of this debate is more developed than the other",
            suggestion="Balance the argument by developing the weaker side",
            priority="medium"
        )
    
    elif atom.name == "one_sided_pro":
        claim_id = str(atom.arguments[0]).strip('"')
        
        return Frontier(
            type="asymmetric",
            location=claim_id,
            description="Only supporting arguments provided, no counterarguments",
            suggestion="Consider potential objections or limitations",
            priority="medium"
        )
    
    elif atom.name == "one_sided_con":
        claim_id = str(atom.arguments[0]).strip('"')
        
        return Frontier(
            type="asymmetric",
            location=claim_id,
            description="Only attacks provided, no supporting arguments",
            suggestion="Provide positive arguments for your position",
            priority="medium"
        )
    
    return None

def prioritize_frontiers(frontiers: List[Frontier]) -> List[Frontier]:
    """Sort frontiers by priority"""
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(frontiers, key=lambda f: priority_order[f.priority])

# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def print_debate_analysis(debate: Debate):
    """Print debate structure and frontiers"""
    
    print("\n" + "="*60)
    print("DEBATE STRUCTURE")
    print("="*60)
    
    if debate.main_claim:
        main = next((c for c in debate.claims if c.id == debate.main_claim), None)
        if main:
            print(f"\n🎯 MAIN CLAIM: {main.content}")
    
    print("\n📝 CLAIMS:")
    for claim in debate.claims:
        # Find relations
        supports = [r for r in debate.relations 
                   if r.from_claim == claim.id and r.relation_type == "supports"]
        attacks = [r for r in debate.relations 
                  if r.from_claim == claim.id and r.relation_type == "attacks"]
        
        print(f"\n  {claim.id}: {claim.content}")
        if supports:
            for s in supports:
                print(f"    → supports {s.to_claim}")
        if attacks:
            for a in attacks:
                print(f"    ⚔ attacks {a.to_claim}")
    
    if debate.frontiers:
        print("\n" + "="*60)
        print("EXPLORATION FRONTIERS")
        print("="*60)
        
        # Group by priority
        high = [f for f in debate.frontiers if f.priority == "high"]
        medium = [f for f in debate.frontiers if f.priority == "medium"]
        low = [f for f in debate.frontiers if f.priority == "low"]
        
        if high:
            print("\n🔴 HIGH PRIORITY:")
            for f in high:
                print(f"\n  [{f.location}] {f.description}")
                print(f"  💡 {f.suggestion}")
        
        if medium:
            print("\n🟡 MEDIUM PRIORITY:")
            for f in medium:
                print(f"\n  [{f.location}] {f.description}")
                print(f"  💡 {f.suggestion}")
        
        if low:
            print("\n🟢 LOW PRIORITY:")
            for f in low:
                print(f"\n  [{f.location}] {f.description}")
                print(f"  💡 {f.suggestion}")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    # Generate overall recommendations
    if any(f.type == "undefended_attack" for f in debate.frontiers):
        print("\n⚔️  Address undefended attacks to strengthen your position")
    
    if any(f.type == "asymmetric" for f in debate.frontiers):
        print("\n⚖️  Balance the debate by developing both sides equally")
    
    if any(f.type == "missing_evidence" for f in debate.frontiers):
        print("\n📊 Add concrete evidence to support key claims")
    
    if any(f.type == "orphaned_claim" for f in debate.frontiers):
        print("\n🔗 Connect or remove claims that don't contribute to the debate")
    
    if not debate.frontiers:
        print("\n✅ This debate appears well-structured with no major gaps!")

def export_argdown(debate: Debate) -> str:
    """Export to Argdown format with frontier markers"""
    
    argdown = "# Debate Map\n\n"
    
    for claim in debate.claims:
        # Add frontier markers
        markers = []
        for f in debate.frontiers:
            if f.location == claim.id:
                if f.type == "undefended_attack":
                    markers.append("🔴")
                elif f.type == "missing_evidence":
                    markers.append("📊")
                elif f.type == "asymmetric":
                    markers.append("⚖️")
                elif f.type == "orphaned_claim":
                    markers.append("🔗")
        
        marker_str = " ".join(markers) if markers else ""
        argdown += f"<{claim.id}> {claim.content} {marker_str}\n"
        
        # Add relations
        for rel in debate.relations:
            if rel.from_claim == claim.id:
                if rel.relation_type == "supports":
                    argdown += f"  + <{rel.to_claim}>\n"
                elif rel.relation_type == "attacks":
                    argdown += f"  - <{rel.to_claim}>\n"
        argdown += "\n"
    
    if debate.frontiers:
        argdown += "## Exploration Frontiers\n\n"
        for f in debate.frontiers:
            argdown += f"- **{f.type}** at {f.location}: {f.description}\n"
            argdown += f"  - Suggestion: {f.suggestion}\n\n"
    
    return argdown

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Debate Frontier Analyzer')
    parser.add_argument('file', nargs='?', default='examples_debate.txt',
                       help='Input file containing debate text (default: examples_debate.txt)')
    parser.add_argument('--export', choices=['argdown', 'json'], 
                       help='Export format')
    parser.add_argument('--no-frontiers', action='store_true',
                       help='Skip frontier detection')
    parser.add_argument('--debug', action='store_true',
                       help='Show ASP program and debug output')
    
    args = parser.parse_args()
    
    # Read input
    with open(args.file, 'r') as f:
        text = f.read()
    
    # Parse debate
    print(f"Analyzing debate from {args.file}...")
    parser = DebateParser()
    debate = parser.parse_debate(text)
    
    # Detect frontiers
    if not args.no_frontiers:
        print("Detecting exploration frontiers...")
        debate.frontiers = detect_frontiers(debate, debug=args.debug)
    
    # Output results
    if args.export == 'argdown':
        print(export_argdown(debate))
    elif args.export == 'json':
        # Export as JSON
        output = {
            "claims": [{"id": c.id, "content": c.content, "type": c.type} 
                      for c in debate.claims],
            "relations": [{"from": r.from_claim, "to": r.to_claim, 
                          "type": r.relation_type, "strength": r.strength}
                         for r in debate.relations],
            "main_claim": debate.main_claim,
            "frontiers": [{"type": f.type, "location": f.location,
                          "description": f.description, "suggestion": f.suggestion,
                          "priority": f.priority} for f in debate.frontiers]
        }
        print(json.dumps(output, indent=2))
    else:
        print_debate_analysis(debate)

if __name__ == "__main__":
    main()
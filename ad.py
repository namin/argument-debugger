#!/usr/bin/env python3
"""
Argument Debugger: An LLM+ASP-based system for analyzing and repairing arguments
"""

import json
import clingo
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from google.genai import types
import os
from pydantic import BaseModel, Field

# Safe quoting for ASP emission
_BACKSLASH = "\\\\"
_QUOTE = '\\"'
def q(s: Optional[str]) -> str:
    """
    Quote a Python string as a Clingo string term.
    Escapes backslashes and double-quotes.
    """
    if s is None:
        s = ""
    return '"' + s.replace("\\", _BACKSLASH).replace('"', _QUOTE) + '"'

_ALLOWED_TYPES = {"premise", "intermediate", "conclusion"}
def clamp_claim_type(t: Optional[str]) -> str:
    """Ensure claim type is one of the allowed atoms; default to 'premise' if unknown."""
    t = (t or "").strip()
    return t if t in _ALLOWED_TYPES else "premise"

# Pydantic models for structured output
class ClaimModel(BaseModel):
    id: str = Field(description="Claim identifier (e.g., c1, c2)")
    content: str = Field(description="The actual claim text")
    type: str = Field(description="Type of claim: premise, intermediate, or conclusion")

class InferenceModel(BaseModel):
    from_claims: List[str] = Field(description="List of claim IDs that support this inference")
    to_claim: str = Field(description="The claim ID that this inference leads to")
    rule_type: str = Field(description="Type of inference: deductive, inductive, causal, or definitional")

class DichotomyModel(BaseModel):
    id: str = Field(description="Claim ID presenting a dichotomy")
    justified: bool = Field(description="True if logically exhaustive (e.g., X or not-X), false if false dichotomy")

class ArgumentStructure(BaseModel):
    """Complete structured output for argument parsing"""
    claims: List[ClaimModel] = Field(description="List of all claims in the argument")
    inferences: List[InferenceModel] = Field(description="List of logical connections between claims")
    equivalences: List[List[str]] = Field(
        default_factory=list,
        description="Lists of claim IDs that express the same idea"
    )
    dichotomies: List[DichotomyModel] = Field(
        default_factory=list,
        description="Claims presenting either/or choices with justification status"
    )
    empirical_claims: List[str] = Field(
        default_factory=list,
        description="Claim IDs that make factual assertions requiring evidence"
    )
    self_evident_claims: List[str] = Field(
        default_factory=list,
        description="Claim IDs that are widely accepted background facts that do not require evidence in this context"
    )
    slippery_slopes: List[str] = Field(
        default_factory=list,
        description="Claim IDs using slippery slope reasoning"
    )
    goal_claim: Optional[str] = Field(
        default=None,
        description="The ID of the main conclusion claim"
    )

# Data structures (keeping original for compatibility)
@dataclass
class Claim:
    id: str
    content: str
    type: str  # premise, intermediate, conclusion
    agent: Optional[str] = None

@dataclass
class Inference:
    from_claims: List[str]
    to_claim: str
    rule_type: str  # deductive, inductive, causal, definitional

@dataclass
class Argument:
    claims: List[Claim]
    inferences: List[Inference]
    goal_claim: Optional[str] = None

@dataclass
class Issue:
    type: str  # missing_link, unsupported_premise, contradiction, circular, false_dichotomy, slippery_slope
    description: str
    involved_claims: List[str]

from llm import init_llm_client, generate_content

class ArgumentParser:
    """Uses language model to parse natural language arguments into formal structure"""
    
    def __init__(self):
        self.client = init_llm_client()
        self.config = types.GenerateContentConfig(
            temperature=0.1,  # Low temperature for more deterministic outputs
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema=ArgumentStructure
        )
    
    def parse_argument(self, text: str) -> Argument:
        """Extract argument structure from natural language using structured output"""
        
        prompt = f"""
        Analyze this argument and extract its logical structure.
        
        Argument: {text}
        
        PARSING RULES:
        1. DO NOT over-decompose claims:
           - "Either A or B" is ONE claim (a disjunction), not three separate claims
           - "A because B, C, and D" means B, C, and D together form ONE compound premise supporting A
           - Only split into multiple claims when there are clear sentence boundaries or explicit logical steps
        
        2. Respect natural argument chunking:
           - One sentence typically = one claim (unless it contains "therefore", "because", etc.)
           - Lists of reasons that support the same conclusion should usually be kept as one compound premise
           - Only separate premises if they independently support different things
        
        Extract:
        1. Claims: List each distinct claim with:
           - id (c1, c2, etc.)
           - content (the actual claim, preserving disjunctions and compound statements)
           - type (premise/intermediate/conclusion)
        
        2. Inferences: How claims connect:
           - from_claims (list of claim ids)
           - to_claim (claim id)
           - rule_type (deductive/inductive/causal/definitional)
        
        3. Equivalences: Lists of claim IDs that express the same idea
           - Each list contains IDs of claims that are semantically equivalent
        
        4. Dichotomies: Claims that present "either/or" choices
           - IMPORTANT: Any claim containing "Either...or..." should be identified as a dichotomy
           - id: claim id of the disjunction itself (the claim containing "either/or")
           - justified: true if logically exhaustive (like "X or not-X"), false if false dichotomy (when more options exist)
        
        5. Empirical claims: Claims that make factual assertions requiring evidence
           - List of claim IDs that need empirical support
        
        6. Self-evident claims: Claims that are widely accepted background facts OR contain specific citations/evidence
           - List of claim IDs that are self-evident or well-supported
           - Include claims that cite specific sources, statistics, studies, or biblical verses
           - Include claims with specific data points (percentages, dates, names)
        
        7. Slippery slopes: Claims that argue one action leads to extreme consequences
           - List of claim IDs using slippery slope reasoning
        
        8. Goal claim: The main conclusion (if identifiable)
        
        CRITICAL INSTRUCTIONS:
        - DO NOT split disjunctions like "Either A or B" into separate A and B claims
        - DO NOT split compound reasons unless they serve different logical roles
        - ALWAYS identify claims containing "Either...or..." as dichotomies and analyze if they're justified
        - If there's a gap between premises and conclusion, DO NOT create an inference
        - For circular reasoning, create both inferences (A to B and B to A)
        - Only include inferences that are explicitly stated or directly implied
        - Mark claims as equivalent ONLY if they make essentially the same assertion
        """
        
        response = generate_content(
            self.client,
            contents=prompt,
            config=self.config
        )
        
        # Parse the structured response
        structured_data = ArgumentStructure.model_validate_json(response.text)
        
        # Convert to Argument object
        claims = [
            Claim(
                id=c.id,
                content=c.content,
                type=c.type
            ) for c in structured_data.claims
        ]
        
        inferences = [
            Inference(
                from_claims=i.from_claims,
                to_claim=i.to_claim,
                rule_type=i.rule_type
            ) for i in structured_data.inferences
        ]
        
        arg = Argument(
            claims=claims,
            inferences=inferences,
            goal_claim=structured_data.goal_claim
        )
        
        # Add additional attributes
        arg.equivalences = structured_data.equivalences
        arg.dichotomies = [d.model_dump() for d in structured_data.dichotomies]
        arg.empirical_claims = structured_data.empirical_claims
        arg.self_evident_claims = structured_data.self_evident_claims
        arg.slippery_slopes = structured_data.slippery_slopes
        
        return arg

class ASPDebugger:
    """Uses ASP to analyze argument structure and find issues"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
    
    def analyze(self, argument: Argument) -> List[Issue]:
        """Find logical issues in the argument"""
        
        # First check for structural issues before running ASP
        issues = []
        
        # Check if conclusion has no inferences leading to it
        if argument.goal_claim:
            has_inference_to_goal = any(
                inf.to_claim == argument.goal_claim 
                for inf in argument.inferences
            )
            if not has_inference_to_goal:
                # Find premise IDs for description
                premise_ids = [c.id for c in argument.claims if c.type == "premise"]
                issues.append(Issue(
                    type="missing_link",
                    description=f"No logical connection from premises to conclusion {argument.goal_claim}",
                    involved_claims=[",".join(premise_ids), argument.goal_claim]
                ))
        
        
        # Build ASP program
        asp_program = self._build_asp_program(argument)
        
        if self.debug:
            print("### ASP Program")
            print("```prolog")
            print(asp_program)
            print("```")
        
        # Run ASP solver
        control = clingo.Control(["--warn=none"])  # Suppress info messages
        control.add("base", [], asp_program)
        control.ground([("base", [])])
        
        asp_issues = []
        with control.solve(yield_=True) as handle:
            for model in handle:
                if self.debug:
                    print(f"Model: {[str(atom) for atom in model.symbols(shown=True)]}")
                
                for atom in model.symbols(shown=True):
                    if atom.name == "missing_link":
                        from_claims = str(atom.arguments[0]).strip('"')
                        to_claim = str(atom.arguments[1]).strip('"')
                        asp_issues.append(Issue(
                            type="missing_link",
                            description=f"No clear logical connection to reach {to_claim}",
                            involved_claims=[from_claims, to_claim]
                        ))
                    
                    elif atom.name == "unsupported_premise":
                        claim_id = str(atom.arguments[0]).strip('"')
                        asp_issues.append(Issue(
                            type="unsupported_premise",
                            description=f"Premise {claim_id} needs supporting evidence",
                            involved_claims=[claim_id]
                        ))
                    
                    elif atom.name == "circular_reasoning":
                        claim_id = str(atom.arguments[0]).strip('"')
                        if not any(i.type == "circular" for i in issues):
                            asp_issues.append(Issue(
                                type="circular",
                                description=f"Circular reasoning detected involving {claim_id}",
                                involved_claims=[claim_id]
                            ))
                    
                    elif atom.name == "false_dichotomy":
                        claim_id = str(atom.arguments[0]).strip('"')
                        asp_issues.append(Issue(
                            type="false_dichotomy",
                            description=f"False dichotomy in {claim_id}: presents only two options when more may exist",
                            involved_claims=[claim_id]
                        ))
                    
                    elif atom.name == "slippery_slope":
                        claim_id = str(atom.arguments[0]).strip('"')
                        asp_issues.append(Issue(
                            type="slippery_slope",
                            description=f"Slippery slope in {claim_id}: argues that one action leads to extreme consequences without justification",
                            involved_claims=[claim_id]
                        ))
                
                # Only take first model
                break
        
        # Combine manual checks with ASP results
        issues.extend(asp_issues)
        
        # Deduplicate issues
        seen = set()
        unique_issues = []
        for issue in issues:
            key = (issue.type, tuple(sorted(issue.involved_claims)))
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)
        
        return unique_issues
    
    def _build_asp_program(self, argument: Argument) -> str:
        """Convert argument to ASP rules"""
        
        claim_contents = {}
        program = "% Claims\n"
        claim_ids = {c.id for c in argument.claims}
        for claim in argument.claims:
            program += f"claim({q(claim.id)}, {q(clamp_claim_type(claim.type))}).\n"
        
        program += "\n% Inferences\n"
        for inf in argument.inferences:
            for from_claim in inf.from_claims:
                # Only emit well-formed inferences between known claim ids
                if from_claim in claim_ids and inf.to_claim in claim_ids:
                    program += f"inference({q(from_claim)}, {q(inf.to_claim)}).\n"
        
        # Add equivalences if they exist
        if hasattr(argument, 'equivalences') and argument.equivalences:
            program += "\n% Equivalences\n"
            for equiv_set in argument.equivalences:
                # Create equivalence facts for each pair in the set
                for i, claim1 in enumerate(equiv_set):
                    for claim2 in equiv_set[i+1:]:
                        # Only for known claim ids
                        if claim1 in claim_ids and claim2 in claim_ids:
                            program += f"equivalent({q(claim1)}, {q(claim2)}).\n"
                            program += f"equivalent({q(claim2)}, {q(claim1)}).\n"
        
        if argument.goal_claim and argument.goal_claim in claim_ids:
            program += f"\n% Goal\ngoal({q(argument.goal_claim)}).\n"
        
        # Add empirical claims identified by parser
        if hasattr(argument, 'empirical_claims') and argument.empirical_claims:
            program += "\n% Empirical claims identified by parser\n"
            for claim_id in argument.empirical_claims:
                if claim_id in claim_ids:
                    program += f"empirical_claim({q(claim_id)}).\n"
        
        # Add self-evident claims identified by parser
        if hasattr(argument, 'self_evident_claims') and argument.self_evident_claims:
            program += "\n% Self-evident claims (LLM judgement)\n"
            for cid in argument.self_evident_claims:
                if cid in claim_ids:
                    program += f"self_evident({q(cid)}).\n"

        # Add facts about dichotomous claims from parser
        if hasattr(argument, 'dichotomies') and argument.dichotomies:
            program += "\n% Dichotomies identified by parser\n"
            for dichot in argument.dichotomies:
                claim_id = dichot.get('id')
                justified = dichot.get('justified', False)
                if not justified:  # Only mark unjustified dichotomies
                    if claim_id in claim_ids:
                        program += f"false_dichotomy_claim({q(claim_id)}).\n"
                    if self.debug:
                        print(f"Marked {claim_id} as false dichotomy")
        
        # Add slippery slope claims identified by parser
        if hasattr(argument, 'slippery_slopes') and argument.slippery_slopes:
            program += "\n% Slippery slopes identified by parser\n"
            for claim_id in argument.slippery_slopes:
                if claim_id in claim_ids:
                    program += f"slippery_slope_claim({q(claim_id)}).\n"
                if self.debug:
                    print(f"Marked {claim_id} as slippery slope")
        
        program += """
% =========================
% Argument Analysis (ASP)
% =========================
% The Python side supplies these facts (do not redefine here):
%   claim(ID, "premise" | "intermediate" | "conclusion").
%   inference(From, To).
%   equivalent(A, B).        % both directions are generated in Python
%   goal(G).                 % optional
%   empirical_claim(ID).     % list from parser
%   self_evident(ID).        % list from parser
%   false_dichotomy_claim(ID).
%   slippery_slope_claim(ID).
%   % Optional (if you ever choose to emit them from the LLM):
%   has_citation(ID).
%   justified_empirically(ID).

% -------------------------
% Support graph (closure)
% -------------------------
supports(X, Y) :- inference(X, Y).
supports(X, Z) :- supports(X, Y), inference(Y, Z).

% Bridge through equivalence (both ways because Python emits both directions).
supports(X, Z) :- supports(X, Y), equivalent(Y, Z).
supports(E, Y) :- equivalent(E, X), supports(X, Y).

has_inference(C) :- inference(_, C).

% -------------------------
% Empirical support
% -------------------------
% A claim C has empirical support if some upstream supporter S is empirical,
% and C is not (even indirectly) supporting S (prevents circular “evidence”).
has_empirical_support(C) :-
    empirical_claim(C),
    supports(S, C),
    empirical_claim(S),
    not supports(C, S).

% Optional levers provided by the parser/LLM (if present)
has_empirical_support(C) :- justified_empirically(C).
has_empirical_support(C) :- has_citation(C).

% -------------------------
% Admissible premises
% -------------------------
% Non-empirical premises are admissible by default.
admissible_premise(C) :-
    claim(C, "premise"),
    not empirical_claim(C).

% Empirical premises are admissible only if supported or self-evident.
admissible_premise(C) :-
    claim(C, "premise"),
    empirical_claim(C),
    has_empirical_support(C).
admissible_premise(C) :-
    claim(C, "premise"),
    empirical_claim(C),
    self_evident(C).

% -------------------------
% Node-level support
% -------------------------
supported(C) :- admissible_premise(C).
supported(C) :- supports(From, C), supported(From).

% -------------------------
% Relevance for premise flags
% -------------------------
relevant_premise(C) :-
    goal(G), supports(C, G).
relevant_premise(C) :-
    supports(C, K), claim(K, "conclusion").

% -------------------------
% Unsupported empirical premises (the main, precise signal)
% -------------------------
unsupported_premise(C) :-
    claim(C, "premise"),
    empirical_claim(C),
    relevant_premise(C),
    not self_evident(C),
    not has_empirical_support(C).

% -------------------------
% Missing links
% -------------------------
% Case A: no inference into a conclusion at all
missing_link("premises", C) :-
    claim(C, "conclusion"),
    not has_inference(C).

% Case B: goal has no inference at all
missing_link("premises", G) :-
    goal(G),
    not has_inference(G).

% Case C: conclusion has some inferences, but its proof fails.
% If failure is *only* because upstream premises are unsupported,
% prefer surfacing those specific unsupported_premise/1 instead of a generic gap.
has_upstream_unsupported(C) :- unsupported_premise(P), supports(P, C).

missing_link("support", C) :-
    claim(C, "conclusion"),
    has_inference(C),
    not supported(C),
    not has_upstream_unsupported(C).

% -------------------------
% Circular reasoning
% -------------------------
depends_on(X, Y) :- inference(Y, X).
depends_on(X, Z) :- depends_on(X, Y), inference(Z, Y).

% Let equivalence propagate dependencies
depends_on(X, Z) :- depends_on(X, Y), equivalent(Y, Z).
depends_on(Z, X) :- equivalent(Z, Y), depends_on(Y, X).

% Self-loop cycle
circular_reasoning(X) :- depends_on(X, X).

% Cycle via equivalence to the “same” claim
circular_reasoning(X) :- depends_on(X, Y), equivalent(X, Y).

% Mutual dependency cycle (A depends on B and B depends on A)
mutually_dependent(X, Y) :- depends_on(X, Y), depends_on(Y, X), X != Y.
circular_reasoning(X) :- mutually_dependent(X, _).

% -------------------------
% Pattern flags from parser (only for known claims)
% -------------------------
false_dichotomy(C) :- false_dichotomy_claim(C), claim(C, _).
slippery_slope(C) :- slippery_slope_claim(C), claim(C, _).

% -------------------------
% Show only issue atoms
% -------------------------
#show missing_link/2.
#show unsupported_premise/1.
#show circular_reasoning/1.
#show false_dichotomy/1.
#show slippery_slope/1.
        """
        
        return program

# RepairGenerator class would remain the same as it doesn't interact with Gemini directly
# ArgumentDebugger class would remain the same

class RepairGenerator:
    """Generates repairs for identified issues"""
    
    def __init__(self, debug: bool = False):
        self.client = init_llm_client()
        self.debug = debug
        self.config = types.GenerateContentConfig(
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )
    
    def generate_repair(self, argument_text: str, argument: Argument, issues: List[Issue]) -> Tuple[Optional[str], Optional[str]]:
        """Generate repair text and cleaned argument"""
        
        if not issues:
            return None, None
        
        # Generate repair text with commentary
        repair_commentary = self._generate_repair_text(argument, issues)
        if not repair_commentary:
            return None, None
        
        # Generate a clean rewritten argument
        clean_argument = self._generate_clean_argument(argument_text, repair_commentary)
        
        return repair_commentary, clean_argument
    
    def _generate_repair_text(self, argument: Argument, issues: List[Issue]) -> Optional[str]:
        """Generate text that addresses the issues"""
        
        # Build a simple list of what needs fixing
        issue_descriptions = []
        for issue in issues:
            if issue.type == "missing_link":
                if len(issue.involved_claims) >= 2:
                    to_claim = issue.involved_claims[1]
                    to_content = self._get_claim_content(argument, to_claim)
                    issue_descriptions.append(f"- Bridge the logical gap to: {to_content}")
            elif issue.type == "unsupported_premise":
                claim_id = issue.involved_claims[0]
                claim_content = self._get_claim_content(argument, claim_id)
                issue_descriptions.append(f"- Provide evidence for: {claim_content}")
            elif issue.type == "circular":
                issue_descriptions.append(f"- Break circular reasoning with independent support")
            elif issue.type == "false_dichotomy":
                claim_id = issue.involved_claims[0]
                claim_content = self._get_claim_content(argument, claim_id)
                issue_descriptions.append(f"- Address the false dichotomy in: {claim_content}")
            elif issue.type == "slippery_slope":
                claim_id = issue.involved_claims[0]
                claim_content = self._get_claim_content(argument, claim_id)
                issue_descriptions.append(f"- Justify the causal chain in: {claim_content}")
        
        issues_text = "\n".join(issue_descriptions)
        
        prompt = f"""
Add text to this argument to address these issues:
{issues_text}

Write additional statements that resolve the issues. Be concise and direct.
"""
        
        response = generate_content(
            self.client,
            contents=prompt,
            config=self.config
        )
        
        repair_text = response.text.strip()
        
        if not repair_text:
            return None
        
        return repair_text
    
    def _generate_clean_argument(self, original_text: str, repair_commentary: str) -> str:
        """Generate a clean, integrated argument from original and repair"""
        
        prompt = f"""
Given this original argument:
{original_text}

And this repair commentary:
{repair_commentary}

Your task is to generate a clean, integrated argument that maintains the original conclusion.

IMPORTANT: If the repair commentary contradicts or refutes the original premise, you should:
1. Acknowledge the weakness of the original reasoning
2. Find an ALTERNATIVE line of reasoning that could support the same conclusion
3. Use phrases like "While [original premise] may be flawed, one could argue..." or "Setting aside [problematic reasoning], another consideration is..."
4. Focus on different evidence or reasoning that doesn't rely on the refuted premise

For example:
- If the original uses a slippery slope that's been refuted, find a different reason to support the conclusion
- If the original uses ad hominem that's been shown invalid, find substantive reasons for the conclusion
- If evidence contradicts a premise, acknowledge this and pivot to different supporting points

Generate a clean argument that:
1. Maintains the ORIGINAL CONCLUSION
2. Addresses weaknesses identified in the repair
3. Uses alternative reasoning if the original reasoning was refuted
4. Remains intellectually honest by acknowledging when shifting to different arguments
5. Includes at least one explicit bridge sentence that links the evidence to the conclusion
6. Ends with the original conclusion as the final sentence

Write ONLY the argument itself as a series of clear statements.
Do not include any headers, explanations, or formatting.
Each statement should be a complete sentence.
"""
        
        response = generate_content(
            self.client,
            contents=prompt,
            config=self.config
        )
        
        return response.text.strip()
    
    def _get_claim_content(self, argument: Argument, claim_id: str) -> str:
        """Get claim content by ID"""
        for claim in argument.claims:
            if claim.id == claim_id:
                return claim.content
        return ""
    

class ArgumentDebugger:
    """Main system that combines all components"""
    
    def __init__(self, debug: bool = False):
        self.parser = ArgumentParser()
        self.analyzer = ASPDebugger(debug=debug)
        self.repairer = RepairGenerator(debug=debug)
        self.debug = debug
    
    def _print_structure(self, argument: Argument, label: str = "Parsed structure"):
        """Helper to print argument structure"""
        print(f"\n{label}:")
        for claim in argument.claims:
            print(f"- {claim.id}: {claim.content} ({claim.type})")
        for inf in argument.inferences:
            print(f"- {inf.from_claims} → {inf.to_claim} ({inf.rule_type})")
    
    def _print_issues(self, issues: List[Issue]) -> None:
        """Helper to print issues"""
        if issues:
            print(f"\n🔍 ISSUES FOUND ({len(issues)}):")
            for issue in issues:
                print(f"  - {issue.type}: {issue.description}")
        else:
            print("\n✅ No logical issues found!")
    
    def debug_argument(self, argument_text: str, apply_repair: bool = True) -> Dict:
        """Complete debugging pipeline"""
        
        # 1. Parse argument
        print("\nParsing argument...")
        argument = self.parser.parse_argument(argument_text)
        
        self._print_structure(argument)
        
        # 2. Analyze for issues
        print("\nAnalyzing logical structure...")
        issues = self.analyzer.analyze(argument)
        
        self._print_issues(issues)
        
        if not issues:
            return {"argument": argument, "issues": issues}
        
        # 3. Generate and apply repair if requested
        if apply_repair and issues:
            print(f"\n🔧 GENERATING REPAIR...")
            repair_commentary, clean_argument = self.repairer.generate_repair(argument_text, argument, issues)
            
            if repair_commentary and clean_argument:
                print("\nREPAIR COMMENTARY:")
                print(repair_commentary)
                
                print("\nCLEAN ARGUMENT:")
                print(clean_argument)

                print("\nParsing repaired argument...")
                repaired_argument = self.parser.parse_argument(clean_argument)
                
                self._print_structure(repaired_argument)
                
                # 2. Analyze for issues
                print("\nRe-analyzing logical structure...")
                remaining_issues = self.analyzer.analyze(repaired_argument)
                
                self._print_issues(remaining_issues)
                
                return {
                    "argument": argument,
                    "issues": issues,
                    "repair_commentary": repair_commentary,
                    "clean_argument": clean_argument,
                    "modified_argument": repaired_argument,
                    "remaining_issues": remaining_issues
                }
        
        return {"argument": argument, "issues": issues}

def main():
    import sys
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Argument Debugger: Analyze and repair logical arguments')
    parser.add_argument('file', nargs='?', default='examples/examples.txt', 
                       help='Input file containing arguments (default: examples/examples.txt)')
    parser.add_argument('--debug', action='store_true', 
                       help='Show ASP programs and debug output')
    parser.add_argument('--no-repairs', action='store_true',
                       help='Skip generating repairs (faster, useful for testing)')
    
    args = parser.parse_args()
    
    print("# Output")
    filename = args.file
    try:
        with open(filename, 'r') as f:
            content = f.read()

        # Split by double newlines to separate arguments
        examples = [arg.strip() for arg in content.split('\n\n') if arg.strip()]
        print(f"Loaded {len(examples)} arguments from {filename}")

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Initialize debugger
    debugger = ArgumentDebugger(debug=args.debug)

    for i, arg_text in enumerate(examples):
        print(f"\n## EXAMPLE {i+1}")
        print("Argument:", arg_text.strip())
        
        try:
            result = debugger.debug_argument(arg_text, apply_repair=not args.no_repairs)
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
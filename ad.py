#!/usr/bin/env python3
"""
Argument Debugger with Pydantic models for structured output from Gemini
"""

import json
import clingo
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from google import genai
from google.genai import types
import os
from pydantic import BaseModel, Field

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

@dataclass
class Repair:
    type: str  # always "addition" for now
    description: str
    content: Optional[str] = None
    additions: Optional[List[str]] = None  # New premises to add

llm_model = "gemini-2.5-flash"
llm_config = types.GenerateContentConfig(
        temperature=0.1,  # Low temperature for more deterministic outputs
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=ArgumentStructure
)

def init_llm_client():
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    google_cloud_project = os.getenv('GOOGLE_CLOUD_PROJECT')
    google_cloud_location = os.getenv('GOOGLE_CLOUD_LOCATION', "us-central1")
    if gemini_api_key:
        return genai.Client(api_key=gemini_api_key)
    elif google_cloud_project:
        return genai.Client(vertexai=True, project=google_cloud_project, location=google_cloud_location)
    else:
        raise ValueError("Gemini configuration required. Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT environment variables.")

class ArgumentParser:
    """Uses language model to parse natural language arguments into formal structure"""
    
    def __init__(self):
        self.client = init_llm_client()
    
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
           - id: claim id of the disjunction itself
           - justified: true if logically exhaustive, false if false dichotomy
        
        5. Empirical claims: Claims that make factual assertions requiring evidence
           - List of claim IDs that need empirical support
        
        6. Slippery slopes: Claims that argue one action leads to extreme consequences
           - List of claim IDs using slippery slope reasoning
        
        7. Goal claim: The main conclusion (if identifiable)
        
        CRITICAL INSTRUCTIONS:
        - DO NOT split disjunctions like "Either A or B" into separate A and B claims
        - DO NOT split compound reasons unless they serve different logical roles
        - If there's a gap between premises and conclusion, DO NOT create an inference
        - For circular reasoning, create both inferences (A to B and B to A)
        - Only include inferences that are explicitly stated or directly implied
        - Mark claims as equivalent ONLY if they make essentially the same assertion
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
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
                    if atom.name == "missing_link" and not any(i.type == "missing_link" for i in issues):
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
                            description=f"False dichotomy: presents only two options when more may exist",
                            involved_claims=[claim_id]
                        ))
                    
                    elif atom.name == "slippery_slope":
                        claim_id = str(atom.arguments[0]).strip('"')
                        asp_issues.append(Issue(
                            type="slippery_slope",
                            description=f"Slippery slope: argues that one action leads to extreme consequences without justification",
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
        
        program = "% Claims\n"
        claim_contents = {}
        for claim in argument.claims:
            program += f'claim("{claim.id}", "{claim.type}").\n'
            claim_contents[claim.id] = claim.content
        
        program += "\n% Inferences\n"
        for inf in argument.inferences:
            for from_claim in inf.from_claims:
                program += f'inference("{from_claim}", "{inf.to_claim}").\n'
        
        # Add equivalences if they exist
        if hasattr(argument, 'equivalences') and argument.equivalences:
            program += "\n% Equivalences\n"
            for equiv_set in argument.equivalences:
                # Create equivalence facts for each pair in the set
                for i, claim1 in enumerate(equiv_set):
                    for claim2 in equiv_set[i+1:]:
                        program += f'equivalent("{claim1}", "{claim2}").\n'
                        program += f'equivalent("{claim2}", "{claim1}").\n'
        
        if argument.goal_claim:
            program += f'\n% Goal\ngoal("{argument.goal_claim}").\n'
        
        # Add empirical claims identified by parser
        if hasattr(argument, 'empirical_claims') and argument.empirical_claims:
            program += "\n% Empirical claims identified by parser\n"
            for claim_id in argument.empirical_claims:
                program += f'empirical_claim("{claim_id}").\n'
        
        # Add facts about dichotomous claims from parser
        if hasattr(argument, 'dichotomies') and argument.dichotomies:
            program += "\n% Dichotomies identified by parser\n"
            for dichot in argument.dichotomies:
                claim_id = dichot.get('id')
                justified = dichot.get('justified', False)
                if not justified:  # Only mark unjustified dichotomies
                    program += f'false_dichotomy_claim("{claim_id}").\n'
                    if self.debug:
                        print(f"Marked {claim_id} as false dichotomy")
        
        # Add slippery slope claims identified by parser
        if hasattr(argument, 'slippery_slopes') and argument.slippery_slopes:
            program += "\n% Slippery slopes identified by parser\n"
            for claim_id in argument.slippery_slopes:
                program += f'slippery_slope_claim("{claim_id}").\n'
                if self.debug:
                    print(f"Marked {claim_id} as slippery slope")
        
        program += """
        % Track which claims have incoming inferences
        has_inference(C) :- inference(_, C).
        
        % A claim is supported if:
        % 1. It's a premise without empirical content, OR
        % 2. It has valid inferences from supported claims
        basic_premise(C) :- 
            claim(C, "premise"),
            not empirical_claim(C).
            
        supported(C) :- basic_premise(C).
        supported(C) :- 
            inference(From, C),
            supported(From).
        
        % Find missing links
        % Case 1: Conclusion with no inference at all
        missing_link("premises", C) :- 
            claim(C, "conclusion"),
            not has_inference(C).
            
        % Case 2: Goal with no path from premises
        missing_link("premises", G) :- 
            goal(G),
            not has_inference(G).
            
        % Case 3: Inference exists but chain is broken
        missing_link("support", C) :- 
            claim(C, "conclusion"),
            has_inference(C),
            not supported(C).
        
        % Find unsupported empirical premises
        unsupported_premise(C) :- 
            claim(C, "premise"),
            empirical_claim(C).
        
        % Detect circular reasoning with equivalences
        % Standard dependencies
        depends_on(X, Y) :- inference(Y, X).
        depends_on(X, Z) :- depends_on(X, Y), inference(Z, Y).
        
        % Key insight: if X depends on Y and Y is equivalent to X, that's circular!
        circular_reasoning(X) :- depends_on(X, Y), equivalent(X, Y).
        
        % Also catch self-loops
        circular_reasoning(X) :- depends_on(X, X).
        
        % Also detect mutual dependency (A->B and B->A implicitly)
        % This catches cases where claims are interdependent
        mutually_dependent(X, Y) :- depends_on(X, Y), depends_on(Y, X), X != Y.
        circular_reasoning(X) :- mutually_dependent(X, _).
        
        % Detect when a claim's only support comes from claims it supports
        % (a more general form of circular reasoning)
        supports(X, Y) :- inference(X, Y).
        supports(X, Z) :- supports(X, Y), supports(Y, Z).
        only_supported_by_dependents(X) :- 
            claim(X, _),
            has_inference(X),
            inference(Y, X),
            supports(X, Y).
        
        % Detect false dichotomies
        % Parser identifies which dichotomies are unjustified
        false_dichotomy(C) :- 
            false_dichotomy_claim(C).
        
        % Detect slippery slopes
        % Parser identifies claims using slippery slope reasoning
        slippery_slope(C) :- 
            slippery_slope_claim(C).
        
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
    """Generates and verifies repairs for identified issues"""
    
    def __init__(self, debug: bool = False):
        self.client = init_llm_client()
        self.debug = debug
        # Config for repair generation
        self.repair_config = types.GenerateContentConfig(
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )
    
    def generate_repair(self, argument: Argument, issues: List[Issue]) -> Tuple[Optional[Repair], List[Issue]]:
        """Generate one comprehensive repair and return it with remaining issues"""
        
        if not issues:
            return None, []
        
        # Generate a comprehensive repair
        repair = self._generate_cover_set_repair(argument, issues)
        if not repair:
            return None, issues
        
        # Apply repair and get full analysis of remaining issues
        modified_arg = self._apply_repair(repair, argument)
        debugger = ASPDebugger(debug=False)
        remaining_issues = debugger.analyze(modified_arg)
        
        return repair, remaining_issues
    
    def _generate_cover_set_repair(self, argument: Argument, issues: List[Issue]) -> Optional[Repair]:
        """Generate a comprehensive repair that covers all issues"""
        
        # Build coverage specification
        coverage_spec = self._build_coverage_specification(argument, issues)
        
        prompt = f"""
{coverage_spec}

Generate premises that, when added to the argument, will resolve ALL the issues listed above.
Do not modify existing claims, only add new supporting premises.

Requirements:
- The additions must resolve every issue in the coverage specification
- Be specific and concrete
- Ensure logical coherence with existing claims

Respond with just the addition(s), one per line. No explanation.
"""
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=self.repair_config
        )
        
        repair_text = response.text.strip()
        
        # Parse additions - just split by newlines
        additions = []
        for line in repair_text.split('\n'):
            line = line.strip()
            if line:
                additions.append(line)
        
        if not additions:
            return None
        
        repair = Repair(
            type="addition",
            description="Comprehensive repair",
            content=repair_text,
            additions=additions
        )
        
        return repair
    
    def _build_coverage_specification(self, argument: Argument, issues: List[Issue]) -> str:
        """Build a structured specification of what needs to be covered"""
        
        # Get argument structure
        premises_text = "\n".join([f"  {c.id}: {c.content}" for c in argument.claims if c.type == "premise"])
        conclusions_text = "\n".join([f"  {c.id}: {c.content}" for c in argument.claims if c.type == "conclusion"])
        
        # Build issue coverage requirements
        coverage_reqs = []
        for i, issue in enumerate(issues, 1):
            if issue.type == "missing_link":
                involved = issue.involved_claims
                if len(involved) >= 2:
                    from_claims = involved[0]
                    to_claim = involved[1]
                    to_content = self._get_claim_content(argument, to_claim)
                    coverage_reqs.append(f"{i}. MISSING LINK: No connection from {from_claims} to {to_claim}\n   REQUIRED: Logical bridge to reach '{to_content}'")
            
            elif issue.type == "unsupported_premise":
                claim_id = issue.involved_claims[0]
                claim_content = self._get_claim_content(argument, claim_id)
                coverage_reqs.append(f"{i}. UNSUPPORTED: Claim {claim_id} lacks evidence\n   REQUIRED: Supporting evidence for '{claim_content}'")
            
            elif issue.type == "circular":
                claim_id = issue.involved_claims[0]
                coverage_reqs.append(f"{i}. CIRCULAR: Claim {claim_id} is part of circular reasoning\n   REQUIRED: Independent support that breaks the circle")
            
            elif issue.type == "false_dichotomy":
                claim_id = issue.involved_claims[0]
                claim_content = self._get_claim_content(argument, claim_id)
                coverage_reqs.append(f"{i}. FALSE DICHOTOMY: {claim_id} presents limited options\n   REQUIRED: Acknowledge other possibilities or justify the limitation")
            
            elif issue.type == "slippery_slope":
                claim_id = issue.involved_claims[0]
                coverage_reqs.append(f"{i}. SLIPPERY SLOPE: {claim_id} makes unjustified leap\n   REQUIRED: Justify the progression or moderate the claim")
        
        spec = f"""ARGUMENT STRUCTURE:
Premises:
{premises_text}

Conclusions:
{conclusions_text}

COVERAGE REQUIREMENTS (must address ALL):
{chr(10).join(coverage_reqs)}
"""
        
        return spec
    
    
    def _apply_repair(self, repair: Repair, argument: Argument) -> Argument:
        """Apply a repair to an argument to create a modified version"""
        
        # Create a deep copy of the argument
        import copy
        modified = copy.deepcopy(argument)
        
        # Preserve all attributes
        if hasattr(argument, 'equivalences'):
            modified.equivalences = copy.deepcopy(argument.equivalences)
        if hasattr(argument, 'dichotomies'):
            modified.dichotomies = copy.deepcopy(argument.dichotomies)
        if hasattr(argument, 'empirical_claims'):
            modified.empirical_claims = copy.deepcopy(argument.empirical_claims)
        if hasattr(argument, 'slippery_slopes'):
            modified.slippery_slopes = copy.deepcopy(argument.slippery_slopes)
        
        # Add new premises
        if repair.additions:
            new_claim_ids = []
            for i, addition in enumerate(repair.additions):
                new_claim_id = f"r{len(modified.claims) + 1 + i}"
                new_claim = Claim(
                    id=new_claim_id,
                    content=addition,
                    type="premise"
                )
                modified.claims.append(new_claim)
                new_claim_ids.append(new_claim_id)
            
            # Try to connect first new premise to unsupported conclusions
            for claim in modified.claims:
                if claim.type == "conclusion":
                    has_inference = any(inf.to_claim == claim.id for inf in modified.inferences)
                    if not has_inference and new_claim_ids:
                        new_inference = Inference(
                            from_claims=[new_claim_ids[0]],
                            to_claim=claim.id,
                            rule_type="deductive"
                        )
                        modified.inferences.append(new_inference)
                        break  # Only connect to first unsupported conclusion
        
        
        return modified
    
    
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
            repair, remaining_issues = self.repairer.generate_repair(argument, issues)
            
            if repair:
                print("\nAPPLYING:")
                if repair.additions:
                    for addition in repair.additions:
                        print(f"-  ADD: \"{addition}\"")
                
                # Apply repair and show full analysis again
                modified_arg = self.repairer._apply_repair(repair, argument)
                
                print("\nAFTER REPAIR:")
                self._print_structure(modified_arg, "Modified structure")
                
                print("\nRe-analyzing logical structure...")
                self._print_issues(remaining_issues)
                
                return {
                    "argument": argument,
                    "issues": issues,
                    "repair": repair,
                    "modified_argument": modified_arg,
                    "remaining_issues": remaining_issues
                }
        
        return {"argument": argument, "issues": issues}

def main():
    import sys
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Argument Debugger: Analyze and repair logical arguments')
    parser.add_argument('file', nargs='?', default='examples.txt', 
                       help='Input file containing arguments (default: examples.txt)')
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
#!/usr/bin/env python3
"""
Argument Debugger: An LLM+ASP-based system for analyzing and repairing arguments
"""

import json
import clingo
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from google import genai
from google.genai import types
import os

# Data structures
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
    type: str  # missing_link, unsupported_premise, contradiction, circular, false_dichotomy
    description: str
    involved_claims: List[str]

@dataclass
class Repair:
    type: str  # add_premise, add_inference, remove_claim
    description: str
    content: Optional[str] = None
    confidence: float = 0.0
    score: float = 0.0  # Overall ranking score
    score_breakdown: Dict[str, float] = field(default_factory=dict)  # Detailed scores

llm_model = "gemini-2.5-flash"
llm_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
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
        raise ValueError("Gemini configuration required. Set GEMINI_API_KEY or GOOGLE_PROUD_PROJECT environment variables.")

class ArgumentParser:
    """Uses language model to parse natural language arguments into formal structure"""
    
    def __init__(self):
        self.client = init_llm_client()
    
    def parse_argument(self, text: str) -> Argument:
        """Extract argument structure from natural language"""
        
        prompt = f"""
        Analyze this argument and extract its logical structure.
        
        Argument: {text}
        
        Return a JSON with:
        1. Claims: List each distinct claim with:
           - id (c1, c2, etc.)
           - content (the actual claim)
           - type (premise/intermediate/conclusion)
        
        2. Inferences: How claims connect:
           - from_claims (list of claim ids)
           - to_claim (claim id)
           - rule_type (deductive/inductive/causal/definitional)
        
        3. Equivalences: Lists of claim IDs that express the same idea
           - Each list contains IDs of claims that are semantically equivalent
           - Example: [["c1", "c3"]] if c1 and c3 are restatements of each other
        
        4. Dichotomies: Claims that present "either/or" choices
           - List of objects with: id (claim id), justified (true if logically exhaustive, false if false dichotomy)
           - Mark justified=true for: X or not-X, binary states (alive/dead), logical opposites
           - Mark justified=false for: policy choices, most real-world scenarios with multiple options
           - Example: [{{"id": "c1", "justified": false}}]
        
        5. Empirical claims: Claims that make factual assertions requiring evidence
           - List of claim IDs that need empirical support
           - Include: statistical claims, causal relationships, historical facts, scientific assertions
           - Exclude: definitions, logical truths, value judgments, hypotheticals
           - Example: ["c1", "c3"] if those claims need evidence
        
        6. Goal claim: The main conclusion (if identifiable)
        
        CRITICAL INSTRUCTIONS:
        - If there's a gap between premises and conclusion (e.g., "Crime increased. Therefore we need more police"), 
          DO NOT create an inference. Leave the inferences list empty or incomplete to show the gap.
        - For circular reasoning (e.g., "A is true because B. B is true because A"), create both inferences:
          one from A to B and one from B to A.
        - Only include inferences that are explicitly stated or directly implied by logical connectors 
          like "because", "therefore", "since", etc.
        - To help in detecting circular epistemic reasoning, add a presupposition inference from a reliability claim to each claim that cites that source.
        - Mark claims as equivalent ONLY if they make essentially the same assertion.
          For example: "Democracy is the best form of government" and "Democracy is the best system" 
          are equivalent (both assert democracy's superiority)
        
        Example of missing link (no inference):
        {{
            "claims": [
                {{"id": "c1", "content": "Crime rates increased", "type": "premise"}},
                {{"id": "c2", "content": "We need more police", "type": "conclusion"}}
            ],
            "inferences": [],  // No connection stated!
            "goal_claim": "c2"
        }}
        
        Example of circular reasoning:
        {{
            "claims": [
                {{"id": "c1", "content": "The Bible is true", "type": "premise"}},
                {{"id": "c2", "content": "The Bible is the word of God", "type": "premise"}}
            ],
            "inferences": [
                {{"from_claims": ["c2"], "to_claim": "c1", "rule_type": "deductive"}},
                {{"from_claims": ["c1"], "to_claim": "c2", "rule_type": "deductive"}}
            ],
            "goal_claim": "c1"
        }}
        
        Return ONLY valid JSON.
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
        )
        
        # Extract JSON from response
        json_text = response.text
        json_start = json_text.find('{')
        json_end = json_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_text = json_text[json_start:json_end]
        
        data = json.loads(json_text)
        
        # Convert to Argument object
        claims = [Claim(**c) for c in data['claims']]
        inferences = [Inference(**i) for i in data['inferences']]
        
        # Store equivalences if provided
        equivalences = data.get('equivalences', [])
        
        # Store dichotomies if provided
        dichotomies = data.get('dichotomies', [])
        
        # Store empirical claims if provided
        empirical_claims = data.get('empirical_claims', [])
        
        arg = Argument(
            claims=claims,
            inferences=inferences,
            goal_claim=data.get('goal_claim')
        )
        # Add equivalences, dichotomies, and empirical_claims as attributes (not in dataclass definition)
        arg.equivalences = equivalences
        arg.dichotomies = dichotomies
        arg.empirical_claims = empirical_claims
        
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
        
        #show missing_link/2.
        #show unsupported_premise/1.
        #show circular_reasoning/1.
        #show false_dichotomy/1.
        """
        
        return program
    
    

class RepairGenerator:
    """Generates and ranks repairs for identified issues"""
    
    def __init__(self):
        self.client = init_llm_client()
        # Weights for repair ranking
        self.ranking_weights = {
            'minimality': 0.25,
            'plausibility': 0.30,
            'relevance': 0.25,
            'evidence_quality': 0.20
        }
    
    def generate_repairs(self, argument: Argument, issues: List[Issue]) -> List[Repair]:
        """Generate concrete repairs for each issue"""
        
        repairs = []
        
        for issue in issues:
            if issue.type == "missing_link":
                # Get all premises and the target
                premises = [c for c in argument.claims if c.type == "premise"]
                to_claim = issue.involved_claims[1]
                to_claim_content = self._get_claim_content(argument, to_claim)
                
                # Generate bridging premise
                premises_text = "\n".join([f"- {c.content}" for c in premises])
                bridge = self._generate_bridge(premises_text, to_claim_content)
                
                repairs.append(Repair(
                    type="add_premise",
                    description=f"Add bridging premise to connect existing claims to {to_claim}",
                    content=bridge,
                    confidence=0.8
                ))
            
            elif issue.type == "unsupported_premise":
                claim_content = self._get_claim_content(argument, issue.involved_claims[0])
                
                # Generate support for unsupported premises
                support = self._generate_support(claim_content)
                repairs.append(Repair(
                    type="add_premise",
                    description=f"Add supporting evidence for {issue.involved_claims[0]}",
                    content=support,
                    confidence=0.7
                ))
            
            elif issue.type == "circular":
                # For circular reasoning, suggest breaking the circle
                repairs.append(Repair(
                    type="add_premise",
                    description=f"Add independent evidence to break circular dependency",
                    content=self._generate_independent_support(argument, issue.involved_claims[0]),
                    confidence=0.6
                ))
            
            elif issue.type == "false_dichotomy":
                # For false dichotomy, suggest alternative options
                claim_content = self._get_claim_content(argument, issue.involved_claims[0])
                alternatives = self._generate_alternatives(claim_content)
                repairs.append(Repair(
                    type="add_premise",
                    description=f"Acknowledge alternative options beyond the presented dichotomy",
                    content=alternatives,
                    confidence=0.85
                ))
        
        # Rank repairs before returning
        ranked_repairs = self._rank_repairs(repairs, argument, issues)
        return ranked_repairs
    
    def _get_claim_content(self, argument: Argument, claim_id: str) -> str:
        """Get claim content by ID"""
        for claim in argument.claims:
            if claim.id == claim_id:
                return claim.content
        return ""
    
    
    def _generate_bridge(self, premises: str, conclusion: str) -> str:
        """Generate a bridging premise using LLM"""
        
        prompt = f"""
        What logical principle or empirical claim would connect these premises to this conclusion?
        
        Premises:
        {premises}
        
        Conclusion: {conclusion}
        
        Provide a single, clear bridging premise that makes the inference valid.
        The premise should be specific and directly connect the given claims.
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
        )
        
        return response.text.strip()
    
    def _generate_support(self, claim: str) -> str:
        """Generate supporting evidence for a claim"""
        
        prompt = f"""
        This claim needs empirical support or evidence:
        
        Claim: {claim}
        
        Provide a single piece of supporting evidence, study, or data that would support this claim.
        Be specific and realistic. If it's an empirical claim, suggest what kind of study or data would be needed.
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
        )
        
        return response.text.strip()
    
    def _generate_independent_support(self, argument: Argument, claim_id: str) -> str:
        """Generate independent support to break circular reasoning"""
        
        claim_content = self._get_claim_content(argument, claim_id)
        
        prompt = f"""
        This claim is part of a circular reasoning pattern and needs independent support:
        
        Claim: {claim_content}
        
        Provide external evidence or reasoning that doesn't rely on the claim itself.
        This should come from outside the circular logic.
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
        )
        
        return response.text.strip()
    
    def _generate_alternatives(self, dichotomous_claim: str) -> str:
        """Generate alternative options for a false dichotomy"""
        
        prompt = f"""
        This argument contains a false dichotomy:
        
        Claim: {dichotomous_claim}
        
        Suggest 2-3 alternative options that are being ignored.
        Be specific and relevant to the context.
        Format as a single statement acknowledging other possibilities.
        """
        
        response = self.client.models.generate_content(
            model=llm_model,
            contents=prompt,
            config=llm_config
        )
        
        return response.text.strip()
    
    def _rank_repairs(self, repairs: List[Repair], argument: Argument, issues: List[Issue]) -> List[Repair]:
        """Rank repairs based on multiple criteria"""
        for repair in repairs:
            scores = {
                'minimality': self._score_minimality(repair),
                'plausibility': self._score_plausibility(repair),
                'relevance': self._score_relevance(repair, issues),
                'evidence_quality': self._score_evidence_quality(repair)
            }
            
            # Calculate weighted total
            total_score = sum(scores[k] * self.ranking_weights[k] for k in scores)
            repair.score = total_score
            repair.score_breakdown = scores
        
        # Sort by score (highest first)
        repairs.sort(key=lambda r: r.score, reverse=True)
        return repairs
    
    def _score_minimality(self, repair: Repair) -> float:
        """Score based on repair simplicity (shorter is better)"""
        if not repair.content:
            return 0.5
        length = len(repair.content)
        if length < 100:
            return 1.0
        elif length < 200:
            return 0.8
        elif length < 400:
            return 0.6
        elif length < 600:
            return 0.4
        else:
            return 0.2
    
    def _score_plausibility(self, repair: Repair) -> float:
        """Score based on repair believability"""
        # Use confidence as proxy for plausibility
        # Could enhance with LLM evaluation if needed
        return repair.confidence
    
    def _score_relevance(self, repair: Repair, issues: List[Issue]) -> float:
        """Score how well repair addresses the issues"""
        relevance_map = {
            'missing_link': ['add_premise', 'add_inference'],
            'unsupported_premise': ['add_premise', 'add_evidence'],
            'circular': ['add_premise', 'remove_claim'],
            'false_dichotomy': ['add_premise', 'qualify_claim']
        }
        
        addressed = 0
        for issue in issues:
            if issue.type in relevance_map:
                if repair.type in relevance_map.get(issue.type, []):
                    addressed += 1
        
        return addressed / len(issues) if issues else 0.5
    
    def _score_evidence_quality(self, repair: Repair) -> float:
        """Score quality of evidence in repair"""
        if not repair.content:
            return 0.0
            
        content_lower = repair.content.lower()
        
        # High-quality evidence indicators
        quality_indicators = [
            'study', 'research', 'data', 'statistics',
            'percent', '%', 'university', 'journal',
            'evidence', 'report', 'analysis'
        ]
        
        # Count indicators (max 1.0)
        score = sum(0.15 for indicator in quality_indicators 
                   if indicator in content_lower)
        
        # Penalty for vague language
        if any(word in content_lower for word in ['might', 'could', 'possibly', 'maybe']):
            score *= 0.8
            
        return min(score, 1.0)

class ArgumentDebugger:
    """Main system that combines all components"""
    
    def __init__(self, debug: bool = False, show_structure: bool = True, generate_repairs: bool = True):
        self.parser = ArgumentParser()
        self.analyzer = ASPDebugger(debug=debug)
        self.repairer = RepairGenerator()
        self.debug = debug
        self.show_structure = show_structure
        self.generate_repairs = generate_repairs
    
    def debug_argument(self, argument_text: str) -> Dict:
        """Complete debugging pipeline"""
        
        # 1. Parse argument
        print("Parsing argument...")
        argument = self.parser.parse_argument(argument_text)
        
        if self.show_structure:
            print("\nParsed structure:")
            for claim in argument.claims:
                print(f"- {claim.id}: {claim.content} ({claim.type})")
            for inf in argument.inferences:
                print(f"- {inf.from_claims} → {inf.to_claim} ({inf.rule_type})")
            if hasattr(argument, 'equivalences') and argument.equivalences:
                print("Equivalences:")
                for equiv_set in argument.equivalences:
                    print(f"- {equiv_set} (semantically equivalent)")
            if hasattr(argument, 'dichotomies') and argument.dichotomies:
                print("Dichotomies:")
                for dichot in argument.dichotomies:
                    justified_str = "justified" if dichot.get('justified') else "unjustified"
                    print(f"- {dichot.get('id')} ({justified_str})")
        
        # 2. Analyze for issues
        print("\nAnalyzing logical structure...")
        issues = self.analyzer.analyze(argument)
        
        # 3. Generate repairs
        repairs = []
        if issues and self.generate_repairs:
            print(f"\nFound {len(issues)} issues. Generating repairs...")
            repairs = self.repairer.generate_repairs(argument, issues)
        elif issues:
            print(f"\nFound {len(issues)} issues.")
        
        # 4. Return complete analysis
        return {
            "argument": argument,
            "issues": issues,
            "repairs": repairs
        }

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
    parser.add_argument('--no-structure', action='store_true',
                       help='Hide parsed structure output')
    
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
    
    # Initialize debugger with command-line options
    debugger = ArgumentDebugger(
        debug=args.debug,
        show_structure=not args.no_structure,
        generate_repairs=not args.no_repairs
    )

    for i, arg_text in enumerate(examples):
        print(f"\n## EXAMPLE {i+1}")
        print("Argument:", arg_text.strip())
        
        try:
            result = debugger.debug_argument(arg_text)
            
            # Display issues
            if result['issues']:
                print("\n🔍 ISSUES FOUND:")
                for issue in result['issues']:
                    print(f"  - {issue.type}: {issue.description}")
            else:
                print("\n✅ No logical issues found!")
            
            # Display repairs with ranking
            if result['repairs']:
                print("\n🔧 SUGGESTED REPAIRS (ranked):")
                for i, repair in enumerate(result['repairs'][:3], 1):  # Show top 3
                    print(f"  {i}. [{repair.type}] Score: {repair.score:.2f}")
                    print(f"     {repair.description}")
                    if repair.content:
                        #content = repair.content if len(repair.content) < 200 else repair.content[:197] + "..."
                        content = repair.content
                        print(f"     → \"{content}\"")
                    if repair.score_breakdown:
                        scores_str = ", ".join(f"{k}={v:.2f}" for k, v in repair.score_breakdown.items())
                        print(f"     (Scores: {scores_str})")
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()

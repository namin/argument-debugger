#!/usr/bin/env python3
"""
Argument Debugger: An LLM+ASP-based system for analyzing and repairing arguments
"""

import json
import clingo
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from google import genai
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

class ArgumentParser:
    """Uses Gemini to parse natural language arguments into formal structure"""
    
    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            api_key = os.getenv('GEMINI_API_KEY')
        
        if api_key:
            self.client = genai.Client(api_key=api_key)
            self.model_available = True
        else:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY environment variable.")
    
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
        
        3. Goal claim: The main conclusion (if identifiable)
        
        CRITICAL INSTRUCTIONS:
        - If there's a gap between premises and conclusion (e.g., "Crime increased. Therefore we need more police"), 
          DO NOT create an inference. Leave the inferences list empty or incomplete to show the gap.
        - For circular reasoning (e.g., "A is true because B. B is true because A"), create both inferences:
          one from A to B and one from B to A.
        - Only include inferences that are explicitly stated or directly implied by logical connectors 
          like "because", "therefore", "since", etc.
        
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
            model="gemini-2.0-flash",
            contents=prompt
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
        
        return Argument(
            claims=claims,
            inferences=inferences,
            goal_claim=data.get('goal_claim')
        )

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
        
        # Check for circular patterns in natural language
        # Look for "A because B" and "B because A" patterns
        for i, claim1 in enumerate(argument.claims):
            for j, claim2 in enumerate(argument.claims):
                if i != j:
                    # Check if claim1 references claim2 and vice versa
                    claim1_lower = claim1.content.lower()
                    claim2_lower = claim2.content.lower()
                    
                    # Look for circular justification patterns
                    if ("because" in claim1_lower and 
                        any(key in claim2_lower for key in ["true", "word of god", "says so"]) and
                        "bible" in claim1_lower and "bible" in claim2_lower):
                        
                        # Check for the specific Bible circular reasoning pattern
                        inference_chain = []
                        for inf in argument.inferences:
                            if inf.to_claim in [claim1.id, claim2.id]:
                                inference_chain.append(inf)
                        
                        if len(inference_chain) >= 2:
                            issues.append(Issue(
                                type="circular",
                                description=f"Circular reasoning: claims justify each other without independent support",
                                involved_claims=[claim1.id, claim2.id]
                            ))
                            break
        
        # Build ASP program
        asp_program = self._build_asp_program(argument)
        
        if self.debug:
            print("=== ASP Program ===")
            print(asp_program)
            print("==================\n")
        
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
        
        if argument.goal_claim:
            program += f'\n% Goal\ngoal("{argument.goal_claim}").\n'
        
        # Add specific facts about empirical claims
        program += "\n% Mark empirical claims that need evidence\n"
        for claim_id, content in claim_contents.items():
            if self._is_empirical_claim(content):
                program += f'empirical_claim("{claim_id}").\n'
        
        # Add facts about dichotomous claims
        program += "\n% Mark dichotomous claims\n"
        for claim_id, content in claim_contents.items():
            if self._is_dichotomous_claim(content):
                program += f'dichotomous_claim("{claim_id}").\n'
                if self.debug:
                    print(f"Marked {claim_id} as dichotomous: {content}")
        
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
        
        % Detect circular reasoning
        depends_on(X, Y) :- inference(Y, X).
        depends_on(X, Z) :- depends_on(X, Y), inference(Z, Y).
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
        % A false dichotomy is when a claim presents exactly two options
        % without proving these are the ONLY options
        false_dichotomy(C) :- 
            dichotomous_claim(C),
            claim(C, _).
        
        % Note: We're marking ALL dichotomous claims as false dichotomies
        % because proving that only two options exist is extremely rare
        % in natural language arguments
        
        #show missing_link/2.
        #show unsupported_premise/1.
        #show circular_reasoning/1.
        #show false_dichotomy/1.
        """
        
        return program
    
    def _is_empirical_claim(self, content: str) -> bool:
        """Check if a claim makes an empirical assertion needing evidence"""
        empirical_indicators = [
            "cause", "causes", "leads to", "results in",
            "increased", "decreased", "rose", "fell",
            "all", "every", "none", "always", "never",
            "percent", "%", "rate", "statistics",
            "study", "research", "data shows"
        ]
        content_lower = content.lower()
        return any(indicator in content_lower for indicator in empirical_indicators)
    
    def _is_dichotomous_claim(self, content: str) -> bool:
        """Check if a claim presents exactly two options"""
        import re
        
        dichotomy_patterns = [
            r"either\s+.+\s+or\s+",  # Changed from .+? to .+ for greedy matching
            r"we must choose between\s+.+\s+and\s+",
            r"if not\s+.+,\s*then\s+",
            r"only two options",
            r"it's\s+.+\s+or\s+",
            r"you're either\s+.+\s+or\s+"
        ]
        
        content_lower = content.lower()
        result = any(re.search(pattern, content_lower) for pattern in dichotomy_patterns)
        
        if self.debug and result:
            print(f"Detected dichotomous claim: {content}")
        
        return result

class RepairGenerator:
    """Generates repairs for identified issues"""
    
    def __init__(self, api_key: Optional[str] = None):
        if not api_key:
            api_key = os.getenv('GEMINI_API_KEY')
        
        if api_key:
            self.client = genai.Client(api_key=api_key)
    
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
                
                # Check if this is an empirical claim that needs evidence
                if self._needs_evidence(claim_content):
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
        
        return repairs
    
    def _get_claim_content(self, argument: Argument, claim_id: str) -> str:
        """Get claim content by ID"""
        for claim in argument.claims:
            if claim.id == claim_id:
                return claim.content
        return ""
    
    def _needs_evidence(self, claim: str) -> bool:
        """Check if a claim is empirical and needs evidence"""
        # Simple heuristic - check for causal/statistical/universal claims
        empirical_indicators = [
            "cause", "causes", "leads to", "results in",
            "all", "every", "none", "always", "never",
            "increase", "decrease", "correlation",
            "percent", "rate", "statistics"
        ]
        claim_lower = claim.lower()
        return any(indicator in claim_lower for indicator in empirical_indicators)
    
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
            model="gemini-2.0-flash",
            contents=prompt
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
            model="gemini-2.0-flash",
            contents=prompt
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
            model="gemini-2.0-flash",
            contents=prompt
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
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        return response.text.strip()

class ArgumentDebugger:
    """Main system that combines all components"""
    
    def __init__(self, api_key: Optional[str] = None, debug: bool = False, show_structure: bool = True):
        self.parser = ArgumentParser(api_key)
        self.analyzer = ASPDebugger(debug=debug)
        self.repairer = RepairGenerator(api_key)
        self.debug = debug
        self.show_structure = show_structure
    
    def debug_argument(self, argument_text: str) -> Dict:
        """Complete debugging pipeline"""
        
        # 1. Parse argument
        print("Parsing argument...")
        argument = self.parser.parse_argument(argument_text)
        
        if self.show_structure:
            print("\nParsed structure:")
            for claim in argument.claims:
                print(f"  {claim.id}: {claim.content} ({claim.type})")
            for inf in argument.inferences:
                print(f"  {inf.from_claims} → {inf.to_claim} ({inf.rule_type})")
        
        # 2. Analyze for issues
        print("\nAnalyzing logical structure...")
        issues = self.analyzer.analyze(argument)
        
        # 3. Generate repairs
        repairs = []
        if issues:
            print(f"\nFound {len(issues)} issues. Generating repairs...")
            repairs = self.repairer.generate_repairs(argument, issues)
        
        # 4. Return complete analysis
        return {
            "argument": argument,
            "issues": issues,
            "repairs": repairs
        }

# Example usage
def main():
    # Example arguments to debug
    examples = [
        # False dichotomy
        """
        Either God does not exist or God is not benevolent because the bible tells many stories of God being cruel, instructing his people to be cruel, and even condoning cruelty.
        """,
        
        # Missing link
        """
        Crime rates have increased in our city.
        Therefore, we need to hire more police officers.
        """,
        
        # Unsupported premise
        """
        Video games cause violence.
        Children play many video games.
        Therefore, we should ban video games for children.
        """,
        
        # Circular reasoning
        """
        The Bible is true because it's the word of God.
        We know it's the word of God because the Bible says so.
        Therefore, we should follow the Bible.
        """,

        # Missing causal link
        """
        Global temperatures are rising.
        Therefore, we should invest in renewable energy.
        """,
        
        # Unsupported generalization
        """
        All politicians are corrupt.
        Senator Smith is a politician.
        Therefore, Senator Smith is corrupt.
        """,
        
        # False dichotomy
        """
        Either we cut social programs or the economy will collapse.
        We cannot let the economy collapse.
        Therefore, we must cut social programs.
        """,
        
        # Ad hominem
        """
        Dr. Johnson argues for climate action.
        Dr. Johnson was arrested for protesting.
        Therefore, we should ignore Dr. Johnson's climate arguments.
        """,
        
        # Slippery slope
        """
        If we allow same-sex marriage, people will want to marry animals.
        We cannot allow people to marry animals.
        Therefore, we should not allow same-sex marriage.
        """
    ]
    
    # Initialize debugger (set debug=True to see ASP programs)
    debugger = ArgumentDebugger(debug=False, show_structure=True)
    
    for i, arg_text in enumerate(examples):
        print(f"\n{'='*60}")
        print(f"EXAMPLE {i+1}")
        print(f"{'='*60}")
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
            
            # Display repairs
            if result['repairs']:
                print("\n🔧 SUGGESTED REPAIRS:")
                for repair in result['repairs']:
                    print(f"  - {repair.type}: {repair.description}")
                    if repair.content:
                        print(f"    → \"{repair.content}\"")
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()

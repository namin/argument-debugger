#!/usr/bin/env python3
"""
Logical Form Analyzer - Deep structure analysis of arguments
Extracts logical predicates, quantifiers, and analyzes validity using ASP
"""

import clingo
from ad import init_llm_client
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from google.genai import types

# Pydantic models for logical structure
class Predicate(BaseModel):
    """A logical predicate like Bird(x) or Flies(x)"""
    name: str = Field(description="Predicate name (e.g., 'bird', 'flies')")
    arguments: List[str] = Field(description="Arguments to the predicate (e.g., ['x'], ['penguin'])")
    negated: bool = Field(default=False, description="Whether the predicate is negated")

class QuantifiedStatement(BaseModel):
    """A quantified statement like ∀x(Bird(x) → Flies(x))"""
    claim_id: str = Field(description="Claim identifier")
    quantifier: Literal["universal", "existential", "none"] = Field(
        description="Type of quantifier: universal (∀), existential (∃), or none"
    )
    variable: Optional[str] = Field(default=None, description="Quantified variable (e.g., 'x')")
    antecedent: Optional[Predicate] = Field(default=None, description="If-part of conditional")
    consequent: Optional[Predicate] = Field(default=None, description="Then-part of conditional")
    predicate: Optional[Predicate] = Field(default=None, description="Simple predicate (non-conditional)")
    connective: Optional[Literal["implies", "and", "or"]] = Field(
        default=None, description="Logical connective between antecedent and consequent"
    )

class LogicalInference(BaseModel):
    """An inference with its pattern"""
    from_claims: List[str] = Field(description="Source claim IDs")
    to_claim: str = Field(description="Target claim ID")
    pattern: str = Field(
        description="Inference pattern: modus_ponens, modus_tollens, syllogism, affirming_consequent, etc."
    )

class LogicalForm(BaseModel):
    """Complete logical structure of an argument"""
    statements: List[QuantifiedStatement] = Field(
        description="All logical statements in the argument"
    )
    inferences: List[LogicalInference] = Field(
        description="Inferences between statements with their patterns"
    )
    goal: Optional[str] = Field(
        default=None, description="ID of the main conclusion"
    )

class LogicalAnalyzer:
    """Analyzes logical form of arguments"""
    
    def __init__(self, debug: bool = False):
        self.client = init_llm_client()
        self.debug = debug
        
    def extract_logical_form(self, argument_text: str) -> LogicalForm:
        """Extract logical structure from natural language argument"""
        
        prompt = f"""
        Analyze this argument and extract its deep logical structure.
        
        Argument: {argument_text}
        
        For each claim, identify:
        1. Logical form (predicates, quantifiers, conditionals)
        2. How claims connect logically
        3. What inference patterns are used
        
        IMPORTANT: Distinguish between:
        - First-order logic (uses variables): "All X are Y", "Some X are Y"  
        - Propositional logic (no variables): "If P then Q", "P and Q"
        
        Examples of logical forms:
        - "All birds fly" → First-order: ∀x(Bird(x) → Flies(x)), use variable 'x'
        - "Penguins are birds" → Predicate: Bird(penguin), specific instance
        - "Some birds walk" → First-order: ∃x(Bird(x) ∧ Walks(x)), use variable 'x'
        - "If it rains, ground is wet" → Propositional: Rains → WetGround, NO variable
        - "You didn't study" → Propositional: ¬StudyHard, NO variable
        
        Examples of inference patterns:
        - modus_ponens: If P then Q, P, therefore Q
        - modus_tollens: If P then Q, not Q, therefore not P
        - syllogism: All A are B, All B are C, therefore All A are C
        - affirming_consequent: If P then Q, Q, therefore P (INVALID!)
        - denying_antecedent: If P then Q, not P, therefore not Q (INVALID!)
        
        Be precise about the logical structure. Identify the exact pattern used.
        """
        
        config = types.GenerateContentConfig(
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            response_mime_type="application/json",
            response_schema=LogicalForm
        )
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=config
        )
        
        return LogicalForm.model_validate_json(response.text)
    
    def build_asp_program(self, logical_form: LogicalForm) -> str:
        """Convert logical form to ASP program"""
        
        program = "% Logical statements\n"
        
        # Add each statement as facts
        for stmt in logical_form.statements:
            claim_id = stmt.claim_id
            
            if stmt.quantifier == "universal" and stmt.antecedent and stmt.consequent:
                # Universal conditional: ∀x(P(x) → Q(x))
                program += f'universal_conditional("{claim_id}", "{stmt.variable}", '
                program += f'"{stmt.antecedent.name}", "{stmt.consequent.name}").\n'
                
            elif stmt.quantifier == "existential" and stmt.predicate:
                # Existential: ∃x P(x)
                program += f'existential("{claim_id}", "{stmt.variable}", "{stmt.predicate.name}").\n'
                
            elif stmt.predicate:  # Handle any predicate, with or without quantifier
                # Simple predicate: P(a)
                pred = stmt.predicate
                if pred.arguments:  # Has arguments
                    for arg in pred.arguments:
                        if pred.negated:
                            program += f'negated_fact("{claim_id}", "{pred.name}", "{arg}").\n'
                        else:
                            program += f'fact("{claim_id}", "{pred.name}", "{arg}").\n'
                        
            elif stmt.antecedent and stmt.consequent and stmt.connective == "implies":
                # Simple conditional (no quantifier): P → Q
                program += f'conditional("{claim_id}", "{stmt.antecedent.name}", "{stmt.consequent.name}").\n'
        
        # Add inferences
        program += "\n% Inferences\n"
        for inf in logical_form.inferences:
            # ASP doesn't support lists directly, so we'll use a different representation
            for from_claim in inf.from_claims:
                program += f'inference_from("{inf.to_claim}", "{from_claim}").\n'
            program += f'inference_pattern("{inf.to_claim}", "{inf.pattern}").\n'
        
        # Add goal if present
        if logical_form.goal:
            program += f'\n% Goal\ngoal("{logical_form.goal}").\n'
        
        # Add ASP rules for detecting issues
        program += """
        
% Valid inference patterns
valid_pattern("modus_ponens").
valid_pattern("modus_tollens").
valid_pattern("universal_instantiation").
valid_pattern("syllogism_barbara").  % All M are P, All S are M, therefore All S are P
valid_pattern("disjunctive_syllogism").

% Invalid inference patterns (formal fallacies)
fallacy("affirming_consequent").
fallacy("denying_antecedent").
fallacy("existential_instantiation_error").  % Some X are Y, a is X, therefore a is Y (invalid!)
fallacy("illicit_major").
fallacy("illicit_minor").

% Detect invalid inferences
invalid_inference(To, Pattern) :-
    inference_pattern(To, Pattern),
    fallacy(Pattern).

% Helper: check if inference is from two specific claims
inference_from_both(To, C1, C2) :-
    inference_from(To, C1),
    inference_from(To, C2),
    C1 != C2.

% Detect modus ponens structure
actual_modus_ponens(C1, C2, C3) :-
    conditional(C1, P, Q),     % If P then Q
    fact(C2, P, _),            % P is true
    fact(C3, Q, _),            % Therefore Q
    inference_from_both(C3, C1, C2),
    inference_pattern(C3, "modus_ponens").

% Detect affirming the consequent
actual_affirming_consequent(C1, C2, C3) :-
    conditional(C1, P, Q),     % If P then Q  
    fact(C2, Q, _),            % Q is true
    fact(C3, P, _),            % Therefore P (INVALID!)
    inference_from_both(C3, C1, C2).

% Detect universal instantiation
valid_universal_instantiation(C1, C2, C3) :-
    universal_conditional(C1, X, Antecedent, Consequent),  % All X: P(X) -> Q(X)
    fact(C2, Antecedent, Instance),                        % P(instance)
    fact(C3, Consequent, Instance),                        % Therefore Q(instance)
    inference_from_both(C3, C1, C2),
    inference_pattern(C3, "universal_instantiation").

% Detect syllogism
valid_barbara(C1, C2, C3) :-
    universal_conditional(C1, X, M, P),  % All M are P
    universal_conditional(C2, Y, S, M),  % All S are M
    universal_conditional(C3, Z, S, P),  % Therefore All S are P
    inference_from_both(C3, C1, C2),
    inference_pattern(C3, "syllogism").

% Detect quantifier errors
quantifier_error(C1, C2, C3) :-
    existential(C1, X, P),    % Some P are Q
    fact(C2, P, A),           % A is P
    fact(C3, Q, A),           % Therefore A is Q (INVALID!)
    inference_from_both(C3, C1, C2).

% Check for missing logical steps
missing_step(To) :-
    inference_pattern(To, Pattern),
    not valid_pattern(Pattern),
    not fallacy(Pattern).

#show invalid_inference/2.
#show actual_affirming_consequent/3.
#show quantifier_error/3.
#show missing_step/1.
#show valid_barbara/3.
#show valid_universal_instantiation/3.
        """
        
        return program
    
    def analyze(self, logical_form: LogicalForm) -> Dict:
        """Analyze logical form using ASP"""
        
        asp_program = self.build_asp_program(logical_form)
        
        if self.debug:
            print("=== ASP Program ===")
            print(asp_program)
            print("==================")
        
        # Run ASP solver
        control = clingo.Control(["--warn=none"])
        control.add("base", [], asp_program)
        control.ground([("base", [])])
        
        issues = []
        valid_inferences = []
        
        with control.solve(yield_=True) as handle:
            for model in handle:
                if self.debug:
                    print(f"Model: {[str(atom) for atom in model.symbols(shown=True)]}")
                
                for atom in model.symbols(shown=True):
                    if atom.name == "invalid_inference":
                        to_claim = str(atom.arguments[0]).strip('"')
                        pattern = str(atom.arguments[1]).strip('"')
                        issues.append({
                            "type": "invalid_inference",
                            "description": f"Invalid inference pattern '{pattern}' used for claim {to_claim}",
                            "pattern": pattern
                        })
                    
                    elif atom.name == "actual_affirming_consequent":
                        c1 = str(atom.arguments[0]).strip('"')
                        c2 = str(atom.arguments[1]).strip('"')
                        c3 = str(atom.arguments[2]).strip('"')
                        issues.append({
                            "type": "affirming_consequent",
                            "description": f"Fallacy of affirming the consequent: [{c1}, {c2}] → {c3}",
                            "claims": [c1, c2, c3]
                        })
                    
                    elif atom.name == "quantifier_error":
                        c1 = str(atom.arguments[0]).strip('"')
                        c2 = str(atom.arguments[1]).strip('"')
                        c3 = str(atom.arguments[2]).strip('"')
                        issues.append({
                            "type": "quantifier_error",
                            "description": f"Invalid quantifier inference: Cannot go from 'some' to specific instance",
                            "claims": [c1, c2, c3]
                        })
                    
                    elif atom.name == "valid_barbara":
                        c1 = str(atom.arguments[0]).strip('"')
                        c2 = str(atom.arguments[1]).strip('"')
                        c3 = str(atom.arguments[2]).strip('"')
                        valid_inferences.append({
                            "type": "valid_syllogism",
                            "description": f"Valid syllogism (Barbara): [{c1}, {c2}] → {c3}"
                        })
                    
                    elif atom.name == "valid_universal_instantiation":
                        c1 = str(atom.arguments[0]).strip('"')
                        c2 = str(atom.arguments[1]).strip('"')
                        c3 = str(atom.arguments[2]).strip('"')
                        valid_inferences.append({
                            "type": "valid_universal_instantiation",
                            "description": f"Valid universal instantiation: [{c1}, {c2}] → {c3}"
                        })
                
                # Only take first model
                break
        
        return {
            "logical_form": logical_form,
            "issues": issues,
            "valid_inferences": valid_inferences
        }
    
    def debug_argument(self, argument_text: str) -> Dict:
        """Complete pipeline: extract and analyze logical form"""
        
        print("Extracting logical form...")
        logical_form = self.extract_logical_form(argument_text)
        
        print("\nLogical Structure:")
        for stmt in logical_form.statements:
            # Handle quantified conditionals (First-order logic)
            if stmt.quantifier and stmt.variable and stmt.variable != "None" and stmt.antecedent and stmt.consequent:
                if stmt.quantifier == "universal":
                    print(f"  {stmt.claim_id}: ∀{stmt.variable}({stmt.antecedent.name}({stmt.variable}) → {stmt.consequent.name}({stmt.variable}))")
                elif stmt.quantifier == "existential":
                    print(f"  {stmt.claim_id}: ∃{stmt.variable}({stmt.antecedent.name}({stmt.variable}) ∧ {stmt.consequent.name}({stmt.variable}))")
            # Handle propositional conditionals (no variables)
            elif stmt.antecedent and stmt.consequent and (not stmt.variable or stmt.variable == "None"):
                ant_neg = "¬" if stmt.antecedent.negated else ""
                cons_neg = "¬" if stmt.consequent.negated else ""
                print(f"  {stmt.claim_id}: {ant_neg}{stmt.antecedent.name} → {cons_neg}{stmt.consequent.name}")
            # Handle predicates with arguments
            elif stmt.predicate:
                neg = "¬" if stmt.predicate.negated else ""
                args = ",".join(stmt.predicate.arguments) if stmt.predicate.arguments else ""
                # If existential quantifier, show it
                if stmt.quantifier == "existential" and stmt.variable:
                    print(f"  {stmt.claim_id}: ∃{stmt.variable}({neg}{stmt.predicate.name}({stmt.variable}))")
                else:
                    print(f"  {stmt.claim_id}: {neg}{stmt.predicate.name}({args})")
        
        print("\nInferences:")
        for inf in logical_form.inferences:
            print(f"  {inf.from_claims} → {inf.to_claim} ({inf.pattern})")
        
        print("\nAnalyzing with ASP...")
        result = self.analyze(logical_form)
        
        return result

def main():
    """Test the logical form analyzer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Logical Form Analyzer')
    parser.add_argument('file', nargs='?', default='examples_logical_form.txt',
                       help='Input file containing arguments (default: examples_logical_form.txt)')
    parser.add_argument('--debug', action='store_true', help='Show ASP program and debug output')
    parser.add_argument('--example', type=int, help='Run a specific example (1-based index)')
    args = parser.parse_args()
    
    # Read examples from file
    print("# Logical Form Analysis")
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
    
    analyzer = LogicalAnalyzer(debug=args.debug)
    
    # Select specific example or run all
    if args.example:
        if 1 <= args.example <= len(examples):
            examples_to_run = [(args.example, examples[args.example - 1])]
        else:
            print(f"Error: Example {args.example} out of range (1-{len(examples)})")
            return
    else:
        examples_to_run = enumerate(examples, 1)
    
    for i, arg_text in examples_to_run:
        print(f"\n{'='*60}")
        print(f"EXAMPLE {i}: {arg_text}")
        print('='*60)
        
        try:
            result = analyzer.debug_argument(arg_text)
            
            if result['issues']:
                print("\n❌ LOGICAL ISSUES FOUND:")
                for issue in result['issues']:
                    print(f"  - {issue['type']}: {issue['description']}")
            
            if result['valid_inferences']:
                print("\n✅ VALID INFERENCES:")
                for valid in result['valid_inferences']:
                    print(f"  - {valid['description']}")
            
            if not result['issues'] and not result['valid_inferences']:
                print("\n⚠️ No formal logical patterns detected")
                
        except Exception as e:
            print(f"Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()
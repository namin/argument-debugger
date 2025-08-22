#!/usr/bin/env python3
"""
Logical Form Analyzer
FOL representation uses plain dataclasses instead of Pydantic for recursive structures
"""

import clingo
from ad import init_llm_client
from dataclasses import dataclass
from typing import List, Dict, Optional, Literal, Union
from google.genai import types
import json

# ============================================================================
# FOL STRUCTURE (using dataclasses)
# ============================================================================

@dataclass
class FOLAtom:
    """Atomic formula: predicate(term1, term2, ...)"""
    predicate: str
    terms: List[str]
    
    def to_string(self) -> str:
        if self.terms:
            return f"{self.predicate}({','.join(self.terms)})"
        else:
            return f"{self.predicate}()"

@dataclass
class FOLFormula:
    """A complete FOL formula"""
    type: Literal["atom", "not", "and", "or", "implies", "iff", "forall", "exists"]
    
    # For atoms
    atom: Optional[FOLAtom] = None
    
    # For unary/binary operators
    left: Optional['FOLFormula'] = None
    right: Optional['FOLFormula'] = None
    
    # For quantifiers
    variable: Optional[str] = None
    body: Optional['FOLFormula'] = None
    
    def to_string(self) -> str:
        if self.type == "atom" and self.atom:
            return self.atom.to_string()
        elif self.type == "not" and self.left:
            return f"¬{self.left.to_string()}"
        elif self.type in ["and", "or", "implies", "iff"] and self.left and self.right:
            symbols = {"and": "∧", "or": "∨", "implies": "→", "iff": "↔"}
            return f"({self.left.to_string()} {symbols[self.type]} {self.right.to_string()})"
        elif self.type in ["forall", "exists"] and self.variable and self.body:
            symbol = "∀" if self.type == "forall" else "∃"
            return f"{symbol}{self.variable}({self.body.to_string()})"
        return "?"

@dataclass
class LogicalStatement:
    """A logical statement with an ID"""
    id: str
    formula: FOLFormula

@dataclass
class LogicalInference:
    """An inference between statements"""
    from_ids: List[str]
    to_id: str
    pattern: str  # modus_ponens, modus_tollens, etc.

@dataclass
class LogicalArgument:
    """Complete logical argument in FOL"""
    statements: List[LogicalStatement]
    inferences: List[LogicalInference]
    goal_id: Optional[str] = None

# ============================================================================
# LOGICAL ANALYZER
# ============================================================================

class LogicalAnalyzer:
    """Analyzes logical form of arguments using FOL"""
    
    def __init__(self, debug: bool = False):
        self.client = init_llm_client()
        self.debug = debug
    
    def parse_formula_json(self, formula_dict: dict) -> FOLFormula:
        """Parse JSON formula representation to FOLFormula object"""
        formula_type = formula_dict.get("type")
        
        if formula_type == "atom":
            return FOLFormula(
                type="atom",
                atom=FOLAtom(
                    predicate=formula_dict["predicate"],
                    terms=formula_dict.get("terms", [])
                )
            )
        elif formula_type == "not":
            return FOLFormula(
                type="not",
                left=self.parse_formula_json(formula_dict["formula"])
            )
        elif formula_type in ["and", "or", "implies", "iff"]:
            return FOLFormula(
                type=formula_type,
                left=self.parse_formula_json(formula_dict["left"]),
                right=self.parse_formula_json(formula_dict["right"])
            )
        elif formula_type in ["forall", "exists"]:
            return FOLFormula(
                type=formula_type,
                variable=formula_dict["variable"],
                body=self.parse_formula_json(formula_dict["body"])
            )
        else:
            raise ValueError(f"Unknown formula type: {formula_type}")
    
    def extract_logical_form(self, argument_text: str) -> LogicalArgument:
        """Extract FOL structure from natural language"""
        
        prompt = f"""
        Convert this argument to First-Order Logic using a JSON representation.
        
        Argument: {argument_text}
        
        Return a JSON object with this structure:
        {{
            "statements": [
                {{
                    "id": "s1",
                    "formula": <formula_object>
                }}
            ],
            "inferences": [
                {{
                    "from_ids": ["s1", "s2"],
                    "to_id": "s3",
                    "pattern": "modus_ponens"
                }}
            ],
            "goal_id": "s3"
        }}
        
        Where <formula_object> can be:
        
        1. ATOMIC: {{"type": "atom", "predicate": "bird", "terms": ["x"]}}
           - Use empty terms [] for propositional predicates like "rains"
        
        2. NEGATION: {{"type": "not", "formula": <formula_object>}}
        
        3. BINARY: {{"type": "and|or|implies|iff", "left": <formula_object>, "right": <formula_object>}}
        
        4. QUANTIFIER: {{"type": "forall|exists", "variable": "x", "body": <formula_object>}}
        
        Examples:
        - "All birds fly" → {{"type": "forall", "variable": "x", "body": {{"type": "implies", "left": {{"type": "atom", "predicate": "bird", "terms": ["x"]}}, "right": {{"type": "atom", "predicate": "flies", "terms": ["x"]}}}}}}
        - "It rains" → {{"type": "atom", "predicate": "rains", "terms": []}}
        - "John is tall" → {{"type": "atom", "predicate": "tall", "terms": ["john"]}}
        
        Identify inference patterns: modus_ponens, modus_tollens, affirming_consequent, 
        denying_antecedent, universal_instantiation, syllogism, hasty_generalization, 
        existential_generalization, disjunctive_syllogism, hypothetical_syllogism
        """
        
        config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json"
        )
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=config
        )
        
        # Parse JSON response
        data = json.loads(response.text)
        
        # Convert to dataclass objects
        statements = []
        for stmt_data in data["statements"]:
            formula = self.parse_formula_json(stmt_data["formula"])
            statements.append(LogicalStatement(
                id=stmt_data["id"],
                formula=formula
            ))
        
        inferences = []
        for inf_data in data.get("inferences", []):
            inferences.append(LogicalInference(
                from_ids=inf_data["from_ids"],
                to_id=inf_data["to_id"],
                pattern=inf_data["pattern"]
            ))
        
        return LogicalArgument(
            statements=statements,
            inferences=inferences,
            goal_id=data.get("goal_id")
        )
    
    def formula_to_asp_facts(self, formula: FOLFormula, stmt_id: str, fact_counter: List[int]) -> str:
        """Convert FOL formula to ASP facts"""
        asp = ""
        fact_id = fact_counter[0]
        fact_counter[0] += 1
        
        if formula.type == "atom" and formula.atom:
            atom = formula.atom
            if not atom.terms:  # Propositional
                asp += f'prop_atom({fact_id}, "{stmt_id}", "{atom.predicate}").\n'
            else:
                asp += f'fol_atom({fact_id}, "{stmt_id}", "{atom.predicate}").\n'
                for i, term in enumerate(atom.terms):
                    if term in ['x', 'y', 'z']:  # Variable
                        asp += f'has_var({fact_id}, {i}, "{term}").\n'
                    else:  # Constant
                        asp += f'has_const({fact_id}, {i}, "{term}").\n'
        
        elif formula.type == "not" and formula.left:
            inner_id = fact_counter[0]
            asp += f'negation({fact_id}, "{stmt_id}", {inner_id}).\n'
            asp += self.formula_to_asp_facts(formula.left, stmt_id, fact_counter)
        
        elif formula.type in ["and", "or", "implies", "iff"] and formula.left and formula.right:
            left_id = fact_counter[0]
            fact_counter[0] += 1
            right_id = fact_counter[0]
            asp += f'binary({fact_id}, "{stmt_id}", "{formula.type}", {left_id}, {right_id}).\n'
            asp += self.formula_to_asp_facts(formula.left, stmt_id, fact_counter)
            asp += self.formula_to_asp_facts(formula.right, stmt_id, fact_counter)
        
        elif formula.type in ["forall", "exists"] and formula.variable and formula.body:
            body_id = fact_counter[0]
            asp += f'quantifier({fact_id}, "{stmt_id}", "{formula.type}", "{formula.variable}", {body_id}).\n'
            asp += self.formula_to_asp_facts(formula.body, stmt_id, fact_counter)
        
        return asp
    
    def build_asp_program(self, argument: LogicalArgument) -> str:
        """Convert logical argument to ASP program"""
        
        program = "% Logical statements as FOL formulas\n"
        fact_counter = [1]  # Mutable counter for fact IDs
        
        # Convert each statement's formula to ASP facts
        for stmt in argument.statements:
            program += f'\n% Statement {stmt.id}: {stmt.formula.to_string()}\n'
            program += f'statement("{stmt.id}").\n'
            program += self.formula_to_asp_facts(stmt.formula, stmt.id, fact_counter)
        
        # Add inferences
        program += "\n% Inferences\n"
        for inf in argument.inferences:
            for from_id in inf.from_ids:
                program += f'inference_from("{inf.to_id}", "{from_id}").\n'
            program += f'inference_pattern("{inf.to_id}", "{inf.pattern}").\n'
        
        # Add goal if present
        if argument.goal_id:
            program += f'\n% Goal\ngoal("{argument.goal_id}").\n'
        
        # Add analysis rules
        program += """

% ============================================================================
% PATTERN DETECTION RULES
% ============================================================================

% Helper: Check if inference is from specific statements
inference_from_both(To, S1, S2) :-
    inference_from(To, S1),
    inference_from(To, S2),
    S1 != S2.

% Detect modus ponens: P→Q, P, therefore Q
valid_modus_ponens(S1, S2, S3) :-
    binary(_, S1, "implies", _, _),
    statement(S2),
    statement(S3),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "modus_ponens").

% Detect modus tollens: P→Q, ¬Q, therefore ¬P
valid_modus_tollens(S1, S2, S3) :-
    binary(_, S1, "implies", _, _),
    negation(_, S2, _),
    negation(_, S3, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "modus_tollens").

% Detect affirming consequent: P→Q, Q, therefore P (INVALID!)
fallacy_affirming_consequent(S1, S2, S3) :-
    binary(_, S1, "implies", _, _),
    statement(S2),
    statement(S3),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "affirming_consequent").

% Detect denying antecedent: P→Q, ¬P, therefore ¬Q (INVALID!)
fallacy_denying_antecedent(S1, S2, S3) :-
    binary(_, S1, "implies", _, _),
    negation(_, S2, _),
    negation(_, S3, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "denying_antecedent").

% Detect universal instantiation: ∀x P(x), therefore P(a)
valid_universal_instantiation(S1, S2) :-
    quantifier(_, S1, "forall", _, _),
    statement(S2),
    inference_from(S2, S1),
    inference_pattern(S2, "universal_instantiation").

% Detect syllogism: All A are B, All B are C, therefore All A are C
valid_syllogism(S1, S2, S3) :-
    quantifier(_, S1, "forall", _, _),
    quantifier(_, S2, "forall", _, _),
    quantifier(_, S3, "forall", _, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "syllogism").

% Detect hasty generalization: P(a), therefore ∀x P(x) (INVALID!)
fallacy_hasty_generalization(S1, S2) :-
    fol_atom(_, S1, _),
    has_const(_, _, _),
    quantifier(_, S2, "forall", _, _),
    inference_from(S2, S1),
    inference_pattern(S2, "hasty_generalization").

% Detect existential generalization: P(a), therefore ∃x P(x) (VALID)
valid_existential_generalization(S1, S2) :-
    fol_atom(_, S1, _),
    quantifier(_, S2, "exists", _, _),
    inference_from(S2, S1),
    inference_pattern(S2, "existential_generalization").

% Invalid patterns
invalid_inference(To, "affirming_consequent") :-
    inference_pattern(To, "affirming_consequent").

invalid_inference(To, "denying_antecedent") :-
    inference_pattern(To, "denying_antecedent").

invalid_inference(To, "hasty_generalization") :-
    inference_pattern(To, "hasty_generalization").

#show valid_modus_ponens/3.
#show valid_modus_tollens/3.
#show fallacy_affirming_consequent/3.
#show fallacy_denying_antecedent/3.
#show valid_universal_instantiation/2.
#show valid_syllogism/3.
#show fallacy_hasty_generalization/2.
#show valid_existential_generalization/2.
#show invalid_inference/2.
        """
        
        return program
    
    def analyze(self, argument: LogicalArgument) -> Dict:
        """Analyze logical argument using ASP"""
        
        asp_program = self.build_asp_program(argument)
        
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
                    atom_name = atom.name
                    
                    if atom_name == "valid_modus_ponens":
                        s1, s2, s3 = [str(arg).strip('"') for arg in atom.arguments]
                        valid_inferences.append({
                            "type": "modus_ponens",
                            "description": f"Valid modus ponens: [{s1}, {s2}] → {s3}"
                        })
                    
                    elif atom_name == "valid_modus_tollens":
                        s1, s2, s3 = [str(arg).strip('"') for arg in atom.arguments]
                        valid_inferences.append({
                            "type": "modus_tollens",
                            "description": f"Valid modus tollens: [{s1}, {s2}] → {s3}"
                        })
                    
                    elif atom_name == "fallacy_affirming_consequent":
                        s1, s2, s3 = [str(arg).strip('"') for arg in atom.arguments]
                        issues.append({
                            "type": "affirming_consequent",
                            "description": f"Fallacy - Affirming the consequent: [{s1}, {s2}] → {s3}"
                        })
                    
                    elif atom_name == "fallacy_denying_antecedent":
                        s1, s2, s3 = [str(arg).strip('"') for arg in atom.arguments]
                        issues.append({
                            "type": "denying_antecedent",
                            "description": f"Fallacy - Denying the antecedent: [{s1}, {s2}] → {s3}"
                        })
                    
                    elif atom_name == "valid_universal_instantiation":
                        s1, s2 = [str(arg).strip('"') for arg in atom.arguments]
                        valid_inferences.append({
                            "type": "universal_instantiation",
                            "description": f"Valid universal instantiation: {s1} → {s2}"
                        })
                    
                    elif atom_name == "valid_syllogism":
                        s1, s2, s3 = [str(arg).strip('"') for arg in atom.arguments]
                        valid_inferences.append({
                            "type": "syllogism",
                            "description": f"Valid syllogism: [{s1}, {s2}] → {s3}"
                        })
                    
                    elif atom_name == "fallacy_hasty_generalization":
                        s1, s2 = [str(arg).strip('"') for arg in atom.arguments]
                        issues.append({
                            "type": "hasty_generalization",
                            "description": f"Fallacy - Hasty generalization: {s1} → {s2}"
                        })
                    
                    elif atom_name == "invalid_inference":
                        to_id = str(atom.arguments[0]).strip('"')
                        pattern = str(atom.arguments[1]).strip('"')
                        issues.append({
                            "type": "invalid_pattern",
                            "description": f"Invalid inference pattern '{pattern}' for statement {to_id}"
                        })
                
                # Only take first model
                break
        
        return {
            "argument": argument,
            "issues": issues,
            "valid_inferences": valid_inferences
        }
    
    def debug_argument(self, argument_text: str) -> Dict:
        """Complete pipeline: extract and analyze logical form"""
        
        print("Extracting logical form...")
        argument = self.extract_logical_form(argument_text)
        
        print("\nLogical Structure:")
        for stmt in argument.statements:
            print(f"  {stmt.id}: {stmt.formula.to_string()}")
        
        print("\nInferences:")
        for inf in argument.inferences:
            print(f"  {inf.from_ids} → {inf.to_id} ({inf.pattern})")
        
        print("\nAnalyzing with ASP...")
        result = self.analyze(argument)
        
        return result

def main():
    """Test the logical form analyzer V3"""
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
                    print(f"  - {issue['description']}")
            
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
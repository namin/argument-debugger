#!/usr/bin/env python3
"""
Logical Form Analyzer
FOL representation uses plain dataclasses instead of Pydantic for recursive structures
"""

import clingo
from logical_form_core import lf_to_core
from lean_bridge import Subgoal, verify_with_lean, verify_ui_with_lean, verify_mt_with_lean, verify_all_chain_with_lean
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

% Helper: check if an inference uses two specific premises (order-insensitive).
inference_from_both(To, S1, S2) :-
    inference_from(To, S1),
    inference_from(To, S2),
    S1 != S2.

% ----------------------------------------------------------------------------
% Valid patterns
% ----------------------------------------------------------------------------

% Modus Ponens: P→Q, P ⊢ Q
valid_modus_ponens(Simp, Sprem, Sgoal) :-
    binary(_, Simp, "implies", _, _),
    statement(Sprem),
    statement(Sgoal),
    inference_from_both(Sgoal, Simp, Sprem),
    inference_pattern(Sgoal, "modus_ponens").

% Modus Tollens: P→Q, ¬Q ⊢ ¬P
valid_modus_tollens(Simp, SnegQ, SnegP) :-
    binary(_, Simp, "implies", _, _),
    negation(_, SnegQ, _),
    negation(_, SnegP, _),
    inference_from_both(SnegP, Simp, SnegQ),
    inference_pattern(SnegP, "modus_tollens").

% Universal Instantiation (UI): ∀x (P x → Q x), P c ⊢ Q c
% Keep 2-arity output (∀-statement, goal) but *require* that the inference
% cites both the ∀-premise and some instance premise.
valid_universal_instantiation(Sforall, Sgoal) :-
    quantifier(_, Sforall, "forall", _, _),
    statement(Sgoal),
    inference_from_both(Sgoal, Sforall, Sinst),
    statement(Sinst),
    inference_pattern(Sgoal, "universal_instantiation").

% Universal syllogism / chain:
% ∀x (A→B), ∀x (B→C) ⊢ ∀x (A→C)
% Accept both labels by using two rules with the same head.

valid_syllogism(S1, S2, S3) :-
    quantifier(_, S1, "forall", _, _),
    quantifier(_, S2, "forall", _, _),
    quantifier(_, S3, "forall", _, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "syllogism").

valid_syllogism(S1, S2, S3) :-
    quantifier(_, S1, "forall", _, _),
    quantifier(_, S2, "forall", _, _),
    quantifier(_, S3, "forall", _, _),
    inference_from_both(S3, S1, S2),
    inference_pattern(S3, "hypothetical_syllogism").

% Existential Generalization (EG): P(c) ⊢ ∃x P(x)
valid_existential_generalization(Sinst, Sexists) :-
    fol_atom(_, Sinst, _),
    quantifier(_, Sexists, "exists", _, _),
    inference_from(Sexists, Sinst),
    inference_pattern(Sexists, "existential_generalization").

% ----------------------------------------------------------------------------
% Fallacies
% ----------------------------------------------------------------------------

% Affirming the Consequent: P→Q, Q ⊢ P
fallacy_affirming_consequent(Simp, Sq, Sp) :-
    binary(_, Simp, "implies", _, _),
    statement(Sq),
    statement(Sp),
    inference_from_both(Sp, Simp, Sq),
    inference_pattern(Sp, "affirming_consequent").

% Denying the Antecedent: P→Q, ¬P ⊢ ¬Q
fallacy_denying_antecedent(Simp, SnegP, SnegQ) :-
    binary(_, Simp, "implies", _, _),
    negation(_, SnegP, _),
    negation(_, SnegQ, _),
    inference_from_both(SnegQ, Simp, SnegP),
    inference_pattern(SnegQ, "denying_antecedent").

% Hasty Generalization: P(c) ⊢ ∀x P(x)
fallacy_hasty_generalization(Sinst, Sforall) :-
    fol_atom(_, Sinst, _),
    has_const(_, _, _),
    quantifier(_, Sforall, "forall", _, _),
    inference_from(Sforall, Sinst),
    inference_pattern(Sforall, "hasty_generalization").

% ----------------------------------------------------------------------------
% Show only specific valid/fallacy predicates (no generic invalid_inference).
% ----------------------------------------------------------------------------
#show valid_modus_ponens/3.
#show valid_modus_tollens/3.
#show valid_universal_instantiation/2.
#show valid_syllogism/3.
#show valid_existential_generalization/2.
#show fallacy_affirming_consequent/3.
#show fallacy_denying_antecedent/3.
#show fallacy_hasty_generalization/2.
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
    
        return result, argument

def fully_verify_with_lean(argument: LogicalArgument) -> Dict:
    try:
        ran_any_check = False
        print("\nLean micro‑verification:")

        # (A) Propositional chain check — only if there are actual edges
        core = lf_to_core(argument)
        if core.implications and core.facts:
            ran_any_check = True
            for g in (core.goals or []):
                sg = Subgoal(
                    atoms=core.atoms,
                    implications=core.implications,
                    facts=core.facts,
                    goal=g,
                    name=f"lf_{g}"
                )
                res = verify_with_lean(sg)
                print(f"  chain goal={g}: {'Verified ✅' if res.verified else 'Not verified ❌'}")
                if res.lean_file:
                    print(f"    artifact: {res.lean_file}")
                if not res.verified and res.message:
                    print("    note:", res.message.splitlines()[0])
        # else: stay silent (no “Not verified” noise when there is nothing to check)

        # (B) Universal Instantiation checks (first‑order)
        ui_checks = 0
        for inf in argument.inferences:
            if inf.pattern != "universal_instantiation":
                continue
            ui_checks += 1
            ran_any_check = True

            s_forall = next((s for s in argument.statements
                                if s.id in inf.from_ids and s.formula.type == "forall"), None)
            s_other  = next((s for s in argument.statements
                                if s.id in inf.from_ids and s is not s_forall), None)
            s_goal   = next((s for s in argument.statements if s.id == inf.to_id), None)

            ok = False; artifact = None; note = ""
            if s_forall and s_other and s_goal:
                body = s_forall.formula.body
                if body and body.type == "implies" and body.left and body.right:
                    L, R = body.left, body.right
                    if (L.type == "atom" and R.type == "atom" and
                        s_other.formula.type == "atom" and s_goal.formula.type == "atom"):
                        # Require unary predicates and matching constant
                        if len(L.atom.terms) == 1 and len(R.atom.terms) == 1 \
                            and len(s_other.formula.atom.terms) == 1 \
                            and len(s_goal.formula.atom.terms) == 1:
                            const = s_other.formula.atom.terms[0]
                            if s_goal.formula.atom.terms[0] == const:
                                ok, artifact, note = verify_ui_with_lean(
                                    L.atom.predicate, R.atom.predicate, const,
                                    name=f"ui_{inf.to_id}"
                                )
                            else:
                                note = "goal constant doesn’t match premise constant"
                        else:
                            note = "non‑unary predicates; UI check skipped"
                    else:
                        note = "expected atomic predicates in ∀x (P x -> Q x)"
                else:
                    note = "∀ body is not an implication"
            else:
                note = "couldn’t line up ∀, instance premise, and goal"

            print(f"  UI {inf.from_ids} → {inf.to_id}: {'Verified ✅' if ok else 'Not verified ❌'}")
            if artifact:
                print(f"    artifact: {artifact}")
            if note and not ok:
                print("    note:", note.splitlines()[0])

        for inf in argument.inferences:
            if inf.pattern != "modus_tollens":
                continue
            s_imp = next((s for s in argument.statements if s.id in inf.from_ids and s.formula.type == "implies"), None)
            s_negQ = next((s for s in argument.statements if s.id in inf.from_ids and s is not s_imp), None)
            s_goal = next((s for s in argument.statements if s.id == inf.to_id), None)

            ok = False; artifact = None; note = ""
            if s_imp and s_negQ and s_goal:
                L, R = s_imp.formula.left, s_imp.formula.right
                if (L and R and L.type == "atom" and R.type == "atom" and
                    s_negQ.formula.type == "not" and s_negQ.formula.left and s_negQ.formula.left.type == "atom" and
                    s_goal.formula.type == "not" and s_goal.formula.left and s_goal.formula.left.type == "atom" and
                    not L.atom.terms and not R.atom.terms and
                    not s_negQ.formula.left.atom.terms and not s_goal.formula.left.atom.terms and
                    s_negQ.formula.left.atom.predicate == R.atom.predicate and
                    s_goal.formula.left.atom.predicate == L.atom.predicate):
                    ok, artifact, note = verify_mt_with_lean(L.atom.predicate, R.atom.predicate, name=f"mt_{inf.to_id}")
                else:
                    note = "non-propositional MT; skipping"
            else:
                note = "could not line up MT components"
            print(f"  MT {inf.from_ids} → {inf.to_id}: {'Verified ✅' if ok else 'Not verified ❌'}")
            if artifact: print(f"    artifact: {artifact}")
            if note and not ok: print("    note:", note.splitlines()[0])

        for inf in argument.inferences:
            if inf.pattern != "hypothetical_syllogism":
                continue
            s1 = next((s for s in argument.statements if s.id in inf.from_ids and s.formula.type == "forall"), None)
            s2 = next((s for s in argument.statements if s.id in inf.from_ids and s.formula.type == "forall" and s is not s1), None)
            s3 = next((s for s in argument.statements if s.id == inf.to_id and s.formula.type == "forall"), None)

            ok = False; artifact = None; note = ""
            if s1 and s2 and s3:
                def parse_imp(s):
                    b = s.formula.body
                    return (b.left, b.right) if b and b.type == "implies" else (None, None)
                L1, R1 = parse_imp(s1); L2, R2 = parse_imp(s2); L3, R3 = parse_imp(s3)
                if all([L1, R1, L2, R2, L3, R3]) and \
                all(x.type == "atom" and len(x.atom.terms) == 1 for x in [L1, R1, L2, R2, L3, R3]):
                    if R1.atom.predicate == L2.atom.predicate and \
                    L1.atom.predicate == L3.atom.predicate and \
                    R2.atom.predicate == R3.atom.predicate:
                        ok, artifact, note = verify_all_chain_with_lean(
                            L1.atom.predicate, R1.atom.predicate, R2.atom.predicate,
                            name=f"all_chain_{inf.to_id}"
                        )
                    else:
                        note = "predicate mismatch in ∀-chain"
                else:
                    note = "expected unary predicate implications under ∀"
            else:
                note = "could not line up ∀-chain components"

            print(f"  ∀-chain {inf.from_ids} → {inf.to_id}: {'Verified ✅' if ok else 'Not verified ❌'}")
            if artifact: print(f"    artifact: {artifact}")
            if note and not ok: print("    note:", note.splitlines()[0])
            
        if not ran_any_check:
            print("  (nothing to verify for this example)")

    except Exception as e:
        print(f"\nLean micro‑verification error: {e}")

def main():
    """Test the logical form analyzer V3"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Logical Form Analyzer')
    parser.add_argument('file', nargs='?', default='examples_logical_form.txt',
                       help='Input file containing arguments (default: examples_logical_form.txt)')
    parser.add_argument('--lean', action='store_true', help='Verify with Lean')
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
        print(f"\n# EXAMPLE {i}\n{arg_text}\n")
        
        try:
            result, argument = analyzer.debug_argument(arg_text)
            
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

            if args.lean:
                print("\nVerifying with Lean...")
                fully_verify_with_lean(argument)

        except Exception as e:
            print(f"Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()

# argfol — minimal FOL→TPTP→E prover glue

This is a tiny, self-contained module you can drop into your codebase to:

1. Build FOL formulas via a small Python AST.
2. Emit TPTP FOF problems.
3. Call **E prover** and parse SZS status + (optional) TSTP proof.

## Install E prover

- macOS (Homebrew): `brew install eprover`
- Ubuntu/Debian: `sudo apt-get install eprover`
- From source: https://wwwlehre.dhbw-stuttgart.de/~sschulz/E/E.html

## Quick start

```bash
python -m argfol.demo_socrates
```

Expected:

- TPTP problem printed
- E prover SZS status `Theorem`
- Optional TSTP proof based on your E version/flags

## Python API

```python
from argfol.fol_ast import Var, Const, Pred, Forall, Implies, AtomF
from argfol.tptp import to_tptp_problem
from argfol.eprover import prove_with_e

X = Var('X')
human = lambda t: Pred('human', [t])
mortal = lambda t: Pred('mortal', [t])
socrates = Const('socrates')

axioms = {
  'humans_are_mortal': Forall([X], Implies(AtomF(human(X)), AtomF(mortal(X)))),
  'socrates_is_human': AtomF(human(socrates)),
}
conj = AtomF(mortal(socrates))

tptp = to_tptp_problem(axioms, conj)
res = prove_with_e(tptp, cpu_limit=5)  # ensure 'eprover' is on PATH
print(res.status)
print(res.used_axioms)
print(res.proof_tstp)
```

## CLI (when your LLM emits FOF strings)

Prepare `problem.json`:

```json
{
  "axioms": {
    "humans_are_mortal": "![X] : ( human(X) => mortal(X) )",
    "socrates_is_human": "human(socrates)"
  },
  "conjecture": "mortal(socrates)"
}
```

Then:

```bash
python -m argfol.argfol_prove problem.json
```

## NL→FOL (bring your own parser)

The package purposely stays out of semantic parsing. In your Argument Debugger:

- Have the LLM output either (a) the `fol_ast` constructors via JSON, or (b) direct TPTP FOF strings.
- Feed that into `to_tptp_problem` or the CLI, then call `prove_with_e`.

Suggested JSON for AST emission (example):

```json
{
  "axioms": [
    {"name": "humans_are_mortal",
     "formula": ["forall", ["X"],
       ["implies", ["pred", "human", ["var", "X"]],
                   ["pred", "mortal", ["var", "X"]]]]
    },
    {"name": "socrates_is_human",
     "formula": ["pred", "human", ["const", "socrates"]]
    }
  ],
  "conjecture": ["pred", "mortal", ["const", "socrates"]]
}
```

You can write a tiny interpreter that turns this JSON into `fol_ast` objects.

## Notes

- We use **FOF** (untyped first-order form). If you later want types/sorts, target **TFF** and call `eprover` or other provers accordingly.
- We don't perform Skolemization—E will handle CNF internally. Keep quantifiers explicit.
- `used_axioms` extraction is heuristic (depends on E output). For auditable pipelines, consider saving the entire TSTP proof.
- Timeouts: adjust `cpu_limit` or pass extra args to E via `extra_args=[...]`.

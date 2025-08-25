# Argument Debugger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/namin/argument-debugger)

_an LLM+ASP system for analyzing and repairing arguments_

## Install

```bash
pip install clingo google-genai
```

## Run

```bash
export GEMINI_API_KEY=... # or
export GOOGLE_CLOUD_PROJECT=...
python ad.py
```

You can run with a custom file of examples, each separated by two newlines.
```bash
python ad.py examples.txt
```

See [sample output](output.md).

See [testing](TESTING.md).

See [our tutorial](TUTORIAL.md) on encoding arguments in Answer Set Programming (ASP).

## Key Components of Current Prototype

### Processing Flow

```
Natural Language Argument
         ↓
[1. ArgumentParser] → LLM extracts claims and inferences
         ↓
Formal Structure (claims, inferences)
         ↓
[2. ASPDebugger] → Clingo identifies logical issues
         ↓
List of Issues (missing_link, circular, etc.)
         ↓
[3. RepairGenerator] → LLM generates a comprehensive repair
         ↓
Apply Repair & Re-analyze
         ↓
Show Remaining Issues
```

### Component Details

- **ArgumentParser**: Uses LLM to extract formal structure from natural language
  - Identifies claims (premises, intermediates, conclusions)
  - Maps inference relationships
  - Detects argument goals

- **ASPDebugger**: Uses Clingo to analyze logical structure
  - Detects missing links between claims
  - Finds unsupported premises
  - Identifies circular reasoning (including transitive)
  - Detects false dichotomies
  - Checks goal reachability

- **RepairGenerator**: Uses LLM to generate comprehensive fixes

- **ArgumentDebugger**: Orchestrates the full pipeline

## Entry Points

- [ad.py](ad.py): main experiment.
- [ad_baseline.py](ad_baseline.py): a whole-LLM baseline from a single prompt to issue detection. Compatible with tests.
- [ad_debate.py](ad_debate.py): analyzes the debate frontier.
- [logical_form.py](logical_form.py): encoding to First-Order Logic (FOL), with detecting using ASP and certification in Lean. See dedicated [tutorial](TUTORIAL_FOL.md). The `--lean` extension requires the [Lean](https://leanprover-community.github.io/) theorem prover via the `lean` command line program.
- [run_unified.py](run_unified.py): from natural language to argumentation semantics to argument debugger for winning set; related files are [nl2apx.py](nl2apx.py), [af_clingo.py](af_clingo.py) and [unified_core.py](unified_core.py). See dedicated tutorial [tutorial](TUTORIAL_AS.md).
- [apxsolve.py](apxsolve.py): a bare-bones alternative to [af_clingo.py](af_clingo.py) for solving argumentation semantics.
- [app](APP.md): a web app that integrates some of these functions.

## References

- [Datasets](DATASETS.md): datasets we could use
- Argumentation Semantics ([cheatsheet](ARGUMENTATION_SEMANTICS.md)):
  - [_An introduction to argumentation semantics_](https://doi.org/10.1017/S0269888911000166). Baroni, Caminada & Giacomin (2011).
  - [_On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games_](https://www.sciencedirect.com/science/article/pii/000437029400041X). Dung (1995).
- [ASP encodings for several semantics and reasoning tasks in Dung AFs](https://www.dbai.tuwien.ac.at/research/argumentation/aspartix/dung.html)
- [International Competition on Computational Models of Argumentation (ICCMA)](https://www.argumentationcompetition.org/)
- [ArgDown](https://argdown.org/)
- [Argunauts: Open LLMs that Master Argument Analysis with Argdown](https://huggingface.co/blog/ggbetz/argunauts-intro)
- [NL2FOL](https://github.com/lovishchopra/NL2FOL): Translating Natural Language to First-Order Logic for Logical Fallacy Detection

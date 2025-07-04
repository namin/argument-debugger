# Argument Debugger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

_an LLM+ASP-based system for analyzing and repairing arguments_

## Install

```bash
pip install clingo google-genai
```

## Run

```bash
export GEMINI_API_KEY=...
python ad.py
```

You can run with a custom file of examples, each separated by two newlines.
```bash
python ad.py examples.txt
```

See [sample output](output.md).

See [our tutorial](TUTORIAL.md) on encoding arguments in Answer Set Programming (ASP).

## Key Components of Current Prototype

- ArgumentParser: Uses LLM to extract formal structure from natural language
  - Identifies claims (premises, intermediates, conclusions)
  - Maps inference relationships
  - Detects argument goals

- ASPDebugger: Uses Clingo to analyze logical structure
  - Detects missing links between claims
  - Finds unsupported premises
  - Identifies circular reasoning (including transitive)
  - Detects false dichotomies
  - Checks goal reachability

- RepairGenerator: Uses Gemini to suggest concrete fixes
  - Generates bridging premises for missing links
  - Suggests supporting evidence for unsupported claims
  - Recommends removing circular dependencies
  - Proposes alternative options for false dichotomies

- ArgumentDebugger: Orchestrates the full pipeline

## References for Future Work

- [ASP encodings for serveral semantics and reasoning tasks in Dung AFs](https://www.dbai.tuwien.ac.at/research/argumentation/aspartix/dung.html)
- [International Competition on Computational Models of Argumentation (ICCMA)](https://www.argumentationcompetition.org/)
- [ArgDown](https://argdown.org/)
- [Argunauts: Open LLMs that Master Argument Analysis with Argdown](https://huggingface.co/blog/ggbetz/argunauts-intro)

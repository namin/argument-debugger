# Argument Debugger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Install

```bash
pip install clingo google-genai
```

## Run

```bash
export GEMINI_API_KEY=...
python ad.py
```

## Key Components of Current Prototype

- ArgumentParser: Uses LLM to extract formal structure from natural language
  - Identifies claims (premises, intermediates, conclusions)
  - Maps inference relationships
  - Detects argument goals

- ASPDebugger: Uses Clingo to analyze logical structure
  - Detects missing links between claims
  - Finds unsupported premises
  - Identifies circular reasoning
  - Checks goal reachability

- RepairGenerator: Uses Gemini to suggest concrete fixes
  - Generates bridging premises for missing links
  - Suggests supporting evidence for unsupported claims
  - Recommends removing circular dependencies

- ArgumentDebugger: Orchestrates the full pipeline

## References for Future Work

- [ASP encodings for serveral semantics and reasoning tasks in Dung AFs](https://www.dbai.tuwien.ac.at/research/argumentation/aspartix/dung.html)
- [International Competition on Computational Models of Argumentation (ICCMA)_](https://www.argumentationcompetition.org/)
- [ArgDown](https://argdown.org/)
- [Argunauts: Open LLMs that Master Argument Analysis with Argdown](https://huggingface.co/blog/ggbetz/argunauts-intro)

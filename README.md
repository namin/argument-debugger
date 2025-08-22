# Argument Debugger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/namin/argument-debugger)

_an LLM+ASP-based system for analyzing and repairing arguments_

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
[3. RepairGenerator] → LLM generates repairs for each issue
         ↓
[4. Repair Ranking] → Scores each repair
         ↓
Ranked Repairs
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

- **RepairGenerator**: Uses LLM to suggest and rank concrete fixes
  - Generates bridging premises for missing links
  - Suggests supporting evidence for unsupported claims
  - Recommends removing circular dependencies
  - Proposes alternative options for false dichotomies
  - Ranks repairs by minimality, plausibility, relevance, and evidence quality

- **ArgumentDebugger**: Orchestrates the full pipeline

## Testing

The project includes a test framework to ensure the Argument Debugger correctly identifies logical issues.

### Running Tests

```bash
# Run all tests
python test_runner.py --all

# Run a specific test
python test_runner.py tests/test_circular.txt

# Run with verbose output to see what issues were found
python test_runner.py --all -v
```

### Creating New Tests

1. Create a test file with your argument:
```bash
echo "All birds can fly.
Penguins are birds.
Therefore, penguins can fly." > tests/test_penguin.txt
```

2. Run the test with `--update` to capture current behavior:
```bash
python test_runner.py tests/test_penguin.txt --update
```

3. Edit the generated `.expected.json` file to specify what should be found:
```json
{
  "must_find": ["unsupported_premise"],
  "may_find": [],
  "must_not_find": ["circular", "false_dichotomy"]
}
```

### Test Organization

Tests are named by the issue type they test:
- `test_circular*.txt` - Circular reasoning tests
- `test_dichotomy*.txt` - False dichotomy detection
- `test_empirical*.txt` - Empirical claim detection
- `test_valid*.txt` - Valid arguments (should find no issues)

### Expected Results Format

Each test has a corresponding `.expected.json` file:
- `must_find`: Issue types that MUST be detected
- `may_find`: Issue types that might be detected (non-deterministic)
- `must_not_find`: Issue types that should NOT be detected (would be false positives)

The test framework handles LLM non-determinism by checking issue types rather than exact text matches.

## References for Future Work

- [ASP encodings for several semantics and reasoning tasks in Dung AFs](https://www.dbai.tuwien.ac.at/research/argumentation/aspartix/dung.html)
- [International Competition on Computational Models of Argumentation (ICCMA)](https://www.argumentationcompetition.org/)
- [ArgDown](https://argdown.org/)
- [Argunauts: Open LLMs that Master Argument Analysis with Argdown](https://huggingface.co/blog/ggbetz/argunauts-intro)
- [NL2FOL](https://github.com/lovishchopra/NL2FOL): Translating Natural Language to First-Order Logic for Logical Fallacy Detection


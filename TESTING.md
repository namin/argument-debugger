## Testing

The project includes a test framework to ensure the Argument Debugger correctly identifies logical issues.

## Running Tests

```bash
# Run all tests
python test_runner.py --all

# Run a specific test
python test_runner.py tests/test_circular.txt

# Run with verbose output to see what issues were found
python test_runner.py --all -v
```

## Creating New Tests

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

## Test Organization

Tests are named by the issue type they test:
- `test_circular*.txt` - Circular reasoning tests
- `test_dichotomy*.txt` - False dichotomy detection
- `test_empirical*.txt` - Empirical claim detection
- `test_valid*.txt` - Valid arguments (should find no issues)

## Expected Results Format

Each test has a corresponding `.expected.json` file:
- `must_find`: Issue types that MUST be detected
- `may_find`: Issue types that might be detected (non-deterministic)
- `must_not_find`: Issue types that should NOT be detected (would be false positives)

The test framework handles LLM non-determinism by checking issue types rather than exact text matches.

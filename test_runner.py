#!/usr/bin/env python3
"""
Simple test framework for the Argument Debugger
"""

import json
import sys
import os
from pathlib import Path
import argparse
from typing import Dict, List, Optional
import subprocess
import tempfile

class TestRunner:
    def __init__(self, verbose=False, use_baseline=False):
        self.verbose = verbose
        self.use_baseline = use_baseline
        self.results = []
    
    def run_debugger(self, test_file: str, use_baseline: bool = False) -> Dict:
        """Run the argument debugger and capture output"""
        # Run ad.py or ad_baseline.py with --no-repairs flag and capture JSON-like output
        script = "ad_baseline.py" if use_baseline else "ad.py"
        cmd = [sys.executable, script, test_file, "--no-repairs"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Parse the output to extract issues
            return self.parse_output(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error running debugger: {e}")
            if self.verbose:
                print(f"stderr: {e.stderr}")
            return {"issues": []}
    
    def parse_output(self, output: str) -> Dict:
        """Parse the text output to extract issue types"""
        issues = []
        in_issues_section = False
        
        for line in output.split('\n'):
            if "ISSUES FOUND" in line:
                in_issues_section = True
                continue
            if in_issues_section and line.strip().startswith("-"):
                # Extract issue type from line like "  - circular: Circular reasoning detected"
                parts = line.strip().lstrip("- ").split(":")
                if parts:
                    issue_type = parts[0].strip()
                    issues.append({"type": issue_type})
            elif in_issues_section and not line.strip():
                # End of issues section
                in_issues_section = False
        
        return {"issues": issues}
    
    def load_expected(self, expected_file: str) -> Dict:
        """Load expected results from JSON file"""
        if not os.path.exists(expected_file):
            return {}
        
        with open(expected_file, 'r') as f:
            return json.load(f)
    
    def save_expected(self, expected_file: str, output: Dict):
        """Save current output as expected (for --update mode)"""
        # Extract just the issue types
        issue_types = [issue["type"] for issue in output.get("issues", [])]
        unique_types = sorted(list(set(issue_types)))
        
        expected = {
            "must_find": unique_types,
            "may_find": [],
            "must_not_find": []
        }
        
        with open(expected_file, 'w') as f:
            json.dump(expected, f, indent=2)
        
        print(f"Updated {expected_file}")
    
    def compare_results(self, test_name: str, output: Dict, expected: Dict) -> bool:
        """Compare actual output with expected results"""
        if not expected:
            print(f"  ⚠️  {test_name}: No expected results file")
            return True  # Don't fail if no expectations set
        
        found_types = [issue["type"] for issue in output.get("issues", [])]
        found_types_set = set(found_types)
        
        passed = True
        messages = []
        
        # Check must_find
        for must in expected.get("must_find", []):
            if must not in found_types_set:
                messages.append(f"Missing required issue: {must}")
                passed = False
        
        # Check must_not_find
        for must_not in expected.get("must_not_find", []):
            if must_not in found_types_set:
                messages.append(f"Found forbidden issue: {must_not}")
                passed = False
        
        # Check status
        if expected.get("may_find", []):
            if not found_types_set:
                messages.append("No issues found, but expected some")
                passed = False

        # Display result
        if passed:
            print(f"  ✅ {test_name}: PASS")
        else:
            print(f"  ❌ {test_name}: FAIL")
            for msg in messages:
                print(f"     - {msg}")
        
        if self.verbose:
            print(f"     Found issues: {sorted(found_types_set)}")
        
        return passed
    
    def run_test(self, test_file: str, update: bool = False) -> bool:
        """Run a single test"""
        test_name = Path(test_file).stem
        expected_file = test_file.replace('.txt', '.expected.json')
        
        # Run the debugger
        output = self.run_debugger(test_file, use_baseline=self.use_baseline)
        
        if update:
            # Update mode: save current output as expected
            self.save_expected(expected_file, output)
            return True
        else:
            # Test mode: compare with expected
            expected = self.load_expected(expected_file)
            return self.compare_results(test_name, output, expected)
    
    def run_all_tests(self, test_dir: str = ".", update: bool = False) -> None:
        """Run all test_*.txt files"""
        test_files = sorted(Path(test_dir).glob("test_*.txt"))
        
        if not test_files:
            print("No test files found (test_*.txt)")
            return
        
        print(f"\n{'='*60}")
        print(f"Running {len(test_files)} tests...")
        print(f"{'='*60}\n")
        
        passed = 0
        failed = 0
        
        for test_file in test_files:
            result = self.run_test(str(test_file), update)
            if result:
                passed += 1
            else:
                failed += 1
        
        if not update:
            print(f"\n{'='*60}")
            print(f"Results: {passed} passed, {failed} failed")
            print(f"{'='*60}\n")
            
            if failed > 0:
                sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Test runner for Argument Debugger')
    parser.add_argument('test_file', nargs='?', help='Specific test file to run')
    parser.add_argument('--all', action='store_true', help='Run all test_*.txt files')
    parser.add_argument('--update', action='store_true', 
                       help='Update expected results with current output')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Show detailed output')
    parser.add_argument('--dir', default='tests', help='Directory to search for tests')
    parser.add_argument('--baseline', action='store_true',
                       help='Use ad_baseline.py instead of ad.py')
    
    args = parser.parse_args()
    
    runner = TestRunner(verbose=args.verbose, use_baseline=args.baseline)
    
    if args.all:
        runner.run_all_tests(args.dir, update=args.update)
    elif args.test_file:
        runner.run_test(args.test_file, update=args.update)
    else:
        print("Please specify a test file or use --all")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Baseline single-shot argument debugger for comparison with multi-step approach
"""

from llm import init_llm_client, generate_content
from pydantic import BaseModel, Field
from typing import List, Dict
from google.genai import types

class DetectedIssue(BaseModel):
    """Simple issue structure for baseline detection"""
    type: str = Field(
        description="Issue type: missing_link, unsupported_premise, contradiction, circular, false_dichotomy, or slippery_slope"
    )
    description: str = Field(description="Clear description of the issue")

class IssueDetectionResult(BaseModel):
    """Structured output for single-shot issue detection"""
    issues: List[DetectedIssue] = Field(
        default_factory=list,
        description="List of logical issues found in the argument"
    )

def detect_issues_single_shot(argument_text: str) -> List[DetectedIssue]:
    """
    Detect logical issues in a single LLM call
    """
    client = init_llm_client()
    
    prompt = f"""Analyze the following argument for logical issues. Identify any of these specific problem types:

1. **missing_link**: A gap in reasoning where a conclusion doesn't follow from the premises without additional unstated assumptions
2. **unsupported_premise**: A premise that lacks justification or evidence  
3. **contradiction**: Claims that are logically inconsistent with each other
4. **circular**: Circular reasoning where the conclusion is used to support itself
5. **false_dichotomy**: Presenting only two options when more exist
6. **slippery_slope**: Claiming one event will lead to extreme consequences without justification

Be precise and only report issues that are clearly present. For each issue found, specify:
- The exact type from the list above
- A clear description of what makes it problematic

Argument to analyze:
{argument_text}

Return a structured list of issues found."""

    config = types.GenerateContentConfig(
        temperature=0.1,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=IssueDetectionResult
    )
    
    response = generate_content(
        client,
        model="gemini-2.5-flash",
        contents=prompt,
        config=config
    )
    
    # Parse the structured response
    import json
    result = json.loads(response.text)
    
    return [DetectedIssue(**issue) for issue in result.get('issues', [])]

def main():
    import sys
    import argparse
    
    # Set up argument parser (compatible with ad.py)
    parser = argparse.ArgumentParser(description='Baseline Argument Debugger: Single-shot logical analysis')
    parser.add_argument('file', nargs='?', default='examples/examples.txt', 
                       help='Input file containing arguments (default: examples.txt)')
    parser.add_argument('--debug', action='store_true', 
                       help='Show debug output')
    parser.add_argument('--no-repairs', action='store_true',
                       help='Skip generating repairs (always true for baseline)')
    parser.add_argument('--no-structure', action='store_true',
                       help='Hide parsed structure output (always true for baseline)')
    
    args = parser.parse_args()
    
    print("# Output (Baseline Single-Shot Version)")
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
    
    for i, arg_text in enumerate(examples):
        print(f"\n## EXAMPLE {i+1}")
        print("Argument:", arg_text.strip())
        
        try:
            issues = detect_issues_single_shot(arg_text)
            
            # Display issues in same format as ad.py
            if issues:
                print("\n🔍 ISSUES FOUND:")
                for issue in issues:
                    print(f"  - {issue.type}: {issue.description}")
            else:
                print("\n✅ No logical issues found!")
        
        except Exception as e:
            print(f"Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()
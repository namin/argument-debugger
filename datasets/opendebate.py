#!/usr/bin/env python3
"""
Converter for OpenEvidenceDebate dataset to argument debugger format
"""

from datasets import load_dataset
import re

def clean_text(text):
    """Clean text for argument-debugger format"""
    prev_text = ''
    while prev_text != text:
        prev_text = text
        text = text.replace('\n\n', '\n')
    return text

def card_to_argument(card):
    """Convert a debate card to argument-debugger format"""
    # Skip if missing essential fields
    if not card.get('tag') or not card.get('summary') :
        return None
    
    # Get the tag (claim/conclusion)
    tag = clean_text(card['tag'].strip())
    
    # Get the evidence
    evidence = card['summary'].strip()
    evidence = clean_text(evidence)
    
    # Build argument: evidence followed by conclusion
    return f"{evidence}\nConclusion: {tag}"

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert OpenDebateEvidence dataset to argument-debugger format')
    parser.add_argument('-n', '--max-samples', type=int, help='Maximum number of valid arguments to convert')
    parser.add_argument('-o', '--output', default='opendebate.txt', help='Output filename (default: opendebate.txt)')
    
    args = parser.parse_args()
    
    if args.max_samples:
        print(f"Will stop after collecting {args.max_samples} valid arguments")
    
    print("Loading OpenDebateEvidence dataset in streaming mode...")
    dataset = load_dataset('Yusuf5/OpenCaselist', split='train', streaming=True)
    
    converted = 0
    skipped = 0
    
    with open(args.output, 'w') as f:
        for card in dataset:
            argument = card_to_argument(card)
            if argument:
                f.write(argument + '\n\n')
                converted += 1
                if args.max_samples and converted >= args.max_samples:
                    break
            else:
                skipped += 1
            
            # Progress update
            if (converted + skipped) % 1000 == 0:
                print(f"Processed {converted + skipped} cards: {converted} converted, {skipped} skipped")
    
    print(f"\nDone! Converted {converted} arguments to {args.output}")
    print(f"Skipped {skipped} cards")

if __name__ == "__main__":
    main()

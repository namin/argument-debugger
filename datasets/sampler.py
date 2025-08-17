#!/usr/bin/env python3
import sys
import random
import argparse

def sample_entries(input_file, output_file, n):
    """Sample n entries from an argument-debugger format file."""
    
    # Read all entries (separated by double newlines)
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by double newlines to get individual entries
    entries = content.strip().split('\n\n')
    
    # Remove empty entries
    entries = [e.strip() for e in entries if e.strip()]
    
    # Sample n entries (or all if n > total)
    if n >= len(entries):
        sampled = entries
        print(f"Requested {n} entries, but file only has {len(entries)}. Using all entries.")
    else:
        sampled = random.sample(entries, n)
        print(f"Sampled {n} entries from {len(entries)} total entries.")
    
    # Write sampled entries to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in sampled:
            f.write(entry + '\n\n')
    
    print(f"Written {len(sampled)} entries to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Sample entries from an argument-debugger format file')
    parser.add_argument('input_file', help='Input file in argument-debugger format')
    parser.add_argument('output_file', help='Output file for sampled entries')
    parser.add_argument('-n', '--number', type=int, required=True, 
                        help='Number of entries to sample')
    parser.add_argument('--seed', type=int, help='Random seed for reproducible sampling')
    
    args = parser.parse_args()
    
    if args.seed is not None:
        random.seed(args.seed)
    
    sample_entries(args.input_file, args.output_file, args.number)

if __name__ == "__main__":
    main()
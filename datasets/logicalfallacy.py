import csv
import sys

def convert_logical_fallacy_dataset(input_file, output_file):
    """Convert logical fallacy CSV dataset to argument debugger format."""
    
    with open(input_file, 'r', encoding='utf-8') as infile:     
        # Work-around issues with the dataset
        # Use counts to decide on misplaced texts
        value_counts = {}
        reader = csv.DictReader(infile)
        for row in reader:
            for field in ['old_label', 'source_article']:
                text = row.get(field, '').strip()
                if text:
                    value_counts[text] = value_counts.get(text, 0) + 1
        
        # Reset file pointer to beginning for second pass
        infile.seek(0)
        reader = csv.DictReader(infile)
        with open(output_file, 'w', encoding='utf-8') as outfile:
            for row in reader:
                # Get both fields, because sometimes the source_article is left in old_label
                source_text = row.get('source_article', '').strip()
                old_label_text = row.get('old_label', '').strip()
                
                # For each row, pick the field with lower count (more unique)
                if old_label_text and source_text:
                    if value_counts[old_label_text] < value_counts[source_text]:
                        text = old_label_text
                    else:
                        text = source_text
                elif source_text:
                    text = source_text
                elif old_label_text:
                    text = old_label_text
                else:
                    continue
                    
                # Remove surrounding quotes if present
                if text.startswith('"""') and text.endswith('"""'):
                    text = text[3:-3]
                elif text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                elif text.startswith('“') and text.endswith('”'):
                    text = text[1:-1]                    
                elif text.startswith('“'):
                    text = text[1:]

                if text:
                    outfile.write(text + '\n\n')

if __name__ == "__main__":
    input_csv = "logical-fallacy/dataset-fixed/edu_all_fixed.csv"
    output_txt = "logicalfallacy.txt"
    
    if len(sys.argv) > 1:
        output_txt = sys.argv[1]
    
    convert_logical_fallacy_dataset(input_csv, output_txt)
    print(f"Converted {input_csv} to {output_txt}")

# Datasets

## OpenDebateEvidence

The script `opendebate.py` converts the OpenDebateEvidence dataset ([huggingface](https://huggingface.co/datasets/Yusuf5/OpenCaselist)) to summary samples for Argument Debugger, in streaming mode.

### Setup

```bash
pip install dataset
```

### Run

```bash
python opendebate.py --output opendebate_100.txt --max-samples 100
```

## Logical Fallacy

The script `logicalfallancy.py` converts the fixed logical fallacy dataset to samples for Argument Debugger.

### Setup

From this directory:
```bash
git clone https://github.com/tmakesense/logical-fallacy
```

### Run

```bash
python logicalfallacy.py
```

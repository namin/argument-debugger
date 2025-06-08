# Tutorial: Encoding Arguments in Answer Set Programming (ASP)

## Introduction

This tutorial explains how we encode natural language arguments into Answer Set Programming (ASP) for logical analysis. ASP allows us to detect logical flaws that would be difficult to find consistently using other approaches.

## Why ASP for Argument Analysis?

ASP excels at:
- Finding ALL solutions that match a pattern (not just the first one)
- Handling circular dependencies and transitive relationships
- Reasoning with incomplete information
- Providing explicit proofs for why something is a logical flaw

## Division of Responsibilities: LLM vs ASP

Understanding what each component does is crucial:

**LLM's Role: The Court Reporter**
- Faithfully parse natural language into formal structure
- Identify what connections the arguer explicitly stated
- Extract claims and their stated relationships
- **Never invent logical connections or judge validity**

**ASP's Role: The Logic Professor**
- Analyze the formal structure for logical flaws
- Detect missing connections and broken chains
- Find circular dependencies through any number of steps
- **Never interpret natural language or generate text**

This division is powerful because:
1. LLM doesn't need complex logical reasoning prompts
2. ASP doesn't need to understand natural language
3. Each component does what it's best at
4. Errors in one component don't cascade

## Basic Encoding

### 1. Claims and Their Types

Natural language arguments contain claims that serve different roles:

```prolog
% Each claim has an ID and a type
claim("c1", "premise").
claim("c2", "premise").  
claim("c3", "conclusion").
```

This encodes:
- `c1` and `c2` are premises (starting assumptions)
- `c3` is a conclusion (what we're trying to prove)

### 2. Inference Relationships

Arguments connect claims through inferences:

```prolog
% inference(FromClaim, ToClaim)
inference("c1", "c3").
inference("c2", "c3").
```

This means:
- `c1` is used to support `c3`
- `c2` is used to support `c3`
- Together, they form the logical structure

## Detecting Logical Issues

### Missing Links

**Problem**: A conclusion has no logical connection from any premises.

**How it works:**

1. **LLM's Job**: Parse the argument structure
   ```
   "Crime increased. Therefore, we need more police."
   ```
   
   LLM outputs:
   ```json
   {
     "claims": [
       {"id": "c1", "content": "Crime increased", "type": "premise"},
       {"id": "c2", "content": "We need more police", "type": "conclusion"}
     ],
     "inferences": []  // LLM correctly notes NO stated connection
   }
   ```

2. **ASP's Job**: Detect the logical gap
   ```prolog
   % A conclusion without any inference leading to it
   missing_link("premises", C) :- 
       claim(C, "conclusion"),
       not has_inference(C).
   
   % Helper: check if any inference leads to claim C
   has_inference(C) :- inference(_, C).
   ```

**Result**: ASP detects no path from premises to conclusion

### Circular Reasoning

**Problem**: Claims depend on each other in a circle.

**How it works:**

1. **LLM's Job**: Parse ALL inferences, even circular ones
   ```
   "The Bible is true because it's God's word. 
    We know it's God's word because the Bible says so."
   ```
   
   LLM outputs:
   ```json
   {
     "claims": [
       {"id": "c1", "content": "The Bible is true", "type": "premise"},
       {"id": "c2", "content": "The Bible is God's word", "type": "premise"}
     ],
     "inferences": [
       {"from_claims": ["c2"], "to_claim": "c1"},  // True BECAUSE God's word
       {"from_claims": ["c1"], "to_claim": "c2"}   // God's word BECAUSE Bible says
     ]
   }
   ```

2. **ASP's Job**: Trace dependencies to find circles
   ```prolog
   % Direct dependency
   depends_on(X, Y) :- inference(Y, X).
   
   % Transitive dependency (X depends on Z through Y)
   depends_on(X, Z) :- depends_on(X, Y), depends_on(Y, Z).
   
   % Circular: X depends on itself
   circular_reasoning(X) :- depends_on(X, X).
   ```

**Result**: ASP traces: c1 → c2 → c1 (circular!)

### Unsupported Empirical Claims

**Problem**: Claims about the world need evidence.

```prolog
% Mark claims needing evidence
empirical_claim("c1").

% Unsupported if it's a premise with no backing
unsupported_premise(C) :- 
    claim(C, "premise"),
    empirical_claim(C),
    not supported_by_evidence(C).
```

**Example**:
```
Video games cause violence. [No evidence provided]
```

ASP detects: Empirical claim used as unsupported premise

### False Dichotomies

**Problem**: Presenting only two options when more exist.

```prolog
% Mark dichotomous claims
dichotomous_claim("c1").

% False dichotomy if no justification for limited options
false_dichotomy(C) :- 
    dichotomous_claim(C),
    claim(C, _),
    not justified_dichotomy(C).
```

**Example**:
```
Either we cut taxes or the economy fails.
```

ASP detects: Dichotomy without proof these are the only options

## Advanced Patterns

### Inference Chains

ASP can trace through multiple steps:

```prolog
% Can we reach the goal from supported premises?
reachable(C) :- claim(C, "premise"), not empirical_claim(C).
reachable(C) :- inference(From, C), reachable(From).

% Goal unreachable = broken argument
broken_chain(G) :- goal(G), not reachable(G).
```

### Hidden Assumptions

ASP can identify what's missing:

```prolog
% If inference seems invalid, what would make it valid?
needs_assumption(From, To) :- 
    inference(From, To),
    not valid_inference_type(From, To).
```

## Complete Example

Let's trace through a flawed argument:

**Argument**: "Crime rose 10%. Therefore, we need more police."

**ASP Encoding**:
```prolog
% Facts
claim("c1", "premise").
claim("c2", "conclusion").
% Note: No inference between them!

% Rules applied
missing_link("premises", "c2") :- 
    claim("c2", "conclusion"),
    not has_inference("c2").
```

**Result**: ASP detects `missing_link("premises", "c2")`

**Repair Generated**: "Add premise: Increased police presence reduces crime rates"

## What ASP Achieves

1. **Completeness**: Finds ALL logical issues, not just obvious ones
2. **Consistency**: Same argument always produces same analysis
3. **Explainability**: Can trace exactly why something is flagged
4. **Composability**: Simple rules combine to detect complex patterns

## Key Concepts

- **Facts**: Basic statements about the argument structure
- **Rules**: Logical patterns that derive new information
- **Constraints**: Conditions that must not be violated
- **Answer Sets**: Complete, consistent sets of conclusions

## Conclusion

ASP encoding transforms messy natural language arguments into precise logical structures where flaws become computationally detectable. This enables consistent, complete, and explainable argument analysis that would be difficult to achieve with machine learning alone.

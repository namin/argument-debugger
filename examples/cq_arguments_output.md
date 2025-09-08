# Output
Loaded 12 arguments from examples/cq_arguments.txt

## EXAMPLE 1
Argument: Premise P1: Implementing a congestion charge would reduce traffic delays and improve air quality in Midtown.
Evidence E1: Prior implementations showed declines in vehicle miles traveled and NOx.
Because E1, P1.
Warrant W1: Policy should adopt actions that promote stated goals when evidence shows benefits.
Therefore C: The city should implement a congestion charge in Midtown next year.
Goal: The city should implement a congestion charge in Midtown next year.

Parsing argument...

Parsed structure:
- c1: Implementing a congestion charge would reduce traffic delays and improve air quality in Midtown. (intermediate)
- c2: Prior implementations showed declines in vehicle miles traveled and NOx. (premise)
- c3: Policy should adopt actions that promote stated goals when evidence shows benefits. (premise)
- c4: The city should implement a congestion charge in Midtown next year. (conclusion)
- ['c2'] → c1 (inductive)
- ['c1', 'c3'] → c4 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (10):
  - missing_link: No clear logical connection to reach c4
  - missing_cq: Inference(s) into c1 require an answer to CQ 'sample_size'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'representativeness'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'bias'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'defeaters'
  - missing_cq: Inference(s) into c4 require an answer to CQ 'achieves'
  - missing_cq: Inference(s) into c4 require an answer to CQ 'alternatives'
  - missing_cq: Inference(s) into c4 require an answer to CQ 'side_effects'
  - missing_cq: Inference(s) into c4 require an answer to CQ 'conflicts'
  - missing_cq: Inference(s) into c4 require an answer to CQ 'preconditions'

## EXAMPLE 2
Argument: Premise P1: Implementing a congestion charge would reduce traffic delays and improve air quality in Midtown.
Evidence E1: Prior implementations showed declines in vehicle miles traveled and NOx.
Because E1, P1.
Warrant W1: Policy should adopt actions that promote stated goals when evidence shows benefits.
Therefore C: The city should implement a congestion charge in Midtown next year.
Goal: The city should implement a congestion charge in Midtown next year.
CQ: achieves — London/Stockholm data show sustained reductions in congestion and NOx after implementation.
CQ: alternatives — Signal retiming and extra bus lanes were modeled; neither met the same targets alone.
CQ: side_effects — Delivery exemptions and off-peak discounts mitigate cost burdens.
CQ: conflicts — The charge is aligned with the city’s public health and equity goals via low-income discounts.
CQ: preconditions — Enabling legislation and gantry procurement are funded.

Parsing argument...

Parsed structure:
- c1: Implementing a congestion charge would reduce traffic delays and improve air quality in Midtown. (premise)
- c2: Prior implementations showed declines in vehicle miles traveled and NOx. (premise)
- c3: Policy should adopt actions that promote stated goals when evidence shows benefits. (premise)
- c4: The city should implement a congestion charge in Midtown next year. (conclusion)
- c5: The city should implement a congestion charge in Midtown next year. (premise)
- c6: London/Stockholm data show sustained reductions in congestion and NOx after implementation. (premise)
- c7: Signal retiming and extra bus lanes were modeled; neither met the same targets alone. (premise)
- c8: Delivery exemptions and off-peak discounts mitigate cost burdens. (premise)
- c9: The charge is aligned with the city’s public health and equity goals via low-income discounts. (premise)
- c10: Enabling legislation and gantry procurement are funded. (premise)
- ['c2'] → c1 (causal)
- ['c1', 'c3'] → c4 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c2 needs supporting evidence

## EXAMPLE 3
Argument: Premise P1: According to the National Panel on Urban Air Quality, a congestion charge substantially reduces NOx in dense cores.
Evidence E1: The panel's 2024 statement asserts this within urban transport policy.
Because E1, P1.
Therefore C: A congestion charge substantially reduces NOx in dense urban cores.
Goal: A congestion charge substantially reduces NOx in dense urban cores.

Parsing argument...

Parsed structure:
- c1: According to the National Panel on Urban Air Quality, a congestion charge substantially reduces NOx in dense cores. (premise)
- c2: The panel's 2024 statement asserts this within urban transport policy. (premise)
- c3: A congestion charge substantially reduces NOx in dense urban cores. (conclusion)
- ['c2'] → c1 (definitional)
- ['c1'] → c3 (inductive)

Analyzing logical structure...

🔍 ISSUES FOUND (9):
  - missing_link: No clear logical connection to reach c3
  - missing_cq: Inference(s) into c1 require an answer to CQ 'access'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'reliability'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'bias'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'corroboration'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'credibility'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'domain_fit'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'consensus'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'evidence_consistency'

## EXAMPLE 4
Argument: Premise P1: According to the National Panel on Urban Air Quality, a congestion charge substantially reduces NOx in dense cores.
Evidence E1: The panel's 2024 statement asserts this within urban transport policy.
Because E1, P1.
Therefore C: A congestion charge substantially reduces NOx in dense urban cores.
Goal: A congestion charge substantially reduces NOx in dense urban cores.
CQ: credibility — The panel is chartered under a national academy with peer-nominated subject-matter experts.
CQ: domain_fit — The conclusion concerns urban transport emissions, matching the panel’s domain.
CQ: consensus — The statement was a formal consensus with no dissenting votes.
CQ: evidence_consistency — The cited meta-analysis of city implementations aligns with the claim.

Parsing argument...

Parsed structure:
- c1: According to the National Panel on Urban Air Quality, a congestion charge substantially reduces NOx in dense cores. (premise)
- c2: The panel's 2024 statement asserts this within urban transport policy. (premise)
- c3: A congestion charge substantially reduces NOx in dense urban cores. (conclusion)
- ['c2'] → c1 (deductive)
- ['c1'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c1 needs supporting evidence

## EXAMPLE 5
Argument: Premise P1: Banning menthol cigarettes will lead to increased illicit trade.
Evidence E1: Countries that enacted bans saw growth in black-market supply afterward.
Because E1, P1.
Therefore C: If menthols are banned, illicit trade is likely to increase.
Goal: If menthols are banned, illicit trade is likely to increase.

Parsing argument...

Parsed structure:
- c1: Banning menthol cigarettes will lead to increased illicit trade. (premise)
- c2: Countries that enacted bans saw growth in black-market supply afterward. (premise)
- c3: If menthols are banned, illicit trade is likely to increase. (conclusion)
- ['c2'] → c1 (inductive)
- ['c1'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (9):
  - missing_link: No clear logical connection to reach c3
  - missing_cq: Inference(s) into c1 require an answer to CQ 'sample_size'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'representativeness'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'bias'
  - missing_cq: Inference(s) into c1 require an answer to CQ 'defeaters'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'strength'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'interveners'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'alternatives'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'testability'

## EXAMPLE 6
Argument: Premise P1: Banning menthol cigarettes will lead to increased illicit trade.
Evidence E1: Countries that enacted bans saw growth in black-market supply afterward.
Because E1, P1.
Therefore C: If menthols are banned, illicit trade is likely to increase.
Goal: If menthols are banned, illicit trade is likely to increase.
CQ: strength — Multiple post-ban studies report consistent, sizable effects on illicit share.
CQ: interveners — Enforcement intensity and border controls are accounted for in the models.
CQ: alternatives — Demand shifts due to price shocks and flavor substitutes were tested and are insufficient alone.
CQ: testability — The hypothesis is testable via time-series with instruments and cross-jurisdiction comparisons.

Parsing argument...

Parsed structure:
- c1: Banning menthol cigarettes will lead to increased illicit trade. (premise)
- c2: Countries that enacted bans saw growth in black-market supply afterward. (premise)
- c3: If menthols are banned, illicit trade is likely to increase. (conclusion)
- ['c2'] → c1 (causal)
- ['c1'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (3):
  - unsupported_premise: Premise c2 needs supporting evidence
  - circular: Circular reasoning detected involving c1
  - circular: Circular reasoning detected involving c3

## EXAMPLE 7
Argument: Premise P1: Allowing unreviewed AI-generated code into production is like letting new interns push without review.
Premise P2: Interns require human review before merges.
Therefore C: AI-generated changes should require human code review before merges.
Goal: AI-generated changes should require human code review before merges.

Parsing argument...

Parsed structure:
- c1: Allowing unreviewed AI-generated code into production is like letting new interns push without review. (premise)
- c2: Interns require human review before merges. (premise)
- c3: AI-generated changes should require human code review before merges. (conclusion)
- ['c1', 'c2'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (3):
  - missing_link: No clear logical connection to reach c3
  - missing_cq: Inference(s) into c3 require an answer to CQ 'relevance'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'disanalogy'

## EXAMPLE 8
Argument: Premise P1: Allowing unreviewed AI-generated code into production is like letting new interns push without review.
Premise P2: Interns require human review before merges.
Therefore C: AI-generated changes should require human code review before merges.
Goal: AI-generated changes should require human code review before merges.
CQ: relevance — Both cases involve contributors with unknown reliability producing diffs that can break invariants.
CQ: disanalogy — Unlike interns, AI lacks accountability; this strengthens, not weakens, the review requirement.
CQ: typicality — The comparison uses common entry-level interns and mainstream LLM code assistants as typical cases.
CQ: coverage — The comparison covers code safety, auditability, and rollback; other factors are non-essential.

Parsing argument...

Parsed structure:
- c1: Allowing unreviewed AI-generated code into production is like letting new interns push without review. (premise)
- c2: Interns require human review before merges. (premise)
- c3: AI-generated changes should require human code review before merges. (conclusion)
- c4: Both cases involve contributors with unknown reliability producing diffs that can break invariants. (premise)
- c5: Unlike interns, AI lacks accountability; this strengthens, not weakens, the review requirement. (premise)
- c6: The comparison uses common entry-level interns and mainstream LLM code assistants as typical cases. (premise)
- c7: The comparison covers code safety, auditability, and rollback; other factors are non-essential. (premise)
- ['c1', 'c2'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence

## EXAMPLE 9
Argument: Premise P1: Policy P defines "medical misinformation" as content that contradicts public health guidance and creates significant risk of harm.
Premise P2: The post asserts claims that contradict the current public guidance and encourage harmful actions.
Therefore C: The post qualifies as medical misinformation under Policy P.
Goal: The post qualifies as medical misinformation under Policy P.

Parsing argument...

Parsed structure:
- c1: Policy P defines "medical misinformation" as content that contradicts public health guidance and creates significant risk of harm. (premise)
- c2: The post asserts claims that contradict the current public guidance and encourage harmful actions. (premise)
- c3: The post qualifies as medical misinformation under Policy P. (conclusion)
- ['c1', 'c2'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (4):
  - missing_link: No clear logical connection to reach c3
  - missing_cq: Inference(s) into c3 require an answer to CQ 'matching'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'exceptions'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'conflicts'

## EXAMPLE 10
Argument: Premise P1: Policy P defines "medical misinformation" as content that contradicts public health guidance and creates significant risk of harm.
Premise P2: The post asserts claims that contradict the current public guidance and encourage harmful actions.
Therefore C: The post qualifies as medical misinformation under Policy P.
Goal: The post qualifies as medical misinformation under Policy P.
CQ: adequacy — Policy P's definition is the current, published standard for the platform.
CQ: fit — The cited sentences directly contradict guidance and advise unsafe interventions.
CQ: borderline — The claims are categorical, not edge cases or satire.

Parsing argument...

Parsed structure:
- c1: Policy P defines "medical misinformation" as content that contradicts public health guidance and creates significant risk of harm. (premise)
- c2: The post asserts claims that contradict the current public guidance and encourage harmful actions. (premise)
- c3: The post qualifies as medical misinformation under Policy P. (conclusion)
- ['c1', 'c2'] → c3 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (4):
  - missing_link: No clear logical connection to reach c3
  - missing_cq: Inference(s) into c3 require an answer to CQ 'matching'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'exceptions'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'conflicts'

## EXAMPLE 11
Argument: Premise P1: A sudden >50% increase in 5xx responses is a sign of a backend outage.
Premise P2: We observed a 60% increase in 5xx responses starting at 14:05.
Therefore C: There is likely an ongoing backend outage.
Goal: There is likely an ongoing backend outage.

Parsing argument...

Parsed structure:
- c1: A sudden >50% increase in 5xx responses is a sign of a backend outage. (premise)
- c2: We observed a 60% increase in 5xx responses starting at 14:05. (premise)
- c3: There is likely an ongoing backend outage. (conclusion)
- ['c1', 'c2'] → c3 (inductive)

Analyzing logical structure...

🔍 ISSUES FOUND (5):
  - missing_link: No clear logical connection to reach c3
  - missing_cq: Inference(s) into c3 require an answer to CQ 'reliability'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'alt_explanations'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'base_rate'
  - missing_cq: Inference(s) into c3 require an answer to CQ 'measurement'

## EXAMPLE 12
Argument: Premise P1: A sudden >50% increase in 5xx responses is a sign of a backend outage.
Premise P2: We observed a 60% increase in 5xx responses starting at 14:05.
Therefore C: There is likely an ongoing backend outage.
Goal: There is likely an ongoing backend outage.
CQ: reliability — Historically, spikes >50% in this service correlate with true outages >90% of the time.
CQ: alt_explanations — No deploys, load tests, or monitor regressions occurred in the last 24h.
CQ: base_rate — Outages occur on <1% of days; combining base rates with the sign gives high posterior odds.
CQ: measurement — 5xx spikes were confirmed in two independent logs and synthetic probes.

Parsing argument...

Parsed structure:
- c1: A sudden >50% increase in 5xx responses is a sign of a backend outage. (premise)
- c2: We observed a 60% increase in 5xx responses starting at 14:05. (premise)
- c3: There is likely an ongoing backend outage. (conclusion)
- c4: Historically, spikes >50% in this service correlate with true outages >90% of the time. (premise)
- c5: No deploys, load tests, or monitor regressions occurred in the last 24h. (premise)
- c6: Outages occur on <1% of days; combining base rates with the sign gives high posterior odds. (premise)
- c7: 5xx spikes were confirmed in two independent logs and synthetic probes. (premise)
- ['c1', 'c2', 'c4', 'c5', 'c6', 'c7'] → c3 (inductive)

Analyzing logical structure...

🔍 ISSUES FOUND (5):
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence
  - unsupported_premise: Premise c5 needs supporting evidence
  - unsupported_premise: Premise c6 needs supporting evidence
  - unsupported_premise: Premise c7 needs supporting evidence

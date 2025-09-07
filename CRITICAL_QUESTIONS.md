# Critical Questions in the Argument Debugger
*A rationale, brief history, and implementation notes*

**Last updated:** 2025‑09‑07

---

## 1) What are “Critical Questions” (CQs)?

**Critical Questions** are canonical prompts attached to common **argumentation schemes**—stereotypical patterns of reasoning such as *Argument from Expert Opinion*, *Cause→Effect*, *Practical Reasoning (means–end)*, *Apply Rule to Case*, and so on. For each scheme, scholars have cataloged the characteristic *vulnerabilities* the reasoning is prone to. The associated CQs are the minimal set of clarifications or tests that, if addressed, typically resolve those vulnerabilities. In short:

> **Schemes** = blueprints of how a type of argument works.  
> **Critical Questions** = targeted diagnostics that probe whether this blueprint is satisfied in the current case.

CQs are not pedantic trivia; they are *actionable checks* that improve argumentative quality. They force authors to add the missing warrant, quantify uncertainty, show feasibility, compare alternatives, disclose conflicts, etc.

---

## 2) Why not “just use an LLM”?

LLMs are strong at paraphrase and local coherence, but unconstrained generation tends to:

1. **Over‑polish** weak arguments without revealing gaps,
2. **Hallucinate bridging warrants** (spurious inference steps),
3. **Ignore decision structure** (e.g., alternatives, side‑effects, feasibility),
4. **Lose global consistency** across edits.

CQs supply **external structure** that *constrains* the LLM to fill the *right* gaps. They also give you an **auditable checklist**: you can show reviewers *which* questions were asked and *which* ones remain unanswered. This complements, rather than competes with, LLMs.

---

## 3) Where CQs come from (very short history)

- **Aristotle’s Topics** and later **Topoi** catalog practical reasoning “places” to discover arguments; many modern schemes trace to these loci.
- **Toulmin (1958)** reframed arguments as *claim–data–warrant–backing–qualifier–rebuttal*. CQs operationalize “warrant/backing/rebuttal” for *specific* patterns.
- **Perelman & Olbrechts‑Tyteca (1958)** stressed audience adherence and argument techniques; again, many are scheme‑like.
- Modern **informal logic** (1970s–) emphasized defeasible reasoning—good‑enough arguments that can be *challenged*.  
- **Walton, Reed & Macagno (2008)** systematized **argumentation schemes** with **standard CQs** for dozens of schemes (expert opinion, analogy, practical reasoning, sign, cause, etc.).
- In **computational argumentation**, **Dung (1995)** introduced abstract frameworks (arguments and attacks) with formal semantics. Later work (e.g., **ASPIC+**, **Value‑based Argumentation**) elaborated structured attacks and preferences. These threads provide **formal backbones** where CQs act like **defeaters** or **preconditions** that can enable/disable inferences.
- In **Answer Set Programming (ASP)** (e.g., `clingo`), such constraints can be encoded declaratively and solved fast at scale.

> The Argument Debugger borrows the **Waltonian schemes + CQs** as the human‑facing layer and uses **ASP** to track support, conflicts, missing links, and CQ “gates”.

---

## 4) How CQs improve the pipeline

The Argument Debugger has three major LLM‑assisted steps and one symbolic step:

1. **Parse** the raw text into claims, inferences, and types (premise/intermediate/conclusion).  
2. **Assign a scheme** to each inference and select the **top‑k** most relevant CQs.  
3. **Harvest answers** present in the text (e.g., explicit “CQ: alternatives — …”) and record which CQs are answered.  
4. **Analyze in ASP**: build the support graph; flag missing links; and—if desired—**disable** inferences whose conclusions require CQs that remain unanswered.

Two modes balance guidance vs. enforcement:

- **Advice mode** – Missing CQs produce human‑readable advice but do **not** switch off the inference. Best for drafting.  
- **Enforce mode** – Unanswered CQs **disable** those inferences in the ASP graph (via a `disabled_inference` predicate), which can expose downstream *missing‑link* failures. Best for QA/compliance.

This creates a **tight loop**: the system is specific about *what to add* (CQs), the author adds a line or two to satisfy them, and the graph immediately improves.

---

## 5) Design principles for the CQ set

- **Small and targeted** – Each scheme has ~3–6 CQs that give the most leverage.  
- **Actionable** – Each CQ includes *how to answer* and *evidence types*, not just a label.  
- **Top‑k** – To avoid flooding, we select only the most relevant CQs per conclusion.  
- **Neutral phrasing** – CQs are checks, not objections; they work for and against any stance.  
- **Auditability** – The report distinguishes between *required* and *answered* CQs.

---

## 6) UX: one‑liners, extended lines, and “Action”

We provide two concise renderings plus a targeted “Action” line:

- **One‑liner**: `Mechanism — Show how A leads to G; cite outcome evidence.`  
- **Extended**: `Mechanism — What process links cause to effect? — Explain the pathway… — Why it matters: …`  
- **Action (first step)**: `Action: Summarize the pathway A→M→G and cite one evaluation.`

This triage gives busy authors *just enough* guidance, and reviewers can drill down into the richer metadata (e.g., pitfalls, answer templates) when needed.

---

## 7) Implementation sketch

- **LLM** produces structured `ArgumentStructure` (claims, inferences, types, etc.).  
- **Scheme assignment** uses the LLM but is *constrained* to a small set of schemes **allowed** per `rule_type` (deductive/inductive/causal/definitional).  
- The assigner aggregates CQs **per conclusion** and caps to **top‑k**.  
- **ASP** receives: claims, inferences, equivalences, goal, empirical flags, plus optional `requires_cq`/`answered_cq`.  
- In **enforce** mode, a rule disables inferences into a conclusion that has *any* required CQ unanswered; otherwise we simply display advisory messages.

---

## 8) Relationship to broader literature

- **Argumentation schemes** mirror classical **topoi** and legal **canons/tests** (e.g., “apply rule to case,” “weigh alternatives,” “check exceptions”).  
- **CQs = defeaters** conceptually: they describe ways an inference can fail unless countered.  
- **ASP** is a good fit for rapidly changing support graphs (add a CQ answer → inference re‑enabled).  
- **LLMs** excel at *classification* and *surface repair*; **ASP** ensures **global consistency** and **explainability**.

---

## 9) When to use “enforce”

- **Safety‑critical** or **policy** arguments where compliance with governance/QA is non‑negotiable.  
- **Procurement** and **grant** decisions where comparative reasoning (alternatives, side‑effects, feasibility) must be explicit.  
- **Evidence‑based** contexts that require calibration, uncertainty, or replication checks (e.g., causal claims).

In other settings (brainstorming, early drafts), **advice** mode keeps momentum while still nudging toward better arguments.

---

## 10) References & suggested reading

- **Walton, Douglas; Reed, Chris; Macagno, Fabrizio (2008).** *Argumentation Schemes.* Cambridge Univ. Press.  
- **Toulmin, Stephen (1958).** *The Uses of Argument.* Cambridge Univ. Press.  
- **Perelman, Chaim; Olbrechts‑Tyteca, Lucie (1958).** *Traité de l’argumentation: La nouvelle rhétorique.* Presses Universitaires de Bruxelles.  
- **Dung, Phan Minh (1995).** “On the Acceptability of Arguments and its Fundamental Role in Nonmonotonic Reasoning.” *Artificial Intelligence*, 77(2):321–357.  
- **Prakken, Henry; Sartor, Giovanni (1996–2010).** Works on legal argumentation and defeasible reasoning (e.g., **ASPIC+** with Gordon & Walton).  
- **Bench‑Capon, Trevor (2003).** “Persuasion in Practical Argument Using Value‑based Argumentation Frameworks.” *Journal of Logic and Computation* 13(3).  
- **Besnard, Philippe; Hunter, Anthony (2008).** *Elements of Argumentation.* MIT Press.  
- **Gebser, Martin; Kaufmann, Benjamin; Schaub, Torsten (2012).** *Answer Set Solving in Practice.* Morgan & Claypool.  
- **Gordon, Thomas F.; Prakken, Henry; Walton, Douglas (2007).** “The Carneades Model of Argument and Burden of Proof.” *Artificial Intelligence* 171(10–15).

---

## 11) Summary

Critical Questions give your debugger a **discipline‑agnostic, auditable, and teachable** way to improve arguments. They turn vague advice (“be more rigorous”) into concrete edits (“quantify effect size,” “show alternatives,” “disclose COIs”). With LLMs doing classification and micro‑edits, and ASP enforcing global coherence, you get the best of both worlds: **fast assistance** and **formal assurance**.

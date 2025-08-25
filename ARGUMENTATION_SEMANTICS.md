# Argumentation Semantics

Argumentation semantics tell us which arguments “survive” in a network where arguments can attack each other.
With Dung’s abstract argumentation frameworks (AFs):
$\text{AF} = (A, →)$ where $A$ is a set of arguments and $→$ is the attack relation.

Key notions on a set of arguments:
- **Conflict‑free**: no two arguments in the set attack each other.
- **Defends**: a set $S$ defends $a$ if for every attacker $b → a$, some $c ∈ S$ attacks $b$.
- **Admissible**: conflict‑free and defends all its members.
- **Complete**: admissible and contains every argument it defends.
- **Grounded**: the least complete extension (skeptical baseline).
- **Preferred**: maximal (by $⊆$) admissible extensions (credulous choices).
- **Stable**: conflict‑free and attacks every argument outside the set (may not exist).

Formal definitions:
- An AF is $⟨A,R⟩$ with arguments $A$ and attacks $R⊆A×A$.
- For $x∈A$, let $\text{Att}(x)={b∈A∣(b,x)∈R}$ (the attackers of $x$).
- A set $S⊆A$ defends $𝑎$ iff for every $b∈\text{Att}(a)$ there is $c∈S$ with $(c,b)∈R$.
- The characteristic function: $F(S)={a∈A∣S \text{defends} a}$.
- ...

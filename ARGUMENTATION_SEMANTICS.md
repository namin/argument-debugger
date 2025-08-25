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
- For $x∈A$, let $\text{Att}(x)=\\{b∈A∣(b,x)∈R\\}$ (the attackers of $x$).
- A set $S⊆A$ defends $𝑎$ iff for every $b∈\text{Att}(a)$ there is $c∈S$ with $(c,b)∈R$.
- The characteristic function: $F(S)=\\{a∈A∣S \text{ defends } a\\}$.
- The grounded extension is the least fixed point of $F$, obtained by iterating from $∅$: $𝑆_0 = ∅$, $S_{i+1} = F(S_i)$ until $S_{i+1} = S_i$.

Intuition box: starting from nothing, we first accept only arguments that nobody attacks; then, with those in hand, we also accept anything they (as a set) defend, and so on, until nothing changes.

Worked-out Toy AF:
- $A=\\{A,B,C\\}$
- $R=\\{(A,B),(B,C)\\}$ (i.e., $A→B$ and $B→C$)

<details>
  <summary>Properties of Toy AF</summary>

- $F(∅) = {A}$.<br/>
- $F(\\{A\\}) = \\{A, C\\}$.<br/>
- $F(\\{A,C\\}) = \\{A,C\\}$.<br/>
- **Conflict‑free**: $∅,\\{A\\},\\{B\\},\\{C\\},\\{A,C\\}$.<br/>
- **Admissible**: $∅,\\{A\\},\\{A,C\\}$.<br/>
- **Complete**: $\\{A,C\\}$.<br/>
- **Grounded**: $\\{A,C\\}$.<br/>
- **Preferred**: $\\{A,C\\}$.<br/>
- **Stable**: $A∖S=\\{B\\}$, and $A∈S$ attacks $B$, so $S=\\{A,C\\}$ is stable.<br/>
</details>

# Output
Loaded 4 arguments from examples/philosophy2.txt

## EXAMPLE 1
Argument: No belief is rationally justified.
But if that's true, then the belief 'no belief is rationally justified' is itself not justified.
So if skepticism is true, we shouldn't believe skepticism.
Therefore, skepticism defeats itself.

Parsing argument...

Parsed structure:
- c1: No belief is rationally justified. (premise)
- c2: If 'no belief is rationally justified' is true, then the belief 'no belief is rationally justified' is itself not justified. (intermediate)
- c3: If skepticism is true, we shouldn't believe skepticism. (intermediate)
- c4: Skepticism defeats itself. (conclusion)
- ['c1'] → c2 (deductive)
- ['c2'] → c3 (deductive)
- ['c3'] → c4 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 2
Argument: Someone with $1 million is rich.
If someone with $X is rich, then someone with $X - 1 is also rich.
(After all, one dollar can't make the difference between rich and not-rich!)
Therefore, someone with $999,999 is rich.
By repeated application: someone with $1 is rich.
But that's absurd - so our concept of 'rich' is incoherent.

Parsing argument...

Parsed structure:
- c1: Someone with $1 million is rich. (premise)
- c2: If someone with $X is rich, then someone with $X - 1 is also rich. (premise)
- c3: one dollar can't make the difference between rich and not-rich! (premise)
- c4: Therefore, someone with $999,999 is rich. (intermediate)
- c5: someone with $1 is rich. (intermediate)
- c6: that's absurd (premise)
- c7: our concept of 'rich' is incoherent. (conclusion)
- ['c1', 'c2', 'c3'] → c4 (deductive)
- ['c1', 'c2'] → c5 (deductive)
- ['c5', 'c6'] → c7 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - slippery_slope: Slippery slope in c5: argues that one action leads to extreme consequences without justification

## EXAMPLE 3
Argument: It's possible that a maximally great being exists.
A maximally great being would have necessary existence (exists in all possible worlds).
If it's possible that a necessary being exists, then that being exists in at least one possible world.
But if a necessary being exists in any possible world, it exists in all possible worlds.
Therefore, a maximally great being exists in the actual world.

Parsing argument...

Parsed structure:
- c1: It's possible that a maximally great being exists. (premise)
- c2: A maximally great being would have necessary existence (exists in all possible worlds). (premise)
- c3: If it's possible that a necessary being exists, then that being exists in at least one possible world. (premise)
- c4: But if a necessary being exists in any possible world, it exists in all possible worlds. (premise)
- c5: Therefore, a maximally great being exists in the actual world. (conclusion)
- ['c1', 'c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 4
Argument: Some people claim 'there is no objective truth.'
But this claim itself purports to be objectively true.
For any meaningful debate to occur, participants must assume that some statements are objectively true or false.
Even to argue against objective truth requires assuming objective standards of logic and evidence.
Therefore, the very possibility of rational discourse presupposes objective truth.

Parsing argument...

Parsed structure:
- c1: Some people claim 'there is no objective truth.' (premise)
- c2: This claim itself purports to be objectively true. (premise)
- c3: For any meaningful debate to occur, participants must assume that some statements are objectively true or false. (premise)
- c4: Even to argue against objective truth requires assuming objective standards of logic and evidence. (premise)
- c5: The very possibility of rational discourse presupposes objective truth. (conclusion)
- ['c1', 'c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c1 needs supporting evidence

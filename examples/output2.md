# Output
Loaded 6 arguments from examples2.txt

## EXAMPLE 1
Argument: John Smith wrote a book that provided a lot of evidence for the earth flat. John Smith sold a billion copies of his book. The information and evidence convinced all one billion people. Therefore, the earth is flat.
Parsing argument...

Parsed structure:
- c1: John Smith wrote a book that provided a lot of evidence for the earth flat. (premise)
- c2: John Smith sold a billion copies of his book. (premise)
- c3: The information and evidence convinced all one billion people. (premise)
- c4: The earth is flat. (conclusion)
- ['c3'] → c4 (inductive)

Analyzing logical structure...

Found 4 issues.

🔍 ISSUES FOUND:
  - missing_link: No clear logical connection to reach c4
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence

## EXAMPLE 2
Argument: Even though there have been no other instances of resurrection recorded throughout history, Jesus's resurrection was real because it is well-documented that he performed miracles. Only God can perform miracles, so Jesus was God. And God can do all things, including resurrecting himself.
Parsing argument...

Parsed structure:
- c1: There have been no other instances of resurrection recorded throughout history. (premise)
- c2: Jesus's resurrection was real. (conclusion)
- c3: It is well-documented that Jesus performed miracles. (premise)
- c4: Only God can perform miracles. (premise)
- c5: Jesus was God. (intermediate)
- c6: God can do all things. (premise)
- c7: God can resurrect himself. (intermediate)
- ['c3', 'c4'] → c5 (deductive)
- ['c6'] → c7 (deductive)
- ['c5', 'c7'] → c2 (deductive)

Analyzing logical structure...

Found 2 issues.

🔍 ISSUES FOUND:
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence

## EXAMPLE 3
Argument: Marriage should be restricted to one man and one woman. Gay people should not be allowed to get married because if you allow two men or two women to get married, then why wouldn't you allow a man to marry a goat or a chair or 15 chickens?
Parsing argument...

Parsed structure:
- c1: Marriage should be restricted to one man and one woman. (conclusion)
- c2: Gay people should not be allowed to get married (intermediate)
- c3: if you allow two men or two women to get married, then why wouldn't you allow a man to marry a goat or a chair or 15 chickens? (premise)
- ['c3'] → c2 (deductive)
- ['c2'] → c1 (deductive)

Analyzing logical structure...

Found 1 issues.

🔍 ISSUES FOUND:
  - slippery_slope: Slippery slope: argues that one action leads to extreme consequences without justification

## EXAMPLE 4
Argument: I cant imagine how something can come from nothing, therefore a creator God must have created the universe.
Parsing argument...

Parsed structure:
- c1: I can't imagine how something can come from nothing (premise)
- c2: A creator God must have created the universe (conclusion)
- ['c1'] → c2 (inductive)

Analyzing logical structure...

Found 2 issues.

🔍 ISSUES FOUND:
  - missing_link: No clear logical connection to reach c2
  - unsupported_premise: Premise c1 needs supporting evidence

## EXAMPLE 5
Argument: Sam has met 100 redheads in his life. 50 of those redheads were missing thumbs. Therefore all readheads are missing thumbs.
Parsing argument...

Parsed structure:
- c1: Sam has met 100 redheads in his life. (premise)
- c2: 50 of those redheads were missing thumbs. (premise)
- c3: All redheads are missing thumbs. (conclusion)
- ['c1', 'c2'] → c3 (inductive)

Analyzing logical structure...

Found 3 issues.

🔍 ISSUES FOUND:
  - missing_link: No clear logical connection to reach c3
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence

## EXAMPLE 6
Argument: Jake has always arrived to work by bus. However, today, the bus service was suspended. It is therefore impossible for Jake to get to work.
Parsing argument...

Parsed structure:
- c1: Jake has always arrived to work by bus. (premise)
- c2: The bus service was suspended today. (premise)
- c3: It is impossible for Jake to get to work. (conclusion)
- ['c1', 'c2'] → c3 (deductive)

Analyzing logical structure...

Found 3 issues.

🔍 ISSUES FOUND:
  - missing_link: No clear logical connection to reach c3
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence

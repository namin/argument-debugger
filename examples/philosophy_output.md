# Output
Loaded 30 arguments from examples/philosophy.txt

## EXAMPLE 1
Argument: I think, therefore I am. I cannot doubt that I am thinking, for doubting is itself a form of thinking. Even if an evil demon deceives me about everything else, he cannot deceive me about my existence while I am thinking. Therefore, my existence as a thinking being is the most certain knowledge possible.

Parsing argument...

Parsed structure:
- c1: I think, therefore I am. (conclusion)
- c2: I cannot doubt that I am thinking, for doubting is itself a form of thinking. (premise)
- c3: Even if an evil demon deceives me about everything else, he cannot deceive me about my existence while I am thinking. (premise)
- c4: my existence as a thinking being is the most certain knowledge possible. (conclusion)
- ['c2', 'c3'] → c1 (deductive)
- ['c1'] → c4 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 2
Argument: The unexamined life is not worth living. Those who never reflect on their actions live like animals, driven by instinct rather than reason. Reason is what distinguishes humans from beasts. A life without philosophy is therefore not truly human. Since a non-human life has no value for a human being, the unexamined life is not worth living.

Parsing argument...

Parsed structure:
- c1: The unexamined life is not worth living. (conclusion)
- c2: Those who never reflect on their actions live like animals, driven by instinct rather than reason. (premise)
- c3: Reason is what distinguishes humans from beasts. (premise)
- c4: A life without philosophy is therefore not truly human. (intermediate)
- c5: A non-human life has no value for a human being. (premise)
- ['c2', 'c3'] → c4 (deductive)
- ['c4', 'c5'] → c1 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 3
Argument: If God exists, then evil should not exist. God is by definition omnipotent, omniscient, and omnibenevolent. An omnipotent being can prevent all evil. An omniscient being knows about all evil. An omnibenevolent being wants to prevent all evil. Yet evil clearly exists in the world. Therefore, God does not exist.

Parsing argument...

Parsed structure:
- c1: If God exists, then evil should not exist. (premise)
- c2: God is by definition omnipotent, omniscient, and omnibenevolent. (premise)
- c3: An omnipotent being can prevent all evil. (premise)
- c4: An omniscient being knows about all evil. (premise)
- c5: An omnibenevolent being wants to prevent all evil. (premise)
- c6: Evil clearly exists in the world. (premise)
- c7: God does not exist. (conclusion)
- ['c2', 'c3', 'c4', 'c5'] → c1 (deductive)
- ['c1', 'c6'] → c7 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c6 needs supporting evidence

## EXAMPLE 4
Argument: We cannot have knowledge of the external world. All our knowledge comes through our senses. Our senses sometimes deceive us, as in dreams or hallucinations. If our senses can deceive us sometimes, they might be deceiving us always. We cannot prove we're not being deceived right now. Therefore, we cannot know anything about the external world with certainty.

Parsing argument...

Parsed structure:
- c1: We cannot have knowledge of the external world. (intermediate)
- c2: All our knowledge comes through our senses. (premise)
- c3: Our senses sometimes deceive us, as in dreams or hallucinations. (premise)
- c4: If our senses can deceive us sometimes, they might be deceiving us always. (intermediate)
- c5: We cannot prove we're not being deceived right now. (premise)
- c6: We cannot know anything about the external world with certainty. (conclusion)
- ['c3'] → c4 (inductive)
- ['c2', 'c4', 'c5'] → c1 (deductive)
- ['c1'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c3 needs supporting evidence
  - slippery_slope: Slippery slope in c4: argues that one action leads to extreme consequences without justification

## EXAMPLE 5
Argument: Every event must have a cause. If every event has a cause, then the first event must have had a cause. But what caused the cause of the first event? This leads to an infinite regress. An infinite regress is impossible. Therefore, there must be an uncaused first cause, which we call God.

Parsing argument...

Parsed structure:
- c1: Every event must have a cause. (premise)
- c2: If every event has a cause, then the first event must have had a cause. (intermediate)
- c3: The first event must have had a cause. (intermediate)
- c4: What caused the cause of the first event? (intermediate)
- c5: This leads to an infinite regress. (intermediate)
- c6: An infinite regress is impossible. (premise)
- c7: Therefore, there must be an uncaused first cause, which we call God. (conclusion)
- ['c1', 'c2'] → c3 (deductive)
- ['c3', 'c4'] → c5 (deductive)
- ['c5', 'c6'] → c7 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 6
Argument: We have no free will. Every action is either determined by prior causes or random. If our actions are determined, we don't have free will. If our actions are random, we don't have control over them, so we don't have free will. Our actions must be either determined or random. Therefore, we have no free will.

Parsing argument...

Parsed structure:
- c1: We have no free will. (conclusion)
- c2: Every action is either determined by prior causes or random. (premise)
- c3: If our actions are determined, we don't have free will. (premise)
- c4: If our actions are random, we don't have control over them, so we don't have free will. (premise)
- c5: Our actions must be either determined or random. (premise)
- ['c2', 'c3', 'c4', 'c5'] → c1 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 7
Argument: The mind cannot be identical to the brain. I can doubt that my brain exists - perhaps I'm a brain in a vat being stimulated to think I have a body. But I cannot doubt that my mind exists, as doubting requires a mind. If I can doubt one but not the other, they cannot be identical. Therefore, the mind and brain are distinct.

Parsing argument...

Parsed structure:
- c1: The mind cannot be identical to the brain. (intermediate)
- c2: I can doubt that my brain exists - perhaps I'm a brain in a vat being stimulated to think I have a body. (premise)
- c3: I cannot doubt that my mind exists, as doubting requires a mind. (premise)
- c4: If I can doubt one but not the other, they cannot be identical. (premise)
- c5: The mind and brain are distinct. (conclusion)
- ['c2', 'c3', 'c4'] → c1 (deductive)
- ['c1'] → c5 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 8
Argument: Morality is relative to culture. Different cultures have different moral codes. There is no objective way to judge between different moral codes. If there were objective moral truths, all cultures would agree on them. Since cultures disagree about morality, there are no objective moral truths. Therefore, what is right is whatever your culture says is right.

Parsing argument...

Parsed structure:
- c1: Morality is relative to culture. (intermediate)
- c2: Different cultures have different moral codes. (premise)
- c3: There is no objective way to judge between different moral codes. (premise)
- c4: If there were objective moral truths, all cultures would agree on them. (premise)
- c5: Cultures disagree about morality. (premise)
- c6: There are no objective moral truths. (intermediate)
- c7: What is right is whatever your culture says is right. (conclusion)
- ['c2', 'c3'] → c1 (deductive)
- ['c4', 'c5'] → c6 (deductive)
- ['c1', 'c6'] → c7 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c5 needs supporting evidence

## EXAMPLE 9
Argument: Life has no inherent meaning. The universe existed for billions of years before humans appeared. The universe will continue for billions of years after humans disappear. On a cosmic scale, human existence is insignificant. Nothing we do will matter in a billion years. Therefore, life has no objective meaning or purpose.

Parsing argument...

Parsed structure:
- c1: Life has no inherent meaning. (premise)
- c2: The universe existed for billions of years before humans appeared. (premise)
- c3: The universe will continue for billions of years after humans disappear. (premise)
- c4: On a cosmic scale, human existence is insignificant. (intermediate)
- c5: Nothing we do will matter in a billion years. (intermediate)
- c6: Life has no objective meaning or purpose. (conclusion)
- ['c2', 'c3'] → c4 (inductive)
- ['c4'] → c5 (inductive)
- ['c1', 'c5'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence

## EXAMPLE 10
Argument: We should maximize happiness for the greatest number. Actions are right when they produce happiness and wrong when they produce suffering. The best action is the one that produces the most happiness overall. This is an objective measure that doesn't depend on personal feelings or cultural norms. Therefore, morality consists in maximizing total happiness.

Parsing argument...

Parsed structure:
- c1: We should maximize happiness for the greatest number. (premise)
- c2: Actions are right when they produce happiness and wrong when they produce suffering. (premise)
- c3: The best action is the one that produces the most happiness overall. (intermediate)
- c4: This is an objective measure that doesn't depend on personal feelings or cultural norms. (premise)
- c5: Morality consists in maximizing total happiness. (conclusion)
- ['c2'] → c3 (deductive)
- ['c1', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 11
Argument: Knowledge is justified true belief. To know something, you must believe it. The belief must be true - you cannot know something false. The belief must be justified - lucky guesses don't count as knowledge. These three conditions are necessary and sufficient for knowledge. Therefore, whenever you have a justified true belief, you have knowledge.

Parsing argument...

Parsed structure:
- c1: Knowledge is justified true belief. (premise)
- c2: To know something, you must believe it. (premise)
- c3: The belief must be true - you cannot know something false. (premise)
- c4: The belief must be justified - lucky guesses don't count as knowledge. (premise)
- c5: These three conditions are necessary and sufficient for knowledge. (premise)
- c6: Whenever you have a justified true belief, you have knowledge. (conclusion)
- ['c1', 'c2', 'c3', 'c4', 'c5'] → c6 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 12
Argument: Personal identity persists through change. The ship of Theseus has all its parts gradually replaced. If it remains the same ship despite total replacement, then identity doesn't depend on physical parts. You remain the same person despite replacing all your cells every seven years. Therefore, personal identity must consist in psychological continuity, not physical continuity.

Parsing argument...

Parsed structure:
- c1: Personal identity persists through change. (premise)
- c2: The ship of Theseus has all its parts gradually replaced. (premise)
- c3: If it remains the same ship despite total replacement, then identity doesn't depend on physical parts. (premise)
- c4: You remain the same person despite replacing all your cells every seven years. (premise)
- c5: Personal identity must consist in psychological continuity, not physical continuity. (conclusion)
- ['c1', 'c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence

## EXAMPLE 13
Argument: Nothing exists except ideas in minds. We only ever perceive our own ideas or sensations. We never perceive material objects directly, only our ideas of them. There is no reason to suppose material objects exist beyond our ideas. A simpler explanation is that only minds and ideas exist. Therefore, material objects are just collections of ideas.

Parsing argument...

Parsed structure:
- c1: Nothing exists except ideas in minds. (premise)
- c2: We only ever perceive our own ideas or sensations. (premise)
- c3: We never perceive material objects directly, only our ideas of them. (premise)
- c4: There is no reason to suppose material objects exist beyond our ideas. (premise)
- c5: A simpler explanation is that only minds and ideas exist. (premise)
- c6: Material objects are just collections of ideas. (conclusion)
- ['c2', 'c3', 'c4', 'c5'] → c6 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 14
Argument: The self is an illusion. When you introspect, you find thoughts, feelings, and sensations. You never find a separate self that has these experiences. The self is supposed to be what remains constant through all experiences. But there is only the stream of experiences, no constant observer. Therefore, the self doesn't exist.

Parsing argument...

Parsed structure:
- c1: The self is an illusion. (premise)
- c2: When you introspect, you find thoughts, feelings, and sensations. (premise)
- c3: You never find a separate self that has these experiences. (premise)
- c4: The self is supposed to be what remains constant through all experiences. (premise)
- c5: There is only the stream of experiences, no constant observer. (premise)
- c6: The self doesn't exist. (conclusion)
- ['c2', 'c3'] → c1 (inductive)
- ['c4', 'c5'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c5 needs supporting evidence

## EXAMPLE 15
Argument: Language determines thought. The Inuit have many words for snow, allowing them to perceive distinctions others cannot. We cannot think about concepts for which we lack words. Different languages carve up reality in different ways. Therefore, speakers of different languages literally experience different worlds.

Parsing argument...

Parsed structure:
- c1: Language determines thought. (premise)
- c2: The Inuit have many words for snow, allowing them to perceive distinctions others cannot. (premise)
- c3: We cannot think about concepts for which we lack words. (premise)
- c4: Different languages carve up reality in different ways. (premise)
- c5: Speakers of different languages literally experience different worlds. (conclusion)
- ['c1', 'c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (4):
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence

## EXAMPLE 16
Argument: You should act only according to maxims you could will to be universal laws. If everyone lied, communication would break down and lying would become impossible. Lying therefore involves a contradiction when universalized. Actions that lead to contradictions when universalized are immoral. Therefore, lying is always wrong, regardless of consequences.

Parsing argument...

Parsed structure:
- c1: You should act only according to maxims you could will to be universal laws. (premise)
- c2: If everyone lied, communication would break down and lying would become impossible. (premise)
- c3: Lying therefore involves a contradiction when universalized. (intermediate)
- c4: Actions that lead to contradictions when universalized are immoral. (premise)
- c5: Lying is always wrong, regardless of consequences. (conclusion)
- ['c2'] → c3 (deductive)
- ['c1', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c2 needs supporting evidence

## EXAMPLE 17
Argument: Beauty is in the eye of the beholder. People disagree about what is beautiful. There is no way to prove one aesthetic judgment correct and another wrong. If beauty were objective, we would all agree about it. Since aesthetic judgments vary across cultures and individuals, beauty must be subjective.

Parsing argument...

Parsed structure:
- c1: Beauty is in the eye of the beholder. (conclusion)
- c2: People disagree about what is beautiful. (premise)
- c3: There is no way to prove one aesthetic judgment correct and another wrong. (premise)
- c4: If beauty were objective, we would all agree about it. (premise)
- c5: Aesthetic judgments vary across cultures and individuals. (premise)
- c6: Beauty must be subjective. (conclusion)
- ['c2', 'c3', 'c4', 'c5'] → c6 (deductive)
- ['c6'] → c1 (definitional)

Analyzing logical structure...

🔍 ISSUES FOUND (5):
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c5 needs supporting evidence
  - circular: Circular reasoning detected involving c6
  - circular: Circular reasoning detected involving c1

## EXAMPLE 18
Argument: We can never step in the same river twice. A river consists of flowing water. The water that makes up the river is different from moment to moment. If the water is different, the river is different. Therefore, the river is constantly changing and never the same.

Parsing argument...

Parsed structure:
- c1: We can never step in the same river twice. (premise)
- c2: A river consists of flowing water. (premise)
- c3: The water that makes up the river is different from moment to moment. (premise)
- c4: If the water is different, the river is different. (premise)
- c5: The river is constantly changing and never the same. (conclusion)
- ['c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c3 needs supporting evidence

## EXAMPLE 19
Argument: All knowledge comes from experience. We are born with minds like blank slates. Every idea we have can be traced back to sensory experience. Even abstract concepts are combinations or abstractions of experiential ideas. There are no innate ideas or a priori knowledge. Therefore, empiricism is the correct theory of knowledge.

Parsing argument...

Parsed structure:
- c1: All knowledge comes from experience. (premise)
- c2: We are born with minds like blank slates. (premise)
- c3: Every idea we have can be traced back to sensory experience. (premise)
- c4: Even abstract concepts are combinations or abstractions of experiential ideas. (premise)
- c5: There are no innate ideas or a priori knowledge. (premise)
- c6: empiricism is the correct theory of knowledge. (conclusion)
- ['c1', 'c2', 'c3', 'c4', 'c5'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (5):
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence
  - unsupported_premise: Premise c5 needs supporting evidence

## EXAMPLE 20
Argument: Death is nothing to us. Death is the absence of experience. Good and bad require experience - you must feel pleasure or pain. When we exist, death is not present. When death is present, we no longer exist. Therefore, death cannot be bad for the person who dies.

Parsing argument...

Parsed structure:
- c1: Death is nothing to us. (conclusion)
- c2: Death is the absence of experience. (premise)
- c3: Good and bad require experience - you must feel pleasure or pain. (premise)
- c4: When we exist, death is not present. (premise)
- c5: When death is present, we no longer exist. (premise)
- c6: Death cannot be bad for the person who dies. (intermediate)
- ['c2', 'c3'] → c6 (deductive)
- ['c4', 'c5', 'c6'] → c1 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 21
Argument: The ends justify the means. The goal of action is to produce good outcomes. An action that produces good outcomes is good, regardless of the action itself. Sometimes harmful actions are necessary to prevent greater harms. Lying to save lives, for example, produces better outcomes than telling the truth. Therefore, morality should focus on consequences, not rules.

Parsing argument...

Parsed structure:
- c1: The ends justify the means. (premise)
- c2: The goal of action is to produce good outcomes. (premise)
- c3: An action that produces good outcomes is good, regardless of the action itself. (intermediate)
- c4: Sometimes harmful actions are necessary to prevent greater harms. (premise)
- c5: Lying to save lives, for example, produces better outcomes than telling the truth. (premise)
- c6: Morality should focus on consequences, not rules. (conclusion)
- ['c1', 'c2'] → c3 (definitional)
- ['c3', 'c4', 'c5'] → c6 (inductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c4 needs supporting evidence
  - unsupported_premise: Premise c5 needs supporting evidence

## EXAMPLE 22
Argument: Motion is impossible. To move from point A to point B, you must first reach the halfway point. To reach the halfway point, you must first reach the quarter-way point. This process continues infinitely. You must complete infinite tasks to move any distance. Completing infinite tasks is impossible. Therefore, motion is impossible.

Parsing argument...

Parsed structure:
- c1: Motion is impossible. (conclusion)
- c2: To move from point A to point B, you must first reach the halfway point. (premise)
- c3: To reach the halfway point, you must first reach the quarter-way point. (premise)
- c4: This process continues infinitely. (intermediate)
- c5: You must complete infinite tasks to move any distance. (intermediate)
- c6: Completing infinite tasks is impossible. (premise)
- ['c2', 'c3'] → c4 (deductive)
- ['c4'] → c5 (deductive)
- ['c5', 'c6'] → c1 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 23
Argument: We cannot prove other minds exist. I know I have consciousness through direct experience. I can only observe other people's behavior, not their consciousness. Behavior could be produced by unconscious automata. There is no way to verify if others have inner experiences. Therefore, I cannot know if anyone else has a mind.

Parsing argument...

Parsed structure:
- c1: We cannot prove other minds exist. (intermediate)
- c2: I know I have consciousness through direct experience. (premise)
- c3: I can only observe other people's behavior, not their consciousness. (premise)
- c4: Behavior could be produced by unconscious automata. (premise)
- c5: There is no way to verify if others have inner experiences. (intermediate)
- c6: I cannot know if anyone else has a mind. (conclusion)
- ['c3', 'c4'] → c5 (deductive)
- ['c1', 'c5'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence

## EXAMPLE 24
Argument: The present is all that exists. The past no longer exists - it has ceased to be. The future does not yet exist - it has not come to be. Only the present moment has existence. But the present has no duration - any duration includes past and future. Therefore, time itself might be an illusion.

Parsing argument...

Parsed structure:
- c1: The present is all that exists. (premise)
- c2: The past no longer exists - it has ceased to be. (premise)
- c3: The future does not yet exist - it has not come to be. (premise)
- c4: Only the present moment has existence. (intermediate)
- c5: the present has no duration (premise)
- c6: any duration includes past and future (premise)
- c7: time itself might be an illusion. (conclusion)
- ['c2', 'c3'] → c1 (deductive)
- ['c1'] → c4 (deductive)
- ['c5', 'c6'] → c7 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - circular: Circular reasoning detected involving c1
  - circular: Circular reasoning detected involving c4

## EXAMPLE 25
Argument: Virtue is knowledge. People only do wrong through ignorance of what is good. If someone truly knew what was good, they would pursue it. No one deliberately chooses what they know to be worse. Therefore, moral education consists in teaching people what is truly good.

Parsing argument...

Parsed structure:
- c1: Virtue is knowledge. (premise)
- c2: People only do wrong through ignorance of what is good. (premise)
- c3: If someone truly knew what was good, they would pursue it. (premise)
- c4: No one deliberately chooses what they know to be worse. (premise)
- c5: Moral education consists in teaching people what is truly good. (conclusion)
- ['c1', 'c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

✅ No logical issues found!

## EXAMPLE 26
Argument: The social contract justifies government. In the state of nature, life is nasty, brutish, and short. People agree to give up some freedom in exchange for security. This agreement creates legitimate political authority. Governments derive their power from the consent of the governed. Therefore, revolution is justified when governments violate the social contract.

Parsing argument...

Parsed structure:
- c1: The social contract justifies government. (premise)
- c2: In the state of nature, life is nasty, brutish, and short. (premise)
- c3: People agree to give up some freedom in exchange for security. (premise)
- c4: This agreement creates legitimate political authority. (intermediate)
- c5: Governments derive their power from the consent of the governed. (premise)
- c6: Revolution is justified when governments violate the social contract. (conclusion)
- ['c2', 'c3'] → c4 (causal)
- ['c1', 'c4', 'c5'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (1):
  - unsupported_premise: Premise c2 needs supporting evidence

## EXAMPLE 27
Argument: Art is the expression of emotion. The purpose of art is to communicate feelings from artist to audience. Successful art makes the audience feel what the artist felt. Technical skill is secondary to emotional authenticity. Therefore, sincere expression matters more than formal beauty in art.

Parsing argument...

Parsed structure:
- c1: Art is the expression of emotion. (premise)
- c2: The purpose of art is to communicate feelings from artist to audience. (premise)
- c3: Successful art makes the audience feel what the artist felt. (premise)
- c4: Technical skill is secondary to emotional authenticity. (premise)
- c5: Sincere expression matters more than formal beauty in art. (conclusion)
- ['c1', 'c2', 'c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (4):
  - unsupported_premise: Premise c1 needs supporting evidence
  - unsupported_premise: Premise c2 needs supporting evidence
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence

## EXAMPLE 28
Argument: Truth is what works. A belief is true if it successfully guides action. Different beliefs work for different people in different contexts. There is no single, objective reality against which to measure beliefs. What matters is practical success, not correspondence to reality. Therefore, truth is relative to purposes and situations.

Parsing argument...

Parsed structure:
- c1: Truth is what works. (premise)
- c2: A belief is true if it successfully guides action. (premise)
- c3: Different beliefs work for different people in different contexts. (premise)
- c4: There is no single, objective reality against which to measure beliefs. (premise)
- c5: What matters is practical success, not correspondence to reality. (premise)
- c6: Truth is relative to purposes and situations. (conclusion)
- ['c1', 'c2', 'c3', 'c4', 'c5'] → c6 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence

## EXAMPLE 29
Argument: Consciousness is what it's like to be something. A system is conscious if there is something it's like to be that system. We cannot explain subjective experience in purely physical terms. Even complete knowledge of brain states wouldn't convey what experience feels like. Therefore, consciousness is irreducible to physical processes.

Parsing argument...

Parsed structure:
- c1: Consciousness is what it's like to be something. (premise)
- c2: A system is conscious if there is something it's like to be that system. (premise)
- c3: We cannot explain subjective experience in purely physical terms. (premise)
- c4: Even complete knowledge of brain states wouldn't convey what experience feels like. (premise)
- c5: Consciousness is irreducible to physical processes. (conclusion)
- ['c3', 'c4'] → c5 (deductive)

Analyzing logical structure...

🔍 ISSUES FOUND (2):
  - unsupported_premise: Premise c3 needs supporting evidence
  - unsupported_premise: Premise c4 needs supporting evidence

## EXAMPLE 30
Argument: Justice is fairness. A just society is one you would choose if you didn't know your position in it. Behind this veil of ignorance, rational people would choose equality. Inequalities are only justified if they benefit the worst off. Therefore, justice requires maximizing the welfare of the least advantaged.

Parsing argument...

Parsed structure:
- c1: Justice is fairness. (premise)
- c2: A just society is one you would choose if you didn't know your position in it. (premise)
- c3: Behind this veil of ignorance, rational people would choose equality. (premise)
- c4: Inequalities are only justified if they benefit the worst off. (intermediate)
- c5: Justice requires maximizing the welfare of the least advantaged. (conclusion)
- ['c2', 'c3'] → c4 (deductive)
- ['c1', 'c4'] → c5 (deductive)

Analyzing logical structure...

✅ No logical issues found!

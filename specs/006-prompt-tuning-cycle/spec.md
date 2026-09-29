# Feature Specification: Prompt Tuning Cycle

**Feature Branch**: `006-prompt-tuning-cycle`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "I want to create a manual process with skill to overfit the prompts according the reports, like the artifact Video Performance Report, the idea is to document what is working, what is not, the period etc. The overfit is not just go into what is working direction, is to keep a base of what work and also have a space to explore, what we don't explored yet, different ideas of what we have explored to confirm the bias or to chalange it, and document. We will periodically overfit the prompt with the goal to make better but also with a space to learn"

## Context

The system now keeps a history of every video: the Reddit signals, the model's grade, the prompt versions and settings that produced it, and the TikTok performance collected afterwards. A first reading of that history (84 videos, 29 Aug to 28 Sep 2026, published as the Video Performance Report) already produced leads: workplace stories where the narrator gets even do far better than their neighbours, stories about strangers and businesses never take off, partner stories are exactly average, titles that promise a reaction help.

Those leads live today in a report and in the operator's head. The editorial prompts (the one that grades which stories are worth producing, the one that writes the title and script, the one that picks hashtags) know nothing about them. The operator wants a repeatable, manual routine, run with the assistant's help, that reads the channel's performance, writes down what was learned, and adjusts the prompts accordingly.

The routine must not simply chase whatever performed best. Eighty-four videos from one month, on a channel whose reach was falling week over week, is thin evidence, and a prompt that only repeats past winners stops producing the information needed to find the next one. So the routine keeps two things side by side: a **base** of what the evidence supports, which the prompts lean on, and an **exploration space** reserved for what has not been tried, for variations of what has, and for deliberate attempts to confirm or challenge what the channel currently believes. Both are documented, so that each cycle starts from what the previous ones learned instead of from memory.

The routine has two rhythms. A **cycle** is the stretch of time during which one set of prompts is in effect; it stays open until the operator closes it. A **follow-up report** is what the operator gets each time they run the skill, as often as they like: a reading of how the open cycle is going, which changes nothing by itself. From a report the operator may adjust the experiments, which does not end the cycle; the prompts are touched only when the cycle is closed. Each report ends with the assistant's recommendation to keep the cycle running or to close it, and the operator decides.

Tuning stays a human decision. The assistant reads, recommends and writes; the operator decides when a cycle ends and approves every change to a prompt or an experiment.

## Clarifications

### Session 2026-09-29

- Q: How is the room for exploration guaranteed when the daily run picks the highest-graded stories? → A: Each candidate story gets two separate scores, one for how good a base story it is and one for how well it serves exploration. The daily run fills base slots from the first ranking and exploration slots from the second, and labels each video with the goal it was picked for. Each video is later judged against its own goal: a base video by how it performed, an exploration video by what it let the channel learn.
- Q: What does the exploration score rank? → A: Fit to the cycle's open experiments only. A story scores high when it serves one of the written experiments, and its label names that experiment. Being unlike what the channel has published earns nothing by itself; untried territory is explored by writing an experiment for it.
- Q: When does a cycle end, and what does running the skill do? → A: A cycle has no fixed length. Running the skill produces a follow-up report, probably once or twice a week, and does not end the cycle by itself. The operator decides when the cycle ends; the skill recommends ending it or keeping it running. When a cycle ends the operator keeps, changes or closes each experiment, and the skill suggests new experiment ideas.
- Q: How many experiments can be open at once? → A: No fixed limit. The assistant recommends how many to keep open and in what order of priority, given the exploration slots available, and the operator decides.
- Q: Can experiments change while a cycle stays open? → A: Yes. At any report the operator can keep, change, close or open experiments, and adjust their priority order and the exploration share; the cycle stays open and the report records the change with its date. Prompts change only when a cycle is closed.
- Q: Where is the information kept and where is the report read? → A: In two separate forms. What matters (findings, beliefs, experiments, decisions, prompt changes) is stored in the repository, in the form best suited to storing it. The report the operator reads is a separate, ephemeral reading view in the form best suited to reading, such as a published page like the Video Performance Report or a PDF; it can be thrown away and produced again from what is stored.

## User Scenarios & Testing *(mandatory)*

The actor in every story is the operator, who runs the channel and is its sole maintainer, working with the assistant through a skill they invoke by hand.

### User Story 1 - Ask for a follow-up report and see what is working (Priority: P1)

As the operator, whenever I want, I run the skill and get a follow-up report. It reads the performance history for a period (by default the last 30 days) and states the period, how many videos it covers, which prompt versions were in effect, what worked, what did not, and what is still unclear. Each finding says what it is based on (how many videos, how they did relative to the videos published around them) and how much it can be trusted. Conditions that distort the reading, such as a channel-wide drop in reach or a stretch of failed uploads, are stated next to the findings they affect. The report also shows how the open cycle is going: each experiment's progress, how the videos made under the current prompts compare with those before, and how much of the production went to exploration. Asking for a report changes nothing by itself: the cycle, the prompts and the experiments stay as they were unless I decide otherwise.

**Why this priority**: The report is the foundation of everything else and has value alone: it leaves the channel's knowledge on paper instead of in memory, and it is what the operator will use most often. It is also the step that protects against tuning on noise.

**Independent Test**: With a history covering at least one month, ask for a report and check that it states the period, the video count and the prompt versions, that every finding carries its evidence and a confidence level, that a finding backed by too few videos is labelled as a lead, and that after the report the prompts, the experiments and the open cycle are unchanged.

**Acceptance Scenarios**:

1. **Given** a history with collected performance for the period, **When** the operator asks for a report, **Then** it is produced with the period, the number of videos, the prompt versions in effect, and separate lists of what worked, what did not and what is inconclusive.
2. **Given** a finding, **When** the operator reads it, **Then** it shows the number of videos behind it, how those videos performed relative to their neighbours in time, and a confidence level.
3. **Given** a pattern supported by fewer videos than the minimum evidence threshold, **When** the report is written, **Then** the pattern appears as a lead to test, and is not eligible to enter the base.
4. **Given** the period contains a known distortion (reach falling across the whole channel, a run of failed uploads, videos too recent to have settled numbers), **When** the report is written, **Then** the distortion is stated and the findings it affects say so.
5. **Given** the period has too few videos with collected performance to say anything, **When** the operator asks for a report, **Then** the assistant says so with the numbers and proposes either widening the period or collecting first, and no findings are invented.
8. **Given** a report was produced, **When** its reading view is discarded or lost, **Then** everything it said is still in the stored record, and the reading view can be produced again from it.
6. **Given** an open cycle, **When** the operator asks for a report and takes no decision, **Then** the cycle stays open, the prompts and experiments are untouched, and the report is kept as a follow-up of that cycle.
7. **Given** a report a few days after the previous one, **When** it is produced, **Then** it states what is new since the previous report and does not present an unchanged finding as fresh confirmation.

---

### User Story 2 - Decide when the cycle ends, with a recommendation (Priority: P1)

As the operator, every report ends with the assistant's recommendation: keep the cycle running or close it, with the reasons. Reasons to close are things like an experiment reaching its sample target, a finding strong enough to change a prompt, or a prompt change that is clearly hurting. Reasons to keep going are things like experiments still short of their targets or too few settled videos since the cycle opened. I decide. If I keep it running, the prompts stay as they are, and I may still adjust the experiments. If I close it, the assistant settles the cycle, I tune the prompts and review the experiments, and the next cycle opens with what I decided.

**Why this priority**: This is what lets the operator look often without changing things often. Without it, every look at the numbers becomes a temptation to tune, and changes pile up faster than they can be evaluated.

**Independent Test**: With an open cycle whose experiments are short of their targets, ask for a report and confirm the recommendation is to keep it running with the counts as reasons; decline to close and confirm nothing changed. With an open cycle whose experiment reached its target, confirm the recommendation is to close; close it and confirm a new cycle opened with the decisions taken.

**Acceptance Scenarios**:

1. **Given** any report on an open cycle, **When** it is produced, **Then** it ends with a recommendation to keep the cycle running or to close it, and the reasons for it.
2. **Given** a recommendation to close, **When** the operator chooses to keep the cycle running, **Then** the cycle stays open and the report records the recommendation and the operator's decision.
3. **Given** a recommendation to keep running, **When** the operator chooses to close anyway, **Then** the cycle is closed, and what could not be judged yet is recorded as such.
4. **Given** the operator closes a cycle, **When** the closing is complete, **Then** the cycle's record holds its start and end dates, its prompts, its experiments with their outcome, its reports, and the decisions taken, and the next cycle is open.
5. **Given** the first time the routine is used, **When** the operator runs the skill, **Then** there is no open cycle; the first cycle is opened with the prompts in effect as baseline and the existing report's leads as starting beliefs.

---

### User Story 3 - Tune the prompts on the base, with the reason attached (Priority: P1)

As the operator, when I close a cycle I receive a proposal of changes to the editorial prompts that reflect the base: what the evidence supports about which stories to pick, how to title them and how to tell them. Each proposed change names the finding that motivates it and is written as an explanation of what the audience responds to and why, not as a list of special-case rules. I approve, adjust or reject each change. What I approve is applied, and the record states which prompt versions the closed cycle had and which the new one has, so every later video can be traced to the cycle that shaped it.

**Why this priority**: This is the improvement the operator is after. It shares P1 with the report because reports that never reach the prompts change nothing on the channel.

**Independent Test**: Close a cycle with at least one finding strong enough for the base; confirm each proposed change cites its finding, reads as rationale, and that after approval the prompt differs, the record lists the old and new versions, and a rejected change left its prompt untouched.

**Acceptance Scenarios**:

1. **Given** a cycle being closed with findings eligible for the base, **When** the operator asks for the prompt proposal, **Then** each proposed change shows the current wording, the proposed wording and the finding that justifies it.
2. **Given** a proposed change, **When** the operator rejects it, **Then** the prompt is left as it was and the record notes the rejection and the reason given.
3. **Given** approved changes, **When** they are applied, **Then** the record lists the prompt versions of the closed cycle and of the new one, and videos produced from then on carry the new versions in the history.
4. **Given** a finding that holds only for a narrow case, **When** the change is written, **Then** it conveys the underlying reason the audience responded, so the model can apply it to stories the finding never saw, in line with the project's principle that prompts carry rationale.
5. **Given** a cycle being closed whose findings justify no prompt change, **When** the proposal is requested, **Then** the assistant says the prompts stay as they are, and the new cycle differs only in its experiments.

---

### User Story 4 - Reserve room to explore and to challenge what we believe (Priority: P2)

As the operator, each cycle has an exploration agenda alongside the base. It holds experiments, each written down before any video is made: the question it asks, why it is worth asking, how stories belonging to it will be recognised, how many videos it needs, and what result would count as confirming or refuting it. Experiments come in three kinds: territory the channel has not tried, variations of something it has, and challenges to a current belief, including giving a second chance to something the channel wrote off on thin evidence. At any report I can keep, change or close each experiment and open new ones, without closing the cycle, and the assistant suggests new ideas. There is no fixed limit on how many run at once; the assistant recommends how many the exploration slots can carry and in what order, and I decide. Every candidate story is scored twice, once as a base story and once for how well it serves an open experiment, and the daily run fills the exploration slots from the second ranking.

**Why this priority**: This is what separates the routine from plain overfitting and is the operator's explicit request. It is P2 only because it needs the report and the cycle to exist first.

**Independent Test**: Ask for a report on a history where one story type dominates the winners; confirm the assistant suggests at least one experiment outside that type and at least one that challenges a current belief, each complete and written before the next videos are produced, with a recommendation of how many to open. Then run the daily run against fake candidates and confirm the exploration slots were filled from the exploration ranking and each video carries its goal.

**Acceptance Scenarios**:

1. **Given** a report, **When** the operator reviews the exploration agenda, **Then** the assistant suggests new experiment ideas drawn from the findings, from beliefs with thin evidence and from territory the channel has not tried, of the three kinds (unexplored, variation, challenge), each with its question, its motivation, how its stories are recognised, the number of videos needed and the result that would confirm or refute it.
2. **Given** the channel believes a story type does not work on the basis of a handful of videos, **When** the agenda is built, **Then** that belief is offered as a candidate for a challenge experiment, with the thinness of its evidence stated.
3. **Given** a belief in the base that has not been retested within the retest interval, **When** the agenda is built, **Then** it is flagged as due for retesting.
4. **Given** open experiments, **When** the operator reviews the agenda at a report, **Then** each is shown with its progress toward its sample target and a recommendation, and the operator keeps it, changes it or closes it while the cycle stays open; the report records each decision with its date, a kept experiment carries its videos on, including into the next cycle, and a changed experiment is recorded as a new one that refers to the old, so videos made under the old wording are not judged by the new.
5. **Given** the experiments the operator wants open and the exploration slots expected, **When** the agenda is built, **Then** the assistant recommends how many to keep open and their order of priority, states how long each would take to reach its target, and warns when the set is too large for any of them to conclude; the operator's choice stands either way.
6. **Given** ideas the operator does not open now, **When** the agenda is settled, **Then** they are kept in a backlog with their motivation.
7. **Given** the exploration share and the priority order of the open cycle, **When** the daily run picks its stories, **Then** it reserves that share of its slots for exploration, gives each of those slots to the highest-priority experiment that has a fitting story that day, and fills the rest from the base ranking.
8. **Given** a video produced during a cycle, **When** the operator reads its history record, **Then** it shows the goal the video was picked for (base, or the experiment it serves) and both scores the story received.
9. **Given** a day on which no candidate serves any open experiment well enough, **When** the daily run fills its slots, **Then** the exploration slots go to base stories, and the unfilled exploration slots are counted so the achieved share stays truthful.

---

### User Story 5 - Settle a cycle when it closes (Priority: P2)

As the operator, when I close a cycle the assistant settles it. Each experiment that reached its sample target gets a verdict against the rule written beforehand: confirmed, refuted or inconclusive. The prompt changes the cycle started with are compared with what came before. Beliefs move accordingly: a confirmed experiment can enter the base, a refuted belief leaves it, and a change that made things worse is proposed for reversal. The record also states how much of the cycle's production was exploration in practice, against what was intended.

**Why this priority**: Without this step the experiments are never read and the routine degrades into opinion. It is P2 because it only becomes possible once a cycle has run.

**Independent Test**: With an open cycle holding one experiment at its target, one short of it and one prompt change, close the cycle and confirm the first experiment received a verdict judged by its pre-written rule, the second is shown as in progress without a verdict, the prompt change received a before/after comparison, and the beliefs list reflects the verdict.

**Acceptance Scenarios**:

1. **Given** an experiment whose settled videos reached its sample target, **When** the cycle is closed, **Then** it gets a verdict of confirmed, refuted or inconclusive, judged against the decision rule written when it was opened, with the videos it was based on.
2. **Given** an experiment that has not reached its sample target, **When** the cycle is closed, **Then** it is shown as in progress with the count reached and its results so far, without a verdict, and the operator chooses to keep it, change it or close it.
3. **Given** the prompt changes the cycle started with, **When** the cycle is closed, **Then** the record compares base videos produced in the cycle with those of the cycle before, each relative to its neighbours in time, and states whether the changes helped, hurt or cannot be told.
4. **Given** a change that hurt, **When** the comparison is shown, **Then** reverting it is proposed to the operator with the evidence, and the reversal, if approved, is recorded like any other change.
5. **Given** a refuted belief that was in the base, **When** beliefs are updated, **Then** it leaves the base, the record keeps what was believed, since when and what overturned it, and the prompt wording that relied on it is proposed for change.
6. **Given** the intended exploration share of the cycle, **When** it is closed, **Then** the record shows the share achieved in practice and points it out when it fell well short.

---

### User Story 6 - Read what the channel knows at a glance (Priority: P3)

As the operator, at any time I can open one place that shows the channel's current knowledge: the beliefs in the base with their evidence and when they were last tested, what is known not to work, the experiments in progress, the backlog of ideas, and the list of cycles with their dates, reports and prompt changes. From a sentence in a prompt I can find the cycle and the finding that put it there.

**Why this priority**: It makes the accumulated learning usable between reports and months later. It is P3 because the cycle records already hold the information; this is the consolidated reading of it.

**Independent Test**: After two closed cycles, open the knowledge summary and confirm it lists current beliefs with evidence and last-tested date, open experiments, backlog and cycles, and that a chosen sentence of a tuned prompt can be traced to its cycle and finding.

**Acceptance Scenarios**:

1. **Given** at least one closed cycle, **When** the operator opens the knowledge summary, **Then** it shows the base, what does not work, open experiments, the backlog and the cycles, each belief with its evidence, confidence and the date it was last tested.
2. **Given** a passage of a prompt introduced when a cycle was closed, **When** the operator asks where it came from, **Then** the cycle and the finding or experiment behind it are identified.
3. **Given** a belief whose status changed over time, **When** the operator reads it, **Then** its history is visible: when it entered, what confirmed or overturned it, and in which cycle.

---

### Edge Cases

- The first use has no open cycle and no documented beliefs. The existing report's leads are taken in as the starting beliefs, labelled with their evidence as it stands (one month, 84 videos), and the prompts in effect become the baseline of the first cycle.
- Videos published in the last days have not accumulated their views yet. They are left out of findings and verdicts and marked as unsettled; a later report counts them.
- Performance for the period was never collected or is stale. The report stops and asks for a collection first; it does not reason over missing numbers.
- Reach for the whole channel moves during the period, so raw views of two weeks are not comparable. Findings compare each video with the videos published around it, and the channel-wide movement is reported separately.
- Failed uploads remove videos from the sample unevenly. The report states how many were lost and whether any story type or experiment was hit harder.
- A story scores high on both rankings, or serves two experiments. It takes one slot only and carries one goal, the one it was picked for; a base video that happens to fit an experiment is not counted in that experiment's verdict.
- Videos produced before the two rankings existed carry no goal. They are attributed from the recognition rules; when the rules do not settle it, the video is listed as ambiguous and excluded from the verdicts.
- An exploration video gets few views. That alone is not a failure: it is judged by whether its experiment reached a verdict, and its views are kept out of the comparison that evaluates base prompt changes.
- A cycle is left open for a long time. Reports keep being possible, and the recommendation says so when the cycle has nothing more to learn by staying open.
- A cycle is closed very soon after it opened, before enough settled videos exist. Its prompt changes are recorded as not evaluated, and the record says the following cycle cannot separate their effect from the next changes.
- The operator opens more experiments than the slots can carry. The choice stands; every report shows the time each experiment is expected to take, and repeats the warning while it holds.
- Several things changed at once between two cycles (a prompt, the writing model, the voice). The before/after comparison says the effect cannot be attributed to the prompt alone.
- The operator edited a prompt by hand while a cycle was open. The next report detects that the version in effect is not the one the cycle opened with, records the change as made outside the routine, asks the operator for its reason, and recommends closing the cycle so that videos before and after are not mixed.
- The evidence contradicts something the operator is convinced of. The finding is recorded as found; the operator may keep the prompt as is, and the record states that the decision went against the evidence and why.
- An experiment turns out to be impossible to test because the source material for it rarely appears. The report shows its unfilled slots and recommends closing it as not testable; it is kept in the backlog with that note.
- The closing of a cycle is abandoned halfway, after the settling and before any decision. The cycle stays open, and what was written is kept as a follow-up report.

## Requirements *(mandatory)*

### Functional Requirements

**The cycle and the reports**

- **FR-001**: The operator MUST be able to ask for a follow-up report on demand through a skill, as often as they want, stating a period or accepting the default of the last 30 days.
- **FR-002**: A cycle MUST be the stretch of time during which one set of editorial prompts is in effect. Exactly one cycle is open at a time, and a cycle has no fixed length.
- **FR-003**: Asking for a report MUST NOT by itself change the cycle, the prompts or the experiments. A cycle ends only when the operator decides to close it.
- **FR-003a**: At any report the operator MUST be able to keep, change, close or open experiments and to adjust their priority order and the exploration share, without closing the cycle. The report MUST record each such decision with its date.
- **FR-004**: Every report MUST end with a recommendation to keep the cycle running or to close it, with the reasons, and MUST record the operator's decision.
- **FR-005**: Closing a cycle MUST proceed in a fixed order: settle the cycle, propose changes to the base, review the experiments and build the next agenda, apply what the operator approved, write the record and open the next cycle. If the operator stops before deciding, the cycle stays open.
- **FR-006**: Nothing in the routine runs by itself. Every report is asked for by the operator, and every change to a prompt or to an experiment requires the operator's explicit approval.
- **FR-007**: A report MUST refuse to produce findings when the period holds fewer videos with collected performance than the minimum the operator has set, and MUST say how many it found.

**The review**

- **FR-008**: Every report MUST state the period, the number of videos considered and excluded (with the reason for exclusion), the prompt versions and production settings in effect, the date of the performance data it used, and the cycle it belongs to.
- **FR-009**: Every report MUST list what worked, what did not and what is inconclusive, covering at least the kind of story, the title and opening, and the posting conditions.
- **FR-010**: Every finding MUST state the number of videos behind it, their performance relative to the videos published around them, and a confidence level derived from that evidence.
- **FR-011**: A finding supported by fewer videos than the evidence threshold MUST be recorded as a lead and MUST NOT enter the base or justify a base change.
- **FR-012**: Every report MUST state the conditions that distort the reading (channel-wide reach movement, failed uploads, unsettled recent videos, several settings changed at once) and mark the findings they affect.
- **FR-013**: Videos too recent to have settled performance MUST be excluded from findings and verdicts.
- **FR-014**: Every report MUST show, for the open cycle, each experiment's progress toward its sample target with the results so far, the exploration share achieved against the share intended, and how the base videos made in the cycle compare with those of the cycle before.
- **FR-015**: A report MUST state what changed since the previous report and MUST NOT present a finding resting on the same videos as new confirmation.

**The base and the prompts**

- **FR-016**: The routine MUST maintain a base: the set of beliefs the evidence currently supports, each with its statement, its evidence, its confidence, the cycle in which it entered and the date it was last tested.
- **FR-017**: The routine MUST equally maintain what is believed not to work, held to the same standard of evidence as the base.
- **FR-018**: Proposed prompt changes MUST each show the current wording, the proposed wording and the finding, belief or experiment that justifies it.
- **FR-019**: Prompt changes MUST be written as the reason the audience responds, so the model can generalise, and MUST NOT take the form of case-by-case rules; this follows the project's principle on rationale-based prompts.
- **FR-020**: The operator MUST be able to approve, modify or reject each proposed change individually; rejected changes leave the prompt untouched and are recorded with the reason.
- **FR-021**: Editorial prompts MUST change only when a cycle is closed, and the record MUST state the prompt versions of each cycle, so that every video in the history can be attributed to the cycle that shaped its prompts.
- **FR-022**: A change made to a prompt while a cycle is open MUST be detected at the next report and recorded, with the reason the operator gives.
- **FR-023**: The routine MUST cover the editorial prompts that decide which stories are produced and how they are titled, told and tagged.

**Exploration**

- **FR-024**: Every cycle MUST have an exploration agenda in addition to the base, and the operator MUST be able to set the share of the cycle's production intended for it.
- **FR-025**: Every experiment MUST be written before its videos are produced, with: the question, its kind (unexplored, variation, challenge), its motivation, how its stories will be recognised, the number of videos it needs and the result that would confirm or refute it.
- **FR-026**: An experiment MAY span several cycles; closing a cycle does not close its experiments, and a kept experiment carries its videos into the next cycle. A changed experiment MUST be recorded as a new experiment referring to the one it replaces, and videos labelled with the old one stay with the old one.
- **FR-027**: In every report the routine MUST suggest new experiment ideas, each with its motivation, drawn from the findings, from beliefs resting on thin evidence, from beliefs not retested within the retest interval and from territory not yet tried. At least one suggestion MUST be unexplored territory or a challenge to a current belief. The operator opens, defers or discards each.
- **FR-028**: The number of experiments open at once MUST NOT be limited by the routine. The routine MUST recommend how many to keep open and their order of priority, state how long each is expected to take to reach its sample target given the exploration slots, and warn when the set is too large to conclude. The operator's choice prevails.
- **FR-029**: Experiment ideas not opened MUST be kept in a backlog with their motivation.
- **FR-030**: Every candidate story MUST receive two separate scores: a base score, for how well it matches what the evidence supports, and an exploration score, for how well it serves the cycle's open experiments. Neither score is derived from the other. The exploration score MUST name the experiment the story serves; novelty alone, without an open experiment it fits, MUST NOT earn an exploration score.
- **FR-031**: The daily run MUST reserve the cycle's exploration share of its slots, give each of them to the highest-priority open experiment that has a fitting story, and fill the remaining slots from the base ranking. A story takes one slot only. With no open experiment, no slot is reserved.
- **FR-032**: Every video MUST be labelled at production with the goal it was picked for (base, or the experiment it serves), and its history record MUST hold that goal and both scores.
- **FR-033**: When no candidate serves an open experiment well enough, the exploration slot MUST go to a base story and be counted as an unfilled exploration slot.
- **FR-034**: Each video MUST be judged against its own goal: a base video by its performance relative to its neighbours in time, an exploration video by its contribution to its experiment's verdict. Exploration videos MUST be left out of the comparison that evaluates base prompt changes.

**Settling a cycle**

- **FR-035**: At the first report after it reaches its sample target in settled videos, and at the latest when the cycle is closed, an open experiment MUST receive a verdict of confirmed, refuted or inconclusive, judged against the rule written when it was opened, together with the videos it was based on.
- **FR-036**: An experiment that has not reached its sample target MUST be shown as in progress with the count reached and no verdict. An experiment the operator closes before its target is recorded as closed without verdict, with the count reached.
- **FR-037**: The prompt changes a cycle started with MUST be evaluated by comparing the base videos of that cycle with those of the cycle before, each relative to its neighbours in time, with a statement of whether they helped, hurt or cannot be told. When too few settled videos exist, they MUST be recorded as not evaluated.
- **FR-038**: Beliefs MUST be updated from the verdicts: confirmed experiments become eligible for the base, refuted beliefs leave it, and the prompt wording depending on a refuted belief is proposed for change.
- **FR-039**: A prompt change found to have hurt MUST be proposed for reversal, and an approved reversal is recorded as a change.
- **FR-040**: Verdicts MUST be based on the goal each video was labelled with. A video without a label (produced before labelling existed) that cannot be attributed unambiguously to the base or to one experiment MUST be listed as ambiguous and left out of the verdicts.

**The knowledge over time**

- **FR-041**: The stored record of every cycle and of every report (its findings, the state of the cycle, the recommendation and the decisions) MUST be kept permanently in the repository, in order, and never rewritten; a later correction is a new entry that refers to the earlier one.
- **FR-041a**: Every report MUST also be delivered as a reading view made for the operator to read, with the visual treatment of the Video Performance Report. The reading view is ephemeral: it MUST hold nothing that is not in the stored record, and it MUST be reproducible from the stored record.
- **FR-041b**: The stored record MUST be organised for storing and retrieving (so that later reports, the assistant and the operator can find a belief, an experiment or a decision), and the reading view for reading; neither form is required to serve the other's purpose.
- **FR-042**: The operator MUST be able to read a consolidated summary of the current knowledge: the base, what does not work, open experiments, the backlog and the list of cycles.
- **FR-043**: Every belief MUST keep its history: when it entered, what confirmed, weakened or overturned it, and in which cycles.
- **FR-044**: From a passage of a prompt, the operator MUST be able to identify the cycle and the finding or experiment that introduced it.
- **FR-045**: The stored records and the summary MUST be readable without the assistant and without running anything.
- **FR-046**: The routine itself MUST change only the editorial prompts, the open experiments with their priority order and the exploration share, and its own records. Apart from the two rankings, the slot reservation and the goal label, how videos are produced, published and measured MUST remain as it is.

### Key Entities

- **Tuning cycle**: the stretch of time during which one set of prompts is in effect. Has a sequence number, the date it opened, the date it closed (empty while open), its prompt versions, the experiments that ran in it with the dated changes made to them, to their priority order and to the exploration share, the share achieved, its follow-up reports, and the decisions taken at its closing.
- **Follow-up report**: one reading asked for by the operator. Has its date, the period it read, the videos considered and excluded, its findings, the state of the open cycle, what changed since the previous report, the recommendation to keep or close the cycle with its reasons, and the operator's decision. Exists in two forms: the stored record, which is permanent, and the reading view, which is ephemeral.
- **Finding**: something observed in a report's period. Has a statement, the area it concerns (story kind, title and opening, posting conditions), the videos behind it, their relative performance, a confidence level and the distortions that affect it.
- **Belief**: what the channel currently holds to be true, built from findings across cycles. Has a statement, a status (in the base, known not to work, lead, contested, retired), its accumulated evidence, the cycle in which it entered, the date it was last tested and its history.
- **Experiment**: a question put to the audience on purpose. Has a kind (unexplored, variation, challenge), the question, the motivation, the belief it tests when there is one, the rule for recognising its stories, the sample target, the decision rule, its priority, the cycle that opened it, the experiment it replaces when there is one, and its outcome (verdict, or closed without verdict) with the videos it was judged on. It may span several cycles.
- **Prompt change**: one approved, modified or rejected alteration of an editorial prompt, decided at the closing of a cycle. Has the prompt concerned, the wording before and after, the justification (finding, belief or experiment), the operator's decision and, once the following cycle is settled, its evaluation.
- **Video goal**: what a video was picked for, recorded at production on its history record: base, or the experiment it serves, together with the base score and the exploration score the story received.
- **Backlog idea**: an experiment not yet run, with its motivation and the cycle in which it was raised.
- **Knowledge summary**: the consolidated, current reading of beliefs, open experiments, backlog and cycles.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The operator gets a follow-up report, reads it and decides whether to keep or close the cycle in under 10 minutes of their own time.
- **SC-002**: The operator closes a cycle, from the decision to approved prompts, settled experiments and an open next cycle, in under 45 minutes of their own time.
- **SC-003**: 100% of the changes made to editorial prompts are traceable to a documented finding, belief or experiment, and to the cycle closing that applied them.
- **SC-004**: 100% of findings state their video count, relative performance and confidence; none enters the base below the evidence threshold.
- **SC-005**: 100% of reports end with a recommendation to keep or close the cycle with its reasons, and leave the prompts unchanged unless the operator closes the cycle and the experiments unchanged unless the operator decides on them.
- **SC-006**: Every report offers at least two new experiment ideas with their motivation, at least one of them untried territory or a challenge to a current belief.
- **SC-007**: Every experiment that reaches its sample target receives its verdict at the first report after that, and every report shows its progress until then.
- **SC-008**: The exploration share achieved is within 10 percentage points of the share intended in at least three of every four cycles that have open experiments.
- **SC-009**: 100% of videos produced during a cycle carry their goal and both scores in the history.
- **SC-010**: No belief stays in the base for more than three months without being retested or carrying a recorded decision not to.
- **SC-014**: 100% of what a reading view shows can be found in the stored record, and a discarded reading view can be produced again without asking the operator anything.
- **SC-011**: From the knowledge summary alone, the operator can answer "why does the prompt say this?" and "what do we currently believe about this kind of story, and on how many videos?" in under two minutes each.
- **SC-012**: After three months, the operator can state with numbers whether base videos produced under tuned prompts perform better, relative to their neighbours in time, than those produced under the baseline prompts.
- **SC-013**: After three months, at least one belief has changed status because of an experiment (entered the base, left it, or was overturned), showing the routine learns and does not only confirm.

## Assumptions

- The performance history and the crossed view delivered by the previous feature are the source of evidence, including retention, traffic sources and followers gained where collected. The Video Performance Report of September 2026 is the model for what a report reads and the origin of the first cycle's starting beliefs. Collecting performance remains a separate step the operator runs before asking for a report.
- "Overfitting" in the operator's words means fitting the prompts to this channel's own audience data on purpose. The exploration space and the evidence threshold are what keep that from turning into fitting to noise.
- Performance is judged relative to the videos published around each video, as the existing report does, because the channel's overall reach moves from week to week.
- The operator expects to ask for a report about once or twice a week. That is a habit, not a rule of the routine: nothing depends on the interval between reports, and a cycle lasts as long as the operator leaves it open.
- A report reads the last 30 days by default, which may reach back before the open cycle, because a single week holds too few videos to support findings. What it says about the open cycle is limited to the videos made in it.
- Defaults the operator can change: an exploration share of about one quarter of production; an evidence threshold of ten videos for a finding to enter the base; a retest interval of three months; videos younger than seven days treated as unsettled.
- Prompts change only at the closing of a cycle. Holding them still while a cycle is open is what makes the base videos of a cycle comparable with each other. Experiments can change at any report because every video carries the label of its experiment, so changing one does not disturb the others or the base.
- The editorial prompts in scope are the one that grades stories for selection, the one that writes title and script, and the one that chooses hashtags. The transcription clean-up prompt and the publishing agent's instructions are outside the routine.
- The routine is carried out by the operator with the assistant through a skill. The daily run scores each candidate twice, reserves the exploration slots and labels each video with its goal; classifying stories by kind for the findings is still done by the assistant from the history when a report is asked for.
- Scoring a story for exploration adds little cost: grading is one model request per candidate and is a small part of what a video costs next to writing, narration and rendering. Whether both scores come from one request or two is a planning decision.
- The stored records live with the project, under version control next to the prompts they explain, so a prompt change and its reason travel together. Their format is chosen in planning for what stores and retrieves best.
- The reading view is a published page like the existing Video Performance Report; a PDF is an acceptable alternative. Which one, and whether each report gets a new page or updates the same one, is a planning decision, since the view is disposable either way.
- The records follow the project's language rule for documentation addressed to the operator; prompt wording stays in the language the prompts are written in.
- Comment text is not yet collected, so audience comments are not evidence at first; when that collection exists it becomes one more input without changing the routine.
- Automatic tuning, scheduled reports, and running two prompt versions side by side on the same day are out of scope.

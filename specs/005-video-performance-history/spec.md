# Feature Specification: Video Performance History

**Feature Branch**: `005-video-performance-history`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "I want to store information about the runs, the videos, generated (not the process, thinking or anything like that) just summary of history, some info of the reddit, like link upvotes comments etc, and be able to get info from the tiktok account and cross with those infos. In the end my goal is to cross the video info with tiktok info ex: A video was rated like 9 for LLM, doing good on reddit, but it didn't perform well on tiktok, or other scenario, not too good video went well on tiktok, I want to have those informations to maybe overfit prompts, change strategies try new strategies etc. But for now I just want this info and have the code prepared for future things"

## Context

Every day the system discovers Reddit stories, grades them with a model, writes a script, renders a video and schedules it on TikTok. Almost everything it learns along the way is thrown away at the end of the run. What survives today is a manifest per video (file path, title, summary, post link, part number) and one line per publish attempt in a log (status, scheduled time, hashtags, error). Nothing records how popular the post was on Reddit when it was picked, what grade the model gave the story, which prompt and model wrote it, or how the resulting video did on TikTok.

The operator wants to start keeping that record now, and to be able to put the TikTok side next to it: for each video, the Reddit signals, the model's grade, the production settings that shaped it, and the performance the video got on the TikTok account. The point is to see patterns such as "the model loved it and Reddit loved it, TikTok did not" or "a middling story went viral", and later use them to adjust prompts and try new strategies. Adjusting prompts or choosing strategies automatically is not part of this feature. This feature collects the information and leaves the seams in place for whatever comes next.

Only outcomes are recorded. The model's reasoning, the agent's browser steps and other process detail stay out of the history.

## Clarifications

### Session 2026-09-28

- Q: Where do the TikTok performance metrics come from? → A: From the TikTok Studio analytics pages, read with the logged-in session the server already holds, by automated page reading without an AI agent. An export-file import and the official interface remain possible later behind the same contract.
- Q: How is a TikTok video matched to its history record? → A: By the caption the system published plus the scheduled time; ambiguous or unmatched videos are reported and resolved by hand. Adding an identifying marker to every caption was considered and rejected so that nothing the audience sees changes.
- Q: Where does the history live now? → A: In a single-file embedded database (SQLite) behind the existing storage boundary. The manifests and the CSV publish log keep being written exactly as today, so publish-only mode and the current files are untouched.
- Q: Does the run itself leave a record? → A: Yes, a summary per run (when, mode, candidates found, target, produced, scheduled, skipped and why). It is a separate entity from the video record: each can be read on its own, the run summary holds no video data, and a video record is complete without its run.
- Q: Are the Reddit signals frozen at discovery or refreshed? → A: Both: the discovery snapshot is kept, and every performance collection also re-reads the post's upvotes, comment count and upvote ratio and stores them as a dated snapshot, the same way TikTok metrics are kept.

## User Scenarios & Testing *(mandatory)*

The actor in every story is the operator, who runs the system and is its sole maintainer.

### User Story 1 - Every video leaves a durable record (Priority: P1)

As the operator, after a daily run I can find, for each video it produced, a single record holding what the system knew about that story at the time: the Reddit post's link, community, author, upvotes, comment count, upvote ratio and posting time as seen when it was discovered; the model's grade with its five component grades, verdict and summary; the video's title, part number, language and duration; and, once the video is scheduled, the publish attempt with its time, hashtags and outcome. The record is written by the run itself, without any extra step.

**Why this priority**: Without the record nothing else in this feature is possible, and every day that passes without it is data lost. It also costs the least: the run already has every one of those values in hand and simply drops them today.

**Independent Test**: Run the daily run in generate-only mode against fake capabilities and read the history back: one record per rendered video, carrying the discovery signals, the grade, the video facts and no publish attempt. Then run publish-only on the same videos and confirm each record gained its attempt with the outcome.

**Acceptance Scenarios**:

1. **Given** a daily run that renders and schedules stories, **When** it finishes, **Then** every rendered video has one record with the Reddit signals, the model grade, the video facts and the publish attempt, and nothing the operator has to do by hand.
2. **Given** a story with more than one part, **When** it is rendered, **Then** each part has its own record, all sharing the same story-level data and each with its own part number and publish attempt.
3. **Given** a video whose publish attempt failed, **When** the run continues, **Then** the record keeps the failed attempt with its error, and a later successful attempt is added to the same record rather than replacing it.
4. **Given** a video produced in generate-only mode, **When** the run ends, **Then** its record exists with no publish attempt, and publish-only later completes it.
5. **Given** the stories the run discovered but did not turn into a video (skipped, failed, or left over once the target was met), **When** the run ends, **Then** they are not in the video history; only videos are recorded, and the run summary carries their counts.
6. **Given** a run in any mode, **When** it ends, **Then** one run summary exists with when it ran, its mode, how many candidates it found, its target, how many videos it produced and scheduled, and how many stories it skipped for each reason; reading it needs no video record, and reading a video record needs no run summary.

---

### User Story 2 - Collect TikTok performance for published videos (Priority: P1)

As the operator, I can ask the system to look at the TikTok account it publishes to, fetch the performance of the videos there (views, likes, comments, shares, saves, and watch-time or completion figures when the account exposes them) and attach each one to the record of the video it came from. I can repeat this whenever I want; each collection is kept as a dated snapshot, so I can see how a video's numbers evolved, and the most recent one is what the crossed view shows.

**Why this priority**: The TikTok side is the other half of the comparison the operator is after. It is P1 alongside the record because the record alone answers no question about performance.

**Independent Test**: Seed a history with a few published videos, point the collection at a fake account source that returns a set of TikTok videos with metrics, run it, and confirm each history record got a snapshot with the right numbers, unmatched TikTok videos were reported, and running it a second time added a second dated snapshot without duplicating the first.

**Acceptance Scenarios**:

1. **Given** a history with videos scheduled on TikTok and an account exposing their metrics, **When** the operator runs the collection, **Then** each of those records gains a dated performance snapshot, and the TikTok video identity is stored on the record so later collections match it directly.
2. **Given** a collection already ran earlier, **When** it runs again, **Then** a new snapshot is added to each matched record and the earlier snapshots are preserved.
3. **Given** a TikTok video that matches no record (for example one posted by hand), **When** the collection runs, **Then** it is listed as unmatched in the collection's report and nothing is attached to any record.
4. **Given** the TikTok account cannot be reached or the session is no longer valid, **When** the collection runs, **Then** it stops with a clear error and the history is left exactly as it was.
5. **Given** two records with the same caption (a story re-published after a failed attempt), **When** the collection cannot tell which one a TikTok video belongs to, **Then** it reports the ambiguity instead of attaching the metrics to either.
6. **Given** a collection runs, **When** it finishes, **Then** every record it touched also has a new dated Reddit snapshot with the post's current upvotes, comment count and upvote ratio, and the discovery snapshot is kept unchanged.

---

### User Story 3 - See the crossed picture in one place (Priority: P2)

As the operator, I can ask for a crossed view of the history: one row per video with the Reddit signals, the model grade, the production settings and the latest TikTok numbers side by side, sortable by any of them and exportable so I can look at it in a spreadsheet. From it I can spot the videos the model graded high that flopped, and the ones it graded low that took off.

**Why this priority**: This is the payoff the operator described. It is P2 only because it is a read of what the two P1 stories store; it can be delivered right after them and without a user interface beyond a command and a file.

**Independent Test**: Seed a history with videos of varied grades and TikTok numbers, ask for the crossed view, and check that every row carries all three groups of information, that sorting by grade and by views works, and that the exported file opens as a table with the same rows.

**Acceptance Scenarios**:

1. **Given** a history with records that have TikTok snapshots, **When** the operator asks for the crossed view, **Then** each row shows the video, its Reddit signals, its grade, its production settings and its latest TikTok metrics, in one table.
2. **Given** a video with no TikTok snapshot yet, **When** the crossed view is produced, **Then** the row is present with the performance columns empty, not omitted.
3. **Given** the crossed view, **When** the operator sorts by model grade and reads down, **Then** high-graded videos with low views, and low-graded videos with high views, are visible without any further processing.
4. **Given** the crossed view, **When** the operator exports it, **Then** the file contains the same rows and columns and can be opened as a table outside the system.

---

### User Story 4 - Tell production strategies apart later (Priority: P2)

As the operator, each record also captures the settings that shaped the video: which version of the editorial prompt wrote the script, which writing model, which grading model, which rendering strategy, which narrator voice and speech rate, the target language, and the hashtags used. When I later change a prompt or try a new strategy, the records made before and after are distinguishable, so the crossed view can compare them.

**Why this priority**: This is what "prepared for future things" means concretely. Comparing strategies later is impossible if the records do not say which strategy produced them, and the information is only available at production time. It is P2 because it is a small addition to the record that must be there from the first day the history exists.

**Independent Test**: Produce a video, change the editorial prompt text, produce another; confirm the two records carry different prompt versions and otherwise identical settings. Change the rendering strategy or the writing model in configuration and confirm the record reflects it.

**Acceptance Scenarios**:

1. **Given** the editorial prompt is edited, **When** the next video is produced, **Then** its record carries a prompt version different from the previous video's, without the operator naming the version anywhere.
2. **Given** the writing model, the rendering strategy or the voice settings change in configuration, **When** a video is produced, **Then** the record reflects the values in effect for that video.
3. **Given** the crossed view, **When** the operator filters by prompt version or by any other setting, **Then** the rows are grouped by the strategy that produced them.

---

### Edge Cases

- A story with N parts produces N records that share the story-level data; TikTok performance is attached per video, since each part is a separate TikTok post.
- Reddit signals are taken at discovery and again at every collection, each as a dated snapshot; the crossed view shows the discovery numbers and the latest ones side by side.
- A Reddit post that was deleted or removed by the time of a collection gets a snapshot marked unavailable; the collection continues with the other records.
- A video produced before this feature existed has only what its manifest and publish-log row contain: title, post link, part, scheduled time, hashtags and outcome. Those are imported once into the history with the missing fields left empty, so that exclusion of already-used posts and the crossed view keep working over the whole account, and no re-grading or re-fetching of Reddit is attempted for them.
- Rows of the publish log that point at test artifacts or at video files that no longer exist are still imported as records of publish attempts; the history does not require the video file to exist.
- A video the collection cannot match to any record is reported, never guessed; a video that matches more than one record is reported as ambiguous. The operator resolves both by hand, by stating which TikTok video belongs to which record, and later collections then match directly.
- A run that finds no candidates or fails before producing anything still leaves a run summary with zero counts and the reason it stopped.
- Repeated collections on the same day add snapshots; the crossed view shows the latest and the history keeps them all.
- The TikTok Studio pages change layout or the session expires mid-collection. The collection fails with the cause and leaves the history unchanged; it is never partially applied.
- The TikTok account exposes different metrics depending on account type and on how old the video is. A metric the account does not expose is left empty in the snapshot; it does not fail the collection.
- A record cannot be written (for example the storage location is not writable). The run fails at that point with the cause, in line with the project's fail-fast principle; the history is not silently skipped.
- Nothing about the process is stored: the model's reasoning, prompt text, intermediate scripts, the agent's browser steps and retries stay out of the history.

## Requirements *(mandatory)*

### Functional Requirements

**Recording**

- **FR-001**: The system MUST create one history record per rendered video during the daily run, in generate-only and full modes, without any operator action.
- **FR-002**: Each record MUST hold the Reddit post's link, community, author, upvotes, comment count, upvote ratio and posting time as observed at discovery.
- **FR-002a**: Every performance collection MUST also re-read each touched record's Reddit post and store its current upvotes, comment count and upvote ratio as a dated snapshot, keeping the discovery snapshot and earlier snapshots; a post that is no longer available is recorded as such.
- **FR-003**: Each record MUST hold the model grade given at discovery: the overall grade, the five component grades (retention, quality, virality, TikTok fit, hook), the verdict and the summary.
- **FR-004**: Each record MUST hold the video facts: title as published, part number and total parts, language, duration, and when it was produced.
- **FR-005**: Each record MUST hold the production settings in effect: a version identifier of the editorial prompt derived from its content, the writing model, the grading model, the rendering strategy, the narrator gender and voice, the speech rate and the hashtags used.
- **FR-006**: Each record MUST hold every publish attempt made for the video: when it was attempted, the scheduled time, the hashtags, the outcome (scheduled or failed) and the error when it failed. A new attempt is added; earlier attempts are kept.
- **FR-007**: The history MUST record outcomes only. Model reasoning, prompt text, intermediate drafts and the publishing agent's step-by-step trace MUST NOT be stored in it.
- **FR-007a**: The system MUST write one run summary per daily run, in every mode: when it ran, the mode, candidates found, target, videos produced, videos scheduled, and stories skipped grouped by reason (content filter, script, render, publish, not needed).
- **FR-007b**: The run summary and the video record MUST be independent entities: the run summary holds counts only and no video data; a video record is complete and readable without any run summary. A video record MAY carry a reference to the run that produced it, and nothing else ties the two together.

**TikTok performance**

- **FR-008**: The operator MUST be able to run a collection that reads the performance of the videos on the TikTok account the system publishes to, from the command line and from the Telegram bot, like the daily run.
- **FR-009**: A performance snapshot MUST hold the collection time and, where the account exposes them, views, likes, comments, shares, saves, average watch time and completion rate. Metrics the account does not expose are left empty.
- **FR-010**: The collection MUST match each TikTok video to its history record using the caption the system published and the scheduled time, store the TikTok video identity on the record once matched, and use that identity for later collections.
- **FR-011**: The collection MUST report TikTok videos that match no record and videos that match more than one, and MUST NOT attach metrics in either case.
- **FR-012**: The operator MUST be able to resolve an unmatched or ambiguous video by stating which record it belongs to.
- **FR-013**: Every collection MUST add a dated snapshot to each matched record and preserve earlier snapshots.
- **FR-014**: A collection that cannot reach the account or read its videos MUST fail with the cause and leave the history unchanged.

**Crossed view**

- **FR-015**: The operator MUST be able to obtain a crossed view with one row per video carrying the Reddit signals at discovery and their latest snapshot, the model grade, the production settings and the latest performance snapshot, including videos with no snapshot yet.
- **FR-016**: The crossed view MUST be sortable and filterable by any of its columns, including prompt version and the other production settings, and exportable to a file that opens as a table.

**Continuity and preparation**

- **FR-017**: The existing manifests and publish-log rows MUST be imported once into the history, with the fields they lack left empty, so the whole account's publishing history is in one place.
- **FR-018**: Exclusion of posts already scheduled, publish-only mode and the daily run's observable behaviour MUST remain as they are today; the existing automated check of the daily run's behaviour keeps passing unchanged.
- **FR-019**: The history MUST be read and written only through the project's storage boundary and kept in a single-file embedded database, so that it can be moved to a server database later without touching the daily run, the collection or the crossed view. The manifests and the publish log MUST keep being written as today, alongside the history.
- **FR-020**: The source of TikTok performance MUST sit behind its own contract. The implementation in this feature reads TikTok Studio with the account session the server already holds; other ways of obtaining metrics (an export file, an official interface) MUST be addable without touching the collection, the matching or the history.
- **FR-021**: Adding a new metric, a new production setting or a new performance source MUST NOT require changes to the daily run.

### Key Entities

- **Video record**: the durable memory of one rendered video. Holds the video facts, references the source post signals, the model grade and the production settings it was made with, and owns its publish attempts and performance snapshots. Parts of one story are separate records sharing the story-level data.
- **Source post signals**: the Reddit post's link, community, author and posting time, plus dated snapshots of its upvotes, comment count and upvote ratio: one at discovery and one per collection. A record may have several, ordered by time.
- **Model grade**: the grade the discovery model gave the story: overall grade, five component grades, verdict, summary, and the grading model.
- **Production settings**: the strategy fingerprint of a video: prompt version, writing model, rendering strategy, narrator gender and voice, speech rate, language, hashtags.
- **Publish attempt**: one try at scheduling a video on TikTok: attempted time, scheduled time, hashtags, outcome, error. A record may have several.
- **Performance snapshot**: the TikTok metrics of one video at one collection time, with the TikTok video identity that links them. A record may have several, ordered by time.
- **Run summary**: the outcome of one daily run: when it ran, its mode, candidates found, target, videos produced, videos scheduled, stories skipped by reason. Independent of the video records; holds no video data.
- **Collection report**: the outcome of one collection: how many records were matched, and which TikTok videos were unmatched or ambiguous.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After any daily run, a run summary exists and 100% of the videos it rendered have a record with the Reddit signals, the model grade, the production settings and, when it published, the publish attempt, with no operator action.
- **SC-002**: At least 95% of the videos the system scheduled on TikTok are matched to their performance automatically by a collection; the remainder are listed for the operator to resolve, and none is attached to the wrong record.
- **SC-003**: From the crossed view alone, without opening files or TikTok, the operator can list the ten highest-graded videos with the fewest views and the ten lowest-graded videos with the most views in under two minutes.
- **SC-004**: Producing the crossed view for the whole history takes under ten seconds, excluding time spent fetching from TikTok.
- **SC-005**: Two videos produced with different editorial prompts are distinguishable in the crossed view by their prompt version in every case.
- **SC-006**: The existing automated check of the daily run's behaviour passes unchanged after the feature; exclusion of already-scheduled posts and publish-only mode behave as before.
- **SC-007**: Nothing from the process is in the history: a review of a record shows no model reasoning, no prompt text and no agent trace.

## Assumptions

- The TikTok performance comes from the same account the system publishes to. The first and only source in this feature reads the TikTok Studio analytics pages with the logged-in session the server already holds, through deterministic automated page reading, not through the AI browsing agent used for publishing. An export-file import or the official interface can be added later behind the same contract. The metrics promised are the ones TikTok Studio exposes for the account.
- TikTok does not hand back a post identity at scheduling time, so the first match between a TikTok video and a record is made on the published caption and the scheduled time; the identity is stored once matched. Putting an identifying marker in every caption would make the match exact but would change what the audience sees, so it was rejected; the captions the system publishes stay exactly as they are today.
- Reddit signals are captured at discovery and refreshed at every collection, because a post picked from the morning's top is still growing then and "doing well on Reddit" should reflect where it ended up. The refresh reuses the post reading the discovery already does.
- The model grade is the existing 0 to 100 overall grade with its five component grades; the operator's "rated 9" corresponds to that scale.
- The prompt version is derived from the prompt's content, so editing the prompt changes the version without the operator naming it.
- The history lives behind the existing storage boundary in a single-file embedded database (SQLite): no server, one file to back up, and sorting, filtering and crossing come from the database rather than from code. Manifests and the CSV publish log keep being written as today; folding them into the database is future work. A web view is an explicit future goal and is out of scope, as is any automatic tuning of prompts or strategies.
- The crossed view is a command that prints a table and exports a file; no user interface beyond that is expected in this feature.
- The collection is run on demand; scheduling it (for example daily after the run) is a small adapter decision that may be added without changing the collection itself.
- The one-time import of existing manifests and publish-log rows uses the server's files, which hold the real history; the copy on the laptop contains mostly test rows.

# Feature Specification: Local Story Preparation and Server Hand-off

**Feature Branch**: `003-local-story-prep`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "I want ideas to run subscription here with good models, my idea is not use my subscriptions as apis, is to manually run histories and the api will no need to run it. Like a hybrid behaviour, if nothing is done it should leave as it is today, otherwise I can run a prompt in my machine to fetch histories, choose one and prepare the script to be used, ship those informations to server and it will use it directly instead of running his own AI. First, the first steps should be local then the server: first an e2e to find histories, generate the text and the audio, to be easier to see, and a way to send to the server. I want this first because I will access the server only in 3 days."

## Context

Today the production server runs a fully automatic daily pipeline: it discovers candidate Reddit stories, asks a paid API model to grade them, asks another paid API model to write the narration script, then synthesizes the narration, builds the video and schedules it on TikTok. The operator only sees the result after the fact.

The operator has an interactive AI assistant on their own machine, paid by subscription, whose writing they prefer over the API models the server uses. That assistant cannot be called by the server, but the operator can drive it by hand. The goal is a hybrid workflow: the operator can, whenever they choose, do the creative part locally (find stories, pick one, write the script, listen to the narration) and hand the finished result to the server, which then skips its own AI steps and goes straight to producing and publishing the video. When the operator does nothing, the server behaves exactly as it does today.

Delivery is split in two, in this order, because the operator will not have access to the server for the next three days:

1. **Local first**: an end-to-end local flow the operator can run and inspect now: find stories, write the script, hear the narration, and package the result together with a way to send it to the server.
2. **Server second**: the daily run consumes any packages the operator has sent before falling back to automatic discovery.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find and choose stories locally (Priority: P1)

As the operator, I run one command on my machine and get a ranked shortlist of today's candidate stories from the configured communities, with enough information (title, community, engagement, length, source link) to pick one or more without opening Reddit and without spending paid API credits.

**Why this priority**: Everything else starts from a chosen story. Without a local shortlist the operator would have to browse Reddit by hand, which defeats the purpose of the flow.

**Independent Test**: Run the discovery command with the production community list and confirm a ranked shortlist is printed and saved, with no calls to any paid model.

**Acceptance Scenarios**:

1. **Given** the configured community list, **When** the operator runs discovery, **Then** they receive a ranked shortlist of candidates showing title, community, score, comment count, text length and the source link.
2. **Given** discovery has run, **When** the operator asks for a candidate by its position in the shortlist, **Then** the full original text of that story is available locally for reading and for the next step.
3. **Given** discovery runs, **When** it finishes, **Then** no paid model was called; ranking relies only on locally computed signals and on the operator's own assistant.
4. **Given** one community cannot be fetched, **When** discovery runs, **Then** the remaining communities are still listed and the failure is reported, matching today's server behavior.

---

### User Story 2 - Write the script with my own assistant (Priority: P1)

As the operator, I hand a chosen story to my interactive assistant and get back a narration script and a cover title that follow the same editorial rules the server uses today (spoken hook first, title not narrated, name anonymization, forbidden word families, closing question and call to action). I can ask for revisions until I am happy, and the result is saved as a self-contained "prepared story" package.

**Why this priority**: This is the step where the subscription model replaces the API model, which is the whole reason for the feature. It is also the step the server will later consume.

**Independent Test**: Take one candidate from the shortlist, produce a package with the assistant, and validate it: the package passes the editorial checks and contains everything the server needs to build the video with no further AI work.

**Acceptance Scenarios**:

1. **Given** a chosen candidate, **When** the operator asks the assistant to write the script, **Then** the assistant applies the same editorial rules the server's script prompt applies, taken from a single shared source so the two cannot drift apart.
2. **Given** a draft script, **When** the operator gives feedback (shorter, different hook, other name), **Then** a revised draft is produced and the previous one is replaced only when the operator accepts it.
3. **Given** an accepted script, **When** the operator saves it, **Then** a package file exists containing the original post details needed for the cover, the cover title, the narration script, the narrator gender, a short summary, the target language and the source link.
4. **Given** a package file, **When** the operator validates it, **Then** missing fields, an empty script, or any forbidden word in the title or script are reported with the offending text, and the validation fails.
5. **Given** a package that passes validation, **When** the operator lists local packages, **Then** it appears with its title, source and creation time.

---

### User Story 3 - Hear the narration before sending (Priority: P2)

As the operator, I can generate the narration audio for a package on my machine and listen to it, so I can judge pacing, hook strength and pronunciation of names before the story leaves my machine.

**Why this priority**: Audio is the fastest honest preview of the final product; it catches problems (awkward hook, mispronounced names, wrong gender voice) that reading the text does not. Rendering the full video locally is not needed for that judgment and is much slower.

**Independent Test**: Generate audio from a validated package and confirm an audio file is produced next to the package using the same voice, gender and speed the server would use.

**Acceptance Scenarios**:

1. **Given** a validated package, **When** the operator asks for a preview, **Then** a narration audio file is produced next to the package using the narrator gender and narration speed configured for production.
2. **Given** the operator changes the script after listening, **When** they ask for a preview again, **Then** the audio is regenerated from the new script and the old audio is replaced.
3. **Given** the preview is generated, **When** the operator inspects the output, **Then** the audio duration is reported so the operator can tell whether the story is too long or too short.

---

### User Story 4 - Send prepared stories to the server (Priority: P2)

As the operator, I run one command to send one or more validated packages to the server's queue, and I can see which packages are waiting there.

**Why this priority**: Without a hand-off the local work never reaches production. It is a small step but it is the bridge between the two halves of the feature. It only requires the server to be reachable, not changed, so it can be verified as soon as the operator regains access.

**Independent Test**: Send a validated package and confirm it is present, unchanged, in the server's queue location; then list the queue from the local machine and see it.

**Acceptance Scenarios**:

1. **Given** a validated package, **When** the operator sends it, **Then** it is copied to the server's queue and the operator is told it arrived.
2. **Given** a package that fails validation, **When** the operator tries to send it, **Then** sending is refused and the validation errors are shown.
3. **Given** packages already in the server queue, **When** the operator lists the queue, **Then** they see each queued package's title, source link and queue time.
4. **Given** a package with the same source link already in the queue, **When** the operator sends it again, **Then** the operator is warned and the queued copy is replaced only on explicit confirmation.
5. **Given** the server is unreachable, **When** the operator sends a package, **Then** the local package is left intact and the failure is reported clearly.

---

### User Story 5 - Server uses prepared stories first (Priority: P3)

As the operator, when the daily run starts and there are prepared stories waiting in the queue, the server produces and schedules videos from those stories, in the order they were queued, without running its own discovery or script generation for them. When the queue is empty the run behaves exactly as today.

**Why this priority**: This closes the loop, but it lives on the server, which the operator cannot reach for three days. It is intentionally last.

**Independent Test**: Place one prepared story in the queue and trigger the daily run in generate-only mode: the produced video must use the prepared title and script verbatim, with no discovery and no script model call for it. Then empty the queue and trigger again: behavior is identical to the current pipeline.

**Acceptance Scenarios**:

1. **Given** an empty queue, **When** the daily run starts, **Then** it discovers, writes, produces and publishes exactly as it does today.
2. **Given** N prepared stories in the queue and a daily target of N, **When** the daily run starts, **Then** it produces and schedules those N stories in queue order, and no story model or grading model is called.
3. **Given** fewer prepared stories than the daily target, **When** the daily run starts, **Then** the prepared ones are produced first and the remaining slots are filled by automatic discovery, unless the operator has configured the run to use prepared stories only.
4. **Given** a prepared story was produced and scheduled, **When** the run finishes, **Then** that package is moved out of the queue into a "done" area with the publish outcome recorded.
5. **Given** a prepared story fails at production or publishing, **When** the run continues, **Then** the package is moved into a "failed" area with the error recorded, and the run moves on to the next candidate as it does today.
6. **Given** a story already prepared, queued, done or previously published, **When** automatic discovery runs, **Then** that story is not selected again.
7. **Given** a prepared story carries its own hashtags, **When** it is published, **Then** those hashtags are used and no hashtag model call is made; otherwise hashtags are generated as today.

---

### Edge Cases

- A queued package was written for a different language than the server's configured language: the server refuses that package with a clear error and moves it to "failed" rather than producing a mismatched video.
- A package sits in the queue for many days: it is still valid and is consumed in order; there is no expiry in this version.
- The operator sends a package while the daily run is in progress: the run keeps its already-loaded candidate list; the new package is picked up by the next run.
- The prepared script contains a forbidden word that slipped past local validation: production still applies the same on-screen censoring it applies today, so the video is not blocked, but the operator should have seen it locally.
- The queue directory does not exist yet on the server: it is created on first use, both by the sending command and by the daily run.
- Discovery locally finds no candidates above the minimum length: the shortlist is empty and says so; nothing else happens.
- The operator's machine lacks the Reddit credentials the server uses: discovery fails immediately with a message naming the missing credentials.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The operator MUST be able to produce, on their own machine, a ranked shortlist of candidate stories from the configured communities without calling any paid model.
- **FR-002**: The shortlist MUST show, per candidate, title, community, score, comment count, text length and source link, and MUST make the full original text available locally on request.
- **FR-003**: The editorial rules used to write a script (hook, title handling, anonymization, forbidden words, closing call to action) MUST come from a single shared source used by both the server's script generation and the local assistant flow.
- **FR-004**: The local flow MUST produce a self-contained prepared-story package holding: original post details needed for the cover (title, community, author, community image), cover title, narration script, narrator gender, resolved voice gender, short summary, target language, source link, creation time, and optional hashtags.
- **FR-005**: The operator MUST be able to validate a package locally; validation MUST fail on missing fields, empty script, language mismatch with the target configuration, or forbidden words in title or script, and MUST name the offending text.
- **FR-006**: The operator MUST be able to generate narration audio from a package locally using the production voice settings (gender, speed), and MUST be told the resulting duration.
- **FR-007**: The operator MUST be able to send one or more validated packages to the server queue with a single command, and MUST be refused for packages that fail validation.
- **FR-008**: The operator MUST be able to list the server queue from their machine.
- **FR-009**: Sending a package whose source link is already queued MUST warn and require explicit confirmation before replacing it.
- **FR-010**: The daily run MUST consume queued packages, in queue order, before any automatic discovery, and MUST NOT call the grading, script or hashtag models for a package that already carries the corresponding data.
- **FR-011**: When the queue is empty the daily run MUST behave exactly as it does today, with no configuration change required.
- **FR-012**: When the queue holds fewer packages than the daily target, the daily run MUST fill the remaining slots by automatic discovery by default; the operator MUST be able to configure the run to use prepared stories only.
- **FR-013**: After a package is produced and scheduled it MUST be moved out of the queue into a "done" area; after a failure it MUST be moved into a "failed" area with the error recorded.
- **FR-014**: Automatic discovery MUST skip stories whose source link is queued, done, or already present in the publish history.
- **FR-015**: Deploying the application to the server MUST NOT delete or alter queued, done or failed packages.
- **FR-016**: Every produced video MUST record in its manifest whether its story came from a prepared package or from automatic generation.

### Key Entities

- **Candidate**: a Reddit post found by discovery, with its engagement signals, length, community and source link; the input to the operator's choice.
- **Prepared Story Package**: the operator-approved, self-contained result of the local flow; carries everything needed to produce and publish one video with no further AI work. Identified by its source link.
- **Queue**: the server-side holding area for packages awaiting the daily run, with sibling "done" and "failed" areas that record the outcome of each consumed package.
- **Daily Run**: the existing server pipeline; extended to draw from the Queue first and from discovery second.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The operator can go from "run discovery" to "validated package with audio preview" for one story in under 15 minutes of wall-clock time, excluding time spent reading and editing.
- **SC-002**: A local run of discovery, script writing, validation and audio preview generates zero paid-model API calls.
- **SC-003**: With the queue empty, the daily run's log and outputs are indistinguishable from the pipeline before this feature.
- **SC-004**: With the queue holding as many packages as the daily target, the daily run makes zero story-grading and zero script-writing model calls.
- **SC-005**: A video produced from a prepared package carries the package's cover title and narration script verbatim.
- **SC-006**: The same story is never published twice through the two paths combined.
- **SC-007**: The local half (User Stories 1 to 4) can be exercised end to end, including the send step against any reachable host, without any change deployed to the server.

## Assumptions

- The operator's interactive assistant on their machine is driven by hand; it is never called programmatically by the server. The subscription is never used as an API.
- The local machine already holds the Reddit credentials used by the server, so discovery can reuse the same fetching logic.
- Local discovery ranks with the existing locally computed signals; grading by a paid model is skipped locally and replaced by the operator's assistant reading the shortlist. The operator accepts a less refined shortlist in exchange for zero API cost.
- The audio preview uses the free narration engine the production server already uses, at the production speed, so what the operator hears matches what will be published.
- Rendering the full video locally is out of scope for the preview; the existing local generation scripts remain available for that.
- Sending packages uses the existing remote-access path the deploy tooling already relies on; no new service or endpoint is introduced on the server. Receiving packages through the Telegram bot is a possible later addition, not part of this feature.
- Queue order is first in, first out; there is no expiry, priority or editing of queued packages in this version.
- When the queue holds fewer packages than the daily target, filling the remainder by automatic discovery is the default, so the daily publishing volume stays stable; the operator can turn this off.
- The daily target and publish slots are unchanged; prepared stories simply take the first slots.
- Prepared stories are produced with the server's current narration and video settings; the package does not carry per-story overrides for speed, voice or background.

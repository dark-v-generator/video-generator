# Feature Specification: Isolated Pipeline Capabilities and Thin Business Flows

**Feature Branch**: `004-clean-architecture-refactor`

**Created**: 2026-09-25

**Updated**: 2026-09-25 (scope narrowed to the daily publishing run; local preparation, queue and two-part format removed)

**Status**: Draft

**Input**: User description: "Today we have some dificulties to adapt the flow to different kinds of histories, adapt part 1 and 2, do the history locally and upload it, its not very easy to do, I want to be able to isolate parts of the application in a way changes will be easier to adapt, like clean archtecture. The idea is the part of selection reddit history to be isolated, the part of transform the link into an IA history isolated, the part of download videos from youtube, the video generation should be isolated receiving any video or any history for example, and the flows to be just the business part that uses all those isolated parts. I want to refact the application thinking of this, because in the future I want to explore changes without the dificulties of adapt what we have. Some example of future changes that might come: put database on the application and put a web application behind all this, so I can see things visually; adapt the prompt of the histories to be easier to change them; create part 1, part 2 part N videos; change the video generation to an animation or sequence of IA generated images for example. The application should have moving parts that should support this, with everythings as almost a lib that does something with interface etc, and the business logic to be the part that really is changed or throw away or adapted"

**Clarification (2026-09-25)**: the operator confirmed that the only behavior worth preserving is the daily video publishing that runs in production today. The local story preparation flow with its server queue, the two-part story format, the image-story pipeline and the interactive bot may all be deleted in this refactor; two-part stories and local preparation may be rebuilt later on top of the new boundaries.

## Context

The application turns Reddit stories into narrated vertical videos and schedules them on TikTok. Over three features it grew a daily automatic run, a local "prepare the story on the laptop" flow with a server-side queue, and a two-part story format. Each of those was harder to add than it should have been, for the same reason: the steps of the pipeline are not separable.

Today one large service knows how to scrape a post, ask a model for a script, synthesize narration, transcribe captions, draw a cover and compose the video, in one or two parts, over YouTube footage or over generated images. The daily run lives inside the Telegram bot module together with queue handling, discovery, scheduling, manifests and the publish log, and the command-line entry point imports the bot to run it. The story format "one video" and "two videos" are two distinct code paths. The editorial prompts sit next to the model client. As a result:

- Telling a story in a new shape (a different number of parts, a different source than Reddit) means touching the service, the bot and the storage at once.
- Preparing a story locally required re-deriving, from inside the service, the exact point after which no model is needed, and exporting it by hand.
- Any tool that only needs one step (rank candidates, render a prompt) drags the whole video stack with it.

The operator wants the application reorganized around a small set of independent capabilities, each usable on its own like a small library with a clear contract, and a thin layer of business flows that merely combine them. The flows are the part that is expected to change, be rewritten or be thrown away; the capabilities are the part that is expected to stay stable and be reused. Anticipated changes that this reorganization must make cheap, without implementing them now: storing state in a database and putting a web interface over it, editing the editorial prompts easily, producing stories in N parts, and replacing the YouTube-footage rendering with an animation or a sequence of AI-generated images.

To keep the refactor small, everything that is not the daily publishing run is removed rather than carried over. The daily run is the only flow whose behavior must be equivalent before and after.

## User Scenarios & Testing *(mandatory)*

The actor in every story is the operator, who is also the sole maintainer. "Change" below means a code or configuration change made by the operator.

### User Story 1 - Render a video from any story and any footage (Priority: P1)

As the operator, I can hand the video rendering capability a story (a title, one or more narration parts, the narrator voice, the language) and a footage source, and get back the finished video artifacts, without the rendering capability knowing where the story came from or how the footage was obtained.

**Why this priority**: Rendering is the most expensive and most coupled step, and it is the one the operator most wants to replace (animation, AI image sequences). Once it accepts any story and any footage, every other change becomes local.

**Independent Test**: Write a story by hand in a test, point the renderer at a local video file as footage, and get a video, its captions, its cover and its narration audio, with no network access and no model call.

**Acceptance Scenarios**:

1. **Given** a story with one part and a footage source, **When** the operator asks for a render, **Then** one video is produced with the same narration, captions, cover, call-to-action timing and anti-fingerprint treatment the daily run produces today.
2. **Given** a footage source that serves a local file instead of YouTube footage, **When** the operator asks for a render, **Then** the render succeeds and no YouTube access is attempted.
3. **Given** a rendering strategy other than "narration over footage" is registered, **When** a flow selects it for a story, **Then** the flow code that produced the story does not change.
4. **Given** a story with more than one part, **When** the operator asks for a render, **Then** one video per part is produced through the same rendering path as the one-part case, each cover carrying its part label.

---

### User Story 2 - Write a story from any text with prompts kept in one editable place (Priority: P1)

As the operator, I can hand the story writing capability a source text (title, body, origin link) and a target language, and receive a story ready to narrate. The editorial prompts that drive the writing live in a single place and are edited without touching code.

**Why this priority**: This is the step whose rules change most often (hooks, anonymization, forbidden words). It must also be swappable, so that a story written by the operator or by another tool can enter the pipeline through the same contract later.

**Independent Test**: Edit the editorial prompt, run the writer with a fake model and confirm it received the new text; then substitute a writer that returns a pre-written story and confirm the rest of the flow proceeds unchanged.

**Acceptance Scenarios**:

1. **Given** a source text, **When** the writer runs, **Then** it returns a story with a title, one narration part, a narrator gender and a summary, equivalent to what the daily run gets today.
2. **Given** an edited prompt file, **When** the writer runs, **Then** it uses the edited text with no code change.
3. **Given** a writer that returns an already-written story, **When** a flow needs a story, **Then** the flow obtains it through the same contract a model-written story uses, and no model is called.
4. **Given** a prompt file with a rendering error, **When** the capability is first used, **Then** it fails immediately naming the prompt, instead of failing midway through a daily run.

---

### User Story 3 - The daily run becomes a thin business flow (Priority: P1)

As the operator, I can read the daily run as a short sequence of decisions and capability calls (discover candidates, get a story, render it, schedule it, record the outcome) that contains no Telegram, terminal, file-layout or model-client specifics, and that behaves exactly as it does today in its three modes: full run, generate only, and publish only from a directory.

**Why this priority**: The flow is the part the operator expects to rewrite or throw away. It cannot be cheap to change while it carries the delivery channel and the storage details inside it. This story is the payoff of the previous two and the only behavior-preservation target of the feature.

**Independent Test**: Run the daily flow in generate-only mode against fakes for every capability and compare the produced artifact set and manifests with today's; run it once from the Telegram command and once from the command line and get the same result.

**Acceptance Scenarios**:

1. **Given** the same discovered candidates, **When** the daily run executes before and after the refactor, **Then** the videos, manifests and publish log rows are equivalent.
2. **Given** the Telegram bot, its daily schedule and the command-line entry point, **When** each triggers the daily run, **Then** all invoke the same flow and differ only in how progress messages are delivered.
3. **Given** a flow reads top to bottom, **When** the operator looks for where a business decision is made (how many stories per day, retry and skip policy, which publish slot comes next), **Then** that decision is in the flow, not inside a capability.
4. **Given** videos generated earlier, **When** the operator runs publish-only on their directory, **Then** they are scheduled as today, including manifests written before the refactor.
5. **Given** a run already in progress, **When** a second run is triggered, **Then** it is refused, as today.

---

### User Story 4 - Discover and select stories in isolation (Priority: P2)

As the operator, I can ask the discovery capability for ranked candidate stories from a set of communities, excluding links I already used, and receive them with their signals, from any entry point (bot, command line, a future web page), without loading the writing or rendering capabilities.

**Why this priority**: Discovery is already mostly separate; this story finishes the job so the selection step can later move to a web page or a database-backed history without touching anything else.

**Independent Test**: Call discovery with a fake Reddit source and an exclusion list, and get ranked candidates; confirm the rendering and writing capabilities were never loaded.

**Acceptance Scenarios**:

1. **Given** a list of communities and an exclusion list, **When** discovery runs, **Then** it returns ranked candidates with title, community, score, comment count, length and link, as today.
2. **Given** one community fails to load, **When** discovery runs, **Then** the other communities are still ranked and the failure is reported, as today.
3. **Given** the optional model-based grading, **When** a flow asks for it, **Then** it is applied on top of the ranked candidates; when a flow does not ask, no model is called.

---

### User Story 5 - Obtain background footage in isolation (Priority: P2)

As the operator, I can ask the footage capability for a background of a given duration and receive it, whether it comes from YouTube downloads, from a local cache, or from another source registered later, without the caller knowing which.

**Why this priority**: Footage sourcing carries its own failure modes (YouTube unreachable, cache-only mode, rate limits) and its own protections (anti-fingerprint). Isolating it lets the renderer accept "any video" and lets a future renderer skip footage altogether.

**Independent Test**: Request footage of a given duration with a footage source backed by local files; confirm the returned material covers the duration and no network was used. Then request with YouTube unreachable and a warm cache and confirm today's cache-only behavior.

**Acceptance Scenarios**:

1. **Given** the configured channels and a duration, **When** footage is requested, **Then** a compilation covering that duration is returned with the same selection, download and rate-limit behavior as today.
2. **Given** YouTube is unreachable and the cache holds enough material, **When** footage is requested, **Then** the request is served from the cache, as today.
3. **Given** a footage source that reads a local folder, **When** it is configured, **Then** the renderer uses it with no change to the renderer or to the flow.

---

### User Story 6 - A story has N parts, and one part is just a case of N (Priority: P3)

As the operator, I model every story as an ordered list of parts. Rendering, scheduling and publish history treat the list generically, so bringing back two-part stories, or adding three-part ones, later needs only a prompt and a flow decision, not changes in the capabilities.

**Why this priority**: "Part 1, part 2, part N" is an explicitly requested future change, and the two-part code that exists today is being deleted. Making the shared model generic now costs little and avoids rebuilding the duplicated paths when the format returns.

**Independent Test**: In a test, feed a three-part story to the renderer and to the scheduling logic and get three videos scheduled in consecutive slots, with no change to rendering, scheduling or publishing code. Production keeps producing one-part stories only.

**Acceptance Scenarios**:

1. **Given** a story with N parts, **When** it is rendered, **Then** N videos are produced with part labels on the covers when N is greater than one, and no label when N is one.
2. **Given** a story with N parts, **When** it is scheduled, **Then** its parts occupy N consecutive publish slots and count as one story toward the daily target.
3. **Given** a failure producing any part, **When** the flow continues, **Then** none of the parts is published and the story is recorded as failed.
4. **Given** the daily run in production, **When** it writes stories, **Then** it produces one-part stories only, as today.

---

### User Story 7 - State lives behind a storage boundary (Priority: P3)

As the operator, everything the flow remembers between runs (produced-video manifests, the publish history, discovered candidates) is read and written through a storage boundary whose file-based implementation is the one used today, so a database can replace it later without touching flows or capabilities.

**Why this priority**: A database and a web view are explicit future goals. They are only cheap if the flow never touches files directly. This story does not add the database; it only makes the seam.

**Independent Test**: Run the daily flow against an in-memory storage implementation in tests and get the same outcomes; run it against the file implementation and get today's files in today's locations.

**Acceptance Scenarios**:

1. **Given** the file-based storage, **When** the flow runs, **Then** it produces the same files, in the same locations and formats, as today.
2. **Given** an alternative storage implementation, **When** it is configured, **Then** the flow and capabilities run unchanged.
3. **Given** a question the future web view would need (what was produced, what was published and when, what failed and why), **When** the operator asks the storage boundary, **Then** the answer is available without callers parsing files.

---

### User Story 8 - Everything outside the daily run is removed (Priority: P2)

As the operator, the code, configuration, commands, documentation and tests that only serve the local preparation flow, the server queue, the two-part story format, the image-story pipeline, the interactive bot and the dead web entry point are deleted, so the refactor has one target and the repository only contains what production uses.

**Why this priority**: The operator chose to drop these rather than carry them through the refactor. Leaving them half-migrated would double the work and blur the boundaries. It is P2 because the deletion is cheap but should happen before the extraction so the remaining code is smaller to move.

**Independent Test**: After removal, the repository has no command, recipe, bot handler, configuration setting, skill or document that refers to prepared stories, the queue, two-part stories, image stories or the interactive bot, and the daily run still passes its equivalence check.

**Acceptance Scenarios**:

1. **Given** the removal is done, **When** the operator lists the task-runner recipes, commands and bot handlers, **Then** only those serving the daily run, its publish modes, deployment and the TikTok session tooling remain.
2. **Given** the removal is done, **When** the daily run starts on the server, **Then** it ignores any leftover queue directory and behaves as an empty-queue run did before.
3. **Given** the removal is done, **When** the automated tests run, **Then** tests of removed behavior are gone and every remaining test passes.

---

### Edge Cases

- Manifests of videos generated before the refactor are still loadable by the publish-only mode.
- The existing configuration files keep working without edits; settings of removed features are ignored, and any renamed or moved setting is read from its old location or the change is documented with the release.
- A prompt file that fails to render is reported at the first use of the writing capability, naming the file, not in the middle of a daily run.
- A footage source that cannot supply the requested duration fails immediately with the shortfall, rather than producing a shorter video.
- Two entry points running the daily flow at the same time keep today's protection: a second run is refused while one is in progress.
- A rendering strategy registered but not fully configured fails at selection time with the missing setting named, not after narration and captions were generated.
- A leftover queue directory on the server, with packages sent before the removal, is not read; those stories are not published and are not excluded from discovery.
- Entry points that are already non-functional today (the web server entry point refers to a module that no longer exists) are deleted, not preserved.

## Requirements *(mandatory)*

### Functional Requirements

**Capabilities**

- **FR-001**: The system MUST expose story discovery as a self-contained capability that, given communities and exclusions, returns ranked candidates, with model-based grading as an optional step the caller requests.
- **FR-002**: The system MUST expose story writing as a self-contained capability that, given a source text and a language, returns a story; a model-backed writer and a writer that returns a pre-written story MUST satisfy the same contract.
- **FR-003**: The editorial prompts MUST live in one place and be editable without code changes.
- **FR-004**: The system MUST expose footage sourcing as a self-contained capability that, given a duration, returns background footage, with YouTube-plus-cache as the default source and room for other sources.
- **FR-005**: The system MUST expose video rendering as a self-contained capability that accepts any story and any footage source and returns the video artifacts (video, narration audio, captions, cover) for each part.
- **FR-006**: The rendering capability MUST allow more than one rendering strategy to coexist, selected per story by the flow, with "narration over footage" as the strategy that reproduces today's output.
- **FR-007**: Publishing MUST be reachable by the flow only through its existing contract (video, description, hashtags, schedule time), with scheduling-slot arithmetic kept out of the publisher.
- **FR-008**: Each capability MUST be usable without loading the others; in particular, discovery MUST run without loading the video-editing stack.

**Story model**

- **FR-009**: A story MUST be represented as a title, an ordered list of one or more narration parts, a narrator gender, a resolved voice, a language, a summary, an origin reference and optional hashtags.
- **FR-010**: Rendering, scheduling and publish history MUST treat the part list generically; the one-part story produced today MUST be a case of the generic model, not a dedicated path.

**Flow**

- **FR-011**: The daily run MUST be a business flow that only combines capabilities and storage and contains no delivery-channel (Telegram, terminal), file-layout or model-client specifics.
- **FR-012**: The Telegram bot (its command and its daily schedule) and the command-line entry point MUST all invoke the same daily flow, providing only the progress-reporting channel.
- **FR-013**: The daily flow MUST keep its three modes: full run, generate only, and publish only from a directory.
- **FR-014**: Business decisions (daily target, retry and skip policies, next publish slot, N parts are all or nothing) MUST be located in the flow, not inside capabilities.

**Storage**

- **FR-015**: Produced-video manifests, the publish history and discovered candidates MUST be accessed through a storage boundary; the file-based implementation MUST produce today's files in today's locations and formats.
- **FR-016**: The storage boundary MUST answer the questions a future visual interface needs (what was produced, what was published and when, what failed and why) without callers parsing files.

**Preservation**

- **FR-017**: The daily run, in all three modes and from all its entry points, is the only flow that MUST be preserved; its observable outputs (artifacts, manifests, publish log rows, operator-facing messages) MUST be equivalent before and after the refactor.
- **FR-018**: Existing configuration files MUST keep working; settings that move MUST either be read from their previous location or be documented as a required edit, and settings of removed features MUST be ignored.
- **FR-019**: Manifests written before the refactor MUST remain loadable by the publish-only mode.

**Removal**

- **FR-020**: The local story preparation flow, its command-line tool, its assistant skill, its task-runner recipes, its documentation and the server-side queue MUST be removed.
- **FR-021**: The two-part story format MUST be removed from production paths: its prompt, its package shape, its dedicated pipeline and its command.
- **FR-022**: The image-story pipeline, its command and its bot, the interactive bot, and the non-functional web entry point MUST be removed.
- **FR-023**: Tests, documentation and configuration settings that only serve removed behavior MUST be removed with it.

### Key Entities

- **Story**: what gets narrated; a title, an ordered list of narration parts, narrator gender and resolved voice, language, summary, origin reference, optional hashtags. Produced by a writer, consumed by a renderer and a scheduler. Independent of Reddit and of any model.
- **Source Text**: the raw material a writer starts from; today a Reddit post (title, body, community, author, link). The origin reference on a Story points back to it.
- **Candidate**: a Source Text plus the ranking signals discovery computed for it; the unit of selection.
- **Footage**: background material of a known duration, from any source, handed to the renderer.
- **Rendered Part**: the artifacts for one part of a story: video, narration audio, captions, cover, part index.
- **Rendering Strategy**: a named way to turn a Story into Rendered Parts; today "narration over footage", later animation or image sequences.
- **Flow**: a business procedure that combines capabilities and storage into an outcome; today only the daily run. Expected to change often.
- **Capability**: a stable, independently usable unit with a contract: discovery, writing, footage, rendering, publishing.
- **Store**: the boundary through which the flow remembers state between runs: manifests, publish history, candidates.
- **Prompt**: an editable editorial instruction to the writer, kept in one place.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the daily run, a fixed set of inputs produces an equivalent set of artifacts, manifests and publish log rows before and after the refactor, verified by an automated comparison.
- **SC-002**: The complete daily flow runs in the automated test suite with no network access and no model call, using substitutes for every capability.
- **SC-003**: Editing an editorial prompt requires changing exactly one file and zero code.
- **SC-004**: A three-part story renders as three videos and is scheduled in three consecutive slots in a test that changes zero files in the rendering, scheduling or publishing capabilities.
- **SC-005**: Registering an alternative rendering strategy or an alternative footage source touches zero files in discovery, writing, storage or the flow.
- **SC-006**: Replacing the file-based store with an in-memory one in tests touches zero files in the flow or capabilities.
- **SC-007**: Discovery starts in under 2 seconds and without loading the video-editing stack.
- **SC-008**: A new flow that renders a hand-written story over a local video file can be written using only the public entry points of the capabilities, in under 60 lines, with no change to any capability.
- **SC-009**: The daily flow reads top to bottom in a single module of at most 300 lines that contains no delivery-channel or file-layout specifics.
- **SC-010**: Every test of preserved behavior keeps passing; the only tests removed are those of removed behavior.
- **SC-011**: After removal, no command, recipe, bot handler, configuration setting, skill or document refers to prepared stories, the queue, two-part stories, image stories or the interactive bot.
- **SC-012**: Every manifest written before the refactor loads in publish-only mode without modification.

## Assumptions

- The operator is the only user and the only maintainer; "easier to change" is measured from their point of view.
- This is a refactor: no new operator-facing capability is delivered. The web interface, the database and the new rendering strategies are explicitly out of scope; only the seams for them are in scope.
- The production surface is the daily run started by the Telegram bot's schedule or command on the server, and the same run started from the command line, in its three modes. Nothing else is preserved.
- Local story preparation and two-part stories may be rebuilt later on top of the new boundaries; the writer contract and the N-part story model are the seams that make that cheap. No package format, queue or two-part prompt survives this feature.
- The refactor is delivered incrementally: removal first, then each capability is put behind its boundary while the existing path keeps working, so that the daily run never stops being deployable. The order and grouping are decided in the plan.
- Prompts stay as files in the repository, written as rationale rather than rules, edited by hand; "easier to change" means one location and no code change.
- The existing TikTok publisher is already behind a contract and is not reworked internally; only the scheduling arithmetic is moved out of it into the flow. The TikTok session tooling (bootstrap, REPL, run logs) is deployment tooling and stays.
- The generic story model supports N parts internally; production produces one-part stories only, and no prompt for two or more parts is written in this feature.
- The existing configuration file remains the single place of configuration; new boundaries are selected by the same file.
- The delivery channels (Telegram bot, command line, and a future web page) are adapters that call the flow and receive progress; they hold no business decisions.

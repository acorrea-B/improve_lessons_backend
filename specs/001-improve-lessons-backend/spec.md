# Feature Specification: Improve Lessons Backend

**Feature Branch**: `001-improve-lessons-backend`

**Created**: 2026-10-13

**Status**: Draft

**Input**: User description: "Improve Lessons Backend — Consolidated Product Features and User Flows. Backend component of a multi-user English-learning product covering registration, learning schedule, reminders, daily records, daily reading/writing practice, weekly and monthly summaries, learning history, a personalized AI assistant, progress indicators, motivation/progressive challenges, two-model content generation/evaluation, and configurable feature availability. Initial release is text-based; audio, images, full courses, social features, payments, native mobile, and automatic platform integrations are out of scope."

## Summary

`improve_lessons_backend` is the backend for a multi-user English-learning product that helps learners build consistent study habits, document what they have learned, reinforce that knowledge through personalized reading and writing practice, and progressively develop their English reading and writing skills.

The product connects five core capabilities into a continuous learning experience: (1) learning schedule management, (2) daily learning records, (3) personalized educational content, (4) contextual AI assistance, and (5) progress tracking. AI-generated content is gated by an independent evaluation model that ensures every delivered material is appropriate for the learner's declared CEFR level (A1–C2).

The initial release is text-based and explicitly excludes audio, images, full-course management, social features, payments, native mobile, automatic external-platform integration, and universal feature availability at launch.

## Clarifications

### Session 2026-10-13

- Q: Once a user submits a daily summary for a session, should the system allow them to edit or replace it, or should the first submission be final? → A: Immutable; the first submission is final. The user must be able to see their writing as it was at the time, so they can see how their own expression advances over time. Resubmissions are rejected; the original wording, submission timestamp, and submission status are preserved.
- Q: If a user tries to submit a daily summary before the session's scheduled start time, how should the system handle that submission? → A: Accept it and flag it for downstream. The submission is recorded as `on_time` if it falls within the end + 30 min window, and a `submitted_before_session_start` flag is set on the summary so daily material generation, weekly, and monthly pipelines can choose whether to act on it immediately or wait.
- Q: What is the expected account lifecycle when a user wants to leave the product? Should the system support account deletion? → A: Not supported in the initial release. The system does not provide a user-facing account-deletion flow. Personal data, learning history, and generated materials are retained for the life of the account. Account deletion is an explicit forward concern.
- Q: When the AI provider is transiently unavailable, how should the content generation and evaluation workflow behave? → A: Retry the corrective loop on transient failures. Transient provider errors share the same bounded corrective-revision loop as validation failures. The bound is reached only when the provider remains unavailable, after which the system records the failure and does not deliver unapproved material.
- Q: What is the canonical weekly boundary in the user's time zone? → A: Monday 00:00 to next Monday 00:00 (ISO-8601). The boundary is deterministic and not per-user configurable in this release. Monthly boundaries are the calendar month in the user's time zone.

## User Scenarios & Testing *(mandatory)*

User journeys are ordered by dependency. Each journey is independently testable and represents a vertical slice of value. Earlier journeys produce artifacts (a registered user, a configured schedule, a submitted summary) that later journeys depend on, but each can be exercised on its own with synthetic data.

### User Story 1 — Register and Configure a Learning Profile (Priority: P1)

A new user visits the platform, registers, declares their English proficiency level (A1–C2), and configures their learning preferences. They can later review or update their profile.

**Why this priority**: This is the foundation. Every other feature (scheduling, reminders, summaries, personalized content) requires a registered user with a declared CEFR level. Without it, no downstream functionality has a personalization anchor.

**Independent Test**: Can be fully tested by completing a registration with a name, an email, a CEFR level, and a time zone, then re-reading the profile. Delivers the value of "we know who the learner is and what level to target."

**Acceptance Scenarios**:

1. **Given** an unregistered visitor, **When** they submit name, email, CEFR level, and time zone, **Then** the system creates an account, persists the profile, and confirms registration.
2. **Given** a registered user, **When** they update their CEFR level or learning preferences, **Then** the system saves the new values and the previous values are retained in history.
3. **Given** a registration attempt with a missing or invalid email, **When** the form is submitted, **Then** the system rejects the request with a clear field-level error and does not create an account.
4. **Given** a registration attempt with a CEFR value outside the supported set (A1, A2, B1, B2, C1, C2), **When** the form is submitted, **Then** the system rejects the value with a clear error.

---

### User Story 2 — Configure a Learning Schedule with Modality (Priority: P1)

A registered user defines the start and end times of their planned learning sessions, selects a recurrence pattern (daily, every other day), declares the class modality (in-person or virtual), and — for virtual classes — selects or registers an external learning platform and its URL. For in-person classes they provide a location. They can review, reuse, and modify the schedule and previously registered platform information.

**Why this priority**: The schedule is the input to reminders, to the on-time/late submission window, and to weekly/monthly period boundaries. Without a configured schedule there is no session to remind the user about and no deadline against which to evaluate submissions.

**Independent Test**: Can be tested by creating a schedule for a known user, retrieving it, and verifying the recurrence expansion for a known window. Delivers the value of "the system knows when the user intends to study and how to reach them."

**Acceptance Scenarios**:

1. **Given** a registered user, **When** they create a schedule with start time, end time, recurrence, modality, and platform (virtual) or location (in-person), **Then** the schedule is saved and associated with the user.
2. **Given** an existing schedule, **When** the user updates start time, end time, recurrence, modality, or platform/location, **Then** the new values are saved and the previous values are retained in history.
3. **Given** a virtual class, **When** the user selects a previously registered platform, **Then** the platform's URL is reused and need not be re-entered.
4. **Given** a virtual class, **When** the user registers a new platform with a name and URL, **Then** the platform is saved for future reuse on subsequent schedules.
5. **Given** a schedule entry with end time not after start time, **When** the form is submitted, **Then** the system rejects the entry with a clear error.
6. **Given** a virtual-class schedule, **When** the user does not provide a platform or URL, **Then** the system rejects the entry with a clear error.
7. **Given** an in-person schedule, **When** the user does not provide a location, **Then** the system rejects the entry with a clear error.

---

### User Story 3 — Receive a Learning Reminder (Priority: P2)

A user with a configured schedule receives an email notification five minutes before the scheduled start time of each class. The notification content reflects the session's modality — for virtual classes it includes the platform URL, for in-person classes the location. The notification is delivered in the user's time zone.

**Why this priority**: Reminders are the mechanism that converts "intended schedule" into "actual session." They depend on the schedule (P1) but are independent of summaries, content generation, and reporting. They can be tested by configuring a schedule and observing a single email.

**Independent Test**: Can be tested by scheduling a known session five or more minutes in the future, advancing the system clock to five minutes before start, and confirming that an email is produced with the correct session info and modality-appropriate content. Delivers the value of "the user is prompted to start on time."

**Acceptance Scenarios**:

1. **Given** a user with a virtual session scheduled to start in five minutes (in the user's time zone), **When** the scheduled time arrives, **Then** the system produces an email containing the session info and the platform URL.
2. **Given** a user with an in-person session scheduled to start in five minutes (in the user's time zone), **When** the scheduled time arrives, **Then** the system produces an email containing the session info and the location.
3. **Given** a user with a session scheduled in their time zone, **When** the reminder is produced, **Then** the reminder is delivered to the email on the user's profile and the timestamp on the notification reflects the user's time zone.
4. **Given** a user who has disabled reminders (per Configurable Feature Availability), **When** the scheduled time arrives, **Then** no email is produced.

---

### User Story 4 — Document a Daily Learning Record (Priority: P1)

After completing a planned learning activity, the user opens the daily record associated with that session, writes a summary of what they learned, and submits it. Summaries submitted within 30 minutes after the scheduled end time are recorded as on-time; summaries submitted after that window are accepted and recorded as late. Both are retained in the user's learning history.

**Why this priority**: The submitted summary is the primary context for personalized content generation (P1), the input to weekly/monthly summaries (P1), and the source of evidence for progress and consistency metrics. Without it, every downstream feature has no learning data to act on.

**Independent Test**: Can be tested by submitting a summary for a known session and verifying the record is stored with a submission timestamp, a derived submission status, and a link to the session. Delivers the value of "the user's learning is captured and dated."

**Acceptance Scenarios**:

1. **Given** a user with a session whose scheduled end time was t_end, **When** they submit a summary at t_end + 10 minutes, **Then** the system persists the summary with submission status `on_time` and timestamp equal to the actual submission time.
2. **Given** a user with a session whose scheduled end time was t_end, **When** they submit a summary at t_end + 45 minutes, **Then** the system persists the summary with submission status `late` and timestamp equal to the actual submission time.
3. **Given** a session for which a summary was already submitted, **When** the user attempts to submit a second summary for the same session, **Then** the system rejects the duplicate and the original summary is preserved unchanged.
3a. **Given** an immutable daily summary, **When** the user reviews their history, **Then** the original wording, submission timestamp, and submission status remain visible so the user can see their writing as it was at the time.
4. **Given** an attempt to submit an empty summary, **When** the request is made, **Then** the system rejects it with a clear error and does not create a record.
5. **Given** a late submission, **When** it is recorded, **Then** it is flagged as late but remains available for downstream material generation, weekly/monthly aggregation, and history retrieval — and is never silently reclassified as a missed session.
6. **Given** any submission, **When** the on-time/late status is computed, **Then** the computation is performed against the user's configured time zone, not the server's local time.

---

### User Story 5 — Generate and Receive Daily Reading and Writing Practice (Priority: P1)

After the user submits a daily summary, the system generates reading material and writing exercises grounded in the summary content and the user's documented learning history, at a difficulty appropriate to the user's CEFR level. The content is produced by a content-generation model and then evaluated by a separate content-evaluation model. The user only sees content that the evaluator has approved.

**Why this priority**: This is the central pedagogical value of the product. The full two-model validation loop is also the most architecturally significant requirement, and the constitution declares it non-negotiable.

**Independent Test**: Can be tested by submitting a summary and then polling for the generated daily material. The test must verify both the artifact exists and that the artifact carries a clear "approved by evaluation" marker. Delivers the value of "the user practices the concepts they just studied, at a level they can actually use."

**Acceptance Scenarios**:

1. **Given** a just-submitted on-time daily summary, **When** the system generates daily reading and writing material, **Then** the content is grounded in the summary and the user's history and is tagged with the user's CEFR level.
2. **Given** a generated daily material, **When** the content-evaluation model runs, **Then** the material is either marked approved (and surfaced to the user) or marked rejected (and never surfaced).
3. **Given** a material rejected by the evaluation model, **When** the corrective process runs, **Then** the generation model produces a revised version and the evaluation model re-runs; the loop continues until approval or a bounded retry limit is reached.
4. **Given** a material that has exceeded the bounded retry limit, **When** the corrective process terminates, **Then** the system records the failure with diagnostic detail and does not surface unapproved material.
5. **Given** a CEFR level far above the difficulty of the generated material, **When** the evaluator runs, **Then** the material is rejected as misaligned.
6. **Given** a CEFR level far below the difficulty of the generated material, **When** the evaluator runs, **Then** the material is rejected as misaligned.
7. **Given** a user with multiple daily summaries in their history, **When** the current summary is processed, **Then** the generated material references relevant previously documented vocabulary and concepts.

---

### User Story 6 — Review a Weekly Learning Summary (Priority: P2)

At the end of the learning week, the user accesses a weekly summary that consolidates their recorded activity for the period: which sessions had summaries, which were on-time and which were late, the recorded study time, learning consistency indicators, the knowledge they documented, and the reading/writing activities generated to reinforce the week's learning. The summary covers sessions of both modalities.

**Why this priority**: Weekly summaries are the first level of longer-horizon reflection. They depend on daily records (P1) and on the date/time-zone machinery established in P1/P2.

**Independent Test**: Can be tested by seeding a known week of submissions (mix of on-time, late, and absent) and verifying the weekly summary's counts, totals, and recommendations. Delivers the value of "the user sees their week, not just their day."

**Acceptance Scenarios**:

1. **Given** a user with a mix of on-time, late, and missing daily summaries in a known week, **When** the user requests the weekly summary, **Then** the summary lists the on-time count, the late count, the missing count, and the recorded study time for that week.
2. **Given** a user with at least one approved daily material in the week, **When** the user requests the weekly summary, **Then** the summary includes the integrated weekly reading and writing activities.
3. **Given** a user whose weekly summary is requested, **When** the consistency indicators are calculated, **Then** only on-time submissions are counted as on-time (late submissions are not promoted), and missing sessions are not inferred from a late submission.
4. **Given** a week that spans a month boundary, **When** the weekly summary is generated, **Then** the week boundary is determined by the user's time zone and aligns with the user's configured start-of-week.
5. **Given** a week with no submissions, **When** the user requests the weekly summary, **Then** the summary still renders (with zero counts and an appropriate "no activity this week" message) rather than erroring.

---

### User Story 7 — Review a Monthly Learning Summary (Priority: P3)

At the end of the learning month, the user accesses a monthly summary that consolidates activity for the month: daily session counts, on-time vs late breakdown, study time, consistency indicators, the knowledge they documented, and the cumulative reading and writing activities generated to reinforce the month.

**Why this priority**: Monthly summaries are a higher-horizon reflection on top of weekly summaries. They depend on the same data and on weekly generation. They are still independent — they can be tested with synthetic monthly data.

**Independent Test**: Can be tested by seeding a month with a known daily-record mix and verifying the monthly rollup. Delivers the value of "the user sees their commitment over a month, not just a week."

**Acceptance Scenarios**:

1. **Given** a user with multiple weeks of activity in a known month, **When** the user requests the monthly summary, **Then** the summary includes the monthly total of on-time and late submissions, recorded study time, and consistency indicators.
2. **Given** a user with at least one weekly summary approved in the month, **When** the user requests the monthly summary, **Then** the monthly summary includes the cumulative reading and writing activities drawn from the month's weekly materials.
3. **Given** a month, **When** monthly period boundaries are computed, **Then** they are determined by the user's time zone, not by the server clock.
4. **Given** a month with no submissions, **When** the user requests the monthly summary, **Then** the summary renders with zero counts and an appropriate message.

---

### User Story 8 — Retrieve Historical Learning Records and Materials (Priority: P2)

The user accesses their learning history, selects a period (day, week, or month), browses the corresponding summaries, opens the associated reading and writing materials, and revisits previously studied concepts. Late submissions are visible in history — not hidden.

**Why this priority**: History is the user's primary review surface and the source of all reinforcement. It depends on summaries and materials existing, but it is independently testable against any seeded history.

**Independent Test**: Can be tested by seeding a known history and querying it for a known period. Delivers the value of "the user can return to any past lesson."

**Acceptance Scenarios**:

1. **Given** a user with a history of daily, weekly, and monthly summaries, **When** the user requests a specific day, **Then** the system returns that day's summary, the associated reading material, and the associated writing exercises.
2. **Given** a user with a history of daily, weekly, and monthly summaries, **When** the user requests a specific week or month, **Then** the system returns the corresponding period summary and the integrated activities.
3. **Given** a user with at least one late submission in history, **When** the user browses history, **Then** the late submission is visible (with its `late` status) and is not hidden, deleted, or reclassified.
4. **Given** a request for a period with no data, **When** the user queries, **Then** the system returns an empty result with a clear "no records" message and a 200/204-style success response, not an error.
5. **Given** any history query, **When** the system returns data, **Then** the relationship between the recorded activity and its associated materials is preserved (i.e., the material returned for a session is the material that was generated for that session, not a regenerated copy).

---

### User Story 9 — Converse with the Personalized AI Learning Assistant (Priority: P2)

The user opens the assistant, asks a question about a concept they do not understand, and receives an explanation adapted to their CEFR level and grounded in their documented learning history. The assistant addresses the user by their preferred name. Conversations are text-based only.

**Why this priority**: The assistant is the most personalized support surface in the product. It depends on a registered user and a populated learning history, but it can be tested in isolation against a synthetic history.

**Independent Test**: Can be tested by sending a known question to the assistant for a user with a known history and verifying the response references the user's level and history. Delivers the value of "the user has a tutor that knows them."

**Acceptance Scenarios**:

1. **Given** a user with a known CEFR level, **When** the user asks a question, **Then** the assistant's response is written at a difficulty appropriate to that level.
2. **Given** a user with documented vocabulary or concepts in their history, **When** the user asks about one of those concepts, **Then** the response references relevant items from the user's history and is not a generic answer.
3. **Given** a user with a preferred name on their profile, **When** the assistant responds, **Then** the response addresses the user by their preferred name.
4. **Given** a request for additional examples or clarification, **When** the user asks a follow-up, **Then** the assistant provides a follow-up that remains grounded in the user's history and level.
5. **Given** an attempt to send audio, voice, or other non-text media, **When** the request is made, **Then** the system rejects it (initial release is text-based).

---

### User Story 10 — Review Reading, Writing, and Consistency Progress Indicators (Priority: P2)

The user accesses their learning progress, reviews the available reading-related indicators, the available writing-related indicators, and the consistency/activity indicators. The product keeps these three dimensions distinct and never presents activity metrics as language proficiency.

**Why this priority**: Progress visibility is the user's primary feedback loop. It depends on recorded history but is otherwise independent.

**Independent Test**: Can be tested by seeding a known history of submissions, completed materials, and on-time/late mix, then verifying that the three indicator dimensions are populated independently and that the language used to describe them does not cross the activity/proficiency line. Delivers the value of "the user sees their effort, fairly framed."

**Acceptance Scenarios**:

1. **Given** a user with a known history, **When** the user requests progress, **Then** the response includes separate sections for reading-related, writing-related, and consistency/activity indicators.
2. **Given** insufficient evidence of skill development, **When** the user views the reading or writing indicators, **Then** the system communicates that the indicators are based on activity signals rather than proficiency evidence.
3. **Given** any progress output, **When** the system presents numbers, **Then** it does not describe them as proficiency scores, certification, or formal assessment.
4. **Given** a user with no recorded activity, **When** the user requests progress, **Then** the system returns a clear "no activity yet" message instead of fabricated numbers.

---

### User Story 11 — Receive Motivation, Recognition, and Progressive Challenges (Priority: P3)

The user receives encouraging feedback and recognition of achievements, is offered reading and writing challenges appropriate to their CEFR level and demonstrated progress, and is invited to take on gradually more demanding activities. Recommendations never exceed the user's productive zone.

**Why this priority**: Motivation is a quality-of-experience feature on top of the core data flows. It is testable independently but depends on the user having some history to draw from.

**Independent Test**: Can be tested by seeding a user with a known history and verifying that the recommended challenges match their CEFR level and that no challenge exceeds the appropriate level. Delivers the value of "the user feels recognized and appropriately stretched."

**Acceptance Scenarios**:

1. **Given** a user who completed a target such as a streak of on-time submissions, **When** the user opens the home surface, **Then** the system shows a recognition message for the achievement.
2. **Given** a user with documented progress, **When** the system recommends a challenge, **Then** the recommended challenge is at or just above the user's current CEFR level — never multiple levels above.
3. **Given** a user whose CEFR level is the highest supported, **When** the system recommends a challenge, **Then** the system recommends refinements within the same level rather than exceeding it.
4. **Given** a user with no recorded history, **When** the system recommends challenges, **Then** the system recommends starting challenges appropriate to the user's declared CEFR level, not derived from any prior activity.

---

### User Story 12 — Operate the Two-Model Content Generation and Evaluation Workflow (Priority: P1 — Cross-cutting)

The system runs a content-generation model and a content-evaluation model with clearly separated responsibilities. Generated content is never delivered to the user until the evaluator approves it. A failed evaluation triggers a corrective revision; a bounded retry strategy prevents uncontrolled retries. The system exposes the evaluation result for any generated material so that other features (daily, weekly, monthly, motivation) can rely on the approval gate.

**Why this priority**: This is the constitution's Principle II — the primary mechanism that protects content quality. It is the dependency under which every content-producing story (P5, P6, P7, P9, P11) runs.

**Independent Test**: Can be tested by submitting a generation request for a known user with a known history and inspecting the evaluation result, the corrective-loop behavior, and the bounded-retry limit. Delivers the value of "no unapproved content is ever delivered."

**Acceptance Scenarios**:

1. **Given** any content generation request, **When** the generation model runs, **Then** it receives the user's CEFR level, the relevant learning history, and the activity purpose as inputs.
2. **Given** a generated material, **When** the evaluation model runs, **Then** it produces a structured assessment covering vocabulary complexity, grammatical structures, sentence length, reading demands, writing demands, and relevance to documented objectives.
3. **Given** an evaluation result of `approved`, **When** the workflow completes, **Then** the material is delivered to the requesting user flow.
4. **Given** an evaluation result of `rejected`, **When** the workflow completes, **Then** the material is not delivered, the corrective process triggers, and the system produces a revised material for re-evaluation.
5. **Given** repeated rejections, **When** the retry count reaches the configured bound, **Then** the workflow terminates with a logged failure and no unapproved material is delivered.
6. **Given** an evaluation result, **When** it is stored, **Then** the result is auditable (i.e., the system can later explain why a given material was approved or rejected for a given user).

---

### User Story 13 — Respect Configurable Feature Availability (Priority: P3 — Cross-cutting)

Selected features are made available according to the product's current release and availability decisions. Feature availability is controlled through configuration. The product supports the gradual introduction of capabilities as it evolves. The exact scope of this configuration (global, per-user, or both) is to be decided during planning.

**Why this priority**: This is a release-management capability that affects all features but is not user-visible in a way that drives a learning outcome. It is testable independently.

**Independent Test**: Can be tested by toggling a feature off in configuration and verifying that the corresponding user flow becomes unavailable with a clear "not available" message. Delivers the value of "the product can release features in stages."

**Acceptance Scenarios**:

1. **Given** a feature flagged as disabled in configuration, **When** the user attempts to use that feature, **Then** the system returns a clear "not currently available" message rather than silently failing.
2. **Given** a feature that is enabled globally, **When** the user accesses it, **Then** the feature is available regardless of per-user state (until per-user overrides are introduced in planning).
3. **Given** a configuration change, **When** a user next interacts with the product, **Then** the new configuration takes effect without requiring a re-login.

---

### Edge Cases

- **No schedule yet but a reminder time arrives**: no reminder is sent (a session requires a configured schedule).
- **No summary for a session**: a daily material is never generated for that session. The session is counted as missing in weekly/monthly summaries, not as "late." The missing session is never silently inferred from silence alone.
- **Summary submitted with no recoverable content** (e.g., blank or all whitespace): rejected as invalid input.
- **Schedule updated after a session has started**: existing reminders are not retroactively modified. The new schedule applies to subsequent sessions.
- **User changes CEFR level**: previously generated materials are not retroactively re-evaluated; future generations use the new level. The change is recorded in the profile history.
- **User changes time zone**: existing sessions and their submission statuses are not retroactively reclassified; future scheduling uses the new time zone. Historical timestamps remain in the original time zone with the original zone recorded.
- **Content evaluation repeatedly fails for a given session**: the bounded-retry limit is reached, the failure is logged, and the user is told the system could not produce appropriate material this time. No unapproved material is delivered.
- **AI provider unavailable during a request**: the system records a structured failure, returns a clear user-facing error, and the user can retry.
- **User attempts to access another user's history, summary, or assistant thread**: the request is rejected as unauthorized.
- **User submits a summary for a session in the future** (i.e., before the scheduled end time): the submission is accepted; status is `on_time` if before the end time and within the 30-minute window — otherwise the system flags the case for product review (documented as Assumption A-3 below).
- **A weekly summary request arrives while the underlying daily materials are still being generated**: the weekly summary uses whatever has been approved at request time and notes the pending count.
- **Feature is toggled off mid-session**: in-flight operations complete; subsequent requests for the disabled feature return the "not available" message.
- **External platform URL is malformed or unreachable**: the URL is stored as the user provided it; reachability is not validated by the system. The reminder uses the URL as-is.

## Requirements *(mandatory)*

### Functional Requirements

#### Registration and Profile (US-1)
- **FR-001**: System MUST allow an unregistered visitor to create an account by providing a name, an email, a CEFR level (A1, A2, B1, B2, C1, C2), and a time zone.
- **FR-002**: System MUST reject a registration that is missing a name, an email, a CEFR level, or a time zone, with a field-level error indicating the missing field.
- **FR-003**: System MUST reject an email that is not syntactically valid or that is already in use by another account.
- **FR-004**: System MUST reject a CEFR value that is not one of {A1, A2, B1, B2, C1, C2}.
- **FR-005**: System MUST allow a registered user to view their current profile.
- **FR-006**: System MUST allow a registered user to update their name, email, CEFR level, or time zone, and MUST retain the previous values in the profile history.
- **FR-007**: System MUST use the declared CEFR level as the personalization anchor for all content generation, content evaluation, and AI assistant responses for that user.
- **FR-008**: System MUST NOT present progress indicators, recommendations, or any internal signals as a formal English proficiency certification.
- **FR-008a**: System MUST NOT provide a user-facing account-deletion flow in the initial release. Personal data, learning history, and generated materials are retained for the life of the account. Account deletion is an explicit future concern and is tracked outside this spec.

#### Learning Schedule (US-2)
- **FR-009**: System MUST allow a registered user to create a schedule with a start time, an end time, a recurrence pattern (at least `daily` and `every_other_day`), a modality (`in_person` or `virtual`), and modality-specific information.
- **FR-010**: System MUST reject a schedule entry whose end time is not strictly after its start time.
- **FR-011**: System MUST require a platform (selected from a registered list) and a URL for a `virtual` modality entry, and MUST require a location for an `in_person` modality entry.
- **FR-012**: System MUST allow a user to register a new external learning platform with a name and a URL, and MUST make that platform available for reuse on subsequent virtual-modality schedules.
- **FR-013**: System MUST associate each scheduled session with a planned start time, end time, modality, and (per modality) the platform/URL or location, all in the user's configured time zone.
- **FR-014**: System MUST allow a user to retrieve, reuse, and modify their schedule.
- **FR-015**: System MUST expand the recurrence pattern into concrete sessions according to the user's time zone, and MUST use those concrete sessions to drive reminders and submission windows.

#### Reminders (US-3)
- **FR-016**: System MUST send a reminder email five minutes before the scheduled start time of each session, in the user's time zone.
- **FR-017**: The reminder content MUST include the session's start time, modality, and modality-specific information (URL for virtual, location for in-person).
- **FR-018**: System MUST deliver reminders to the email address on the user's profile.
- **FR-019**: System MUST respect the configurable-feature-availability gate: if reminders are disabled, no email is produced.
- **FR-020**: System MUST record every reminder attempt (sent, suppressed, or failed) in a structured log.
- **FR-021**: System MUST NOT treat the production or delivery of a reminder as evidence that the user studied.

#### Daily Records and Submission Status (US-4)
- **FR-022**: System MUST allow a user to open the daily record associated with a specific scheduled session and submit a non-empty summary of what they learned.
- **FR-023**: System MUST reject a summary that is empty or contains only whitespace.
- **FR-024**: System MUST persist each submitted summary with an immutable record containing the user, the session, the submission timestamp, and the derived submission status.
- **FR-024a**: System MUST reject any attempt to modify or replace a previously submitted daily summary; the original wording, timestamp, and status MUST be preserved so the user can see their writing as it was at the time of submission.
- **FR-025**: System MUST derive submission status as `on_time` if the submission timestamp is at or before the scheduled end time plus 30 minutes (in the user's time zone), and `late` otherwise.
- **FR-025a**: System MUST accept a submission whose timestamp is before the session's scheduled start time, classify it as `on_time` if it falls within the end + 30 minute window, and record a `submitted_before_session_start` flag on the summary so downstream pipelines (daily material generation, weekly/monthly aggregation, progress) can decide whether to act on the record or wait for the actual session to occur.
- **FR-026**: System MUST accept late submissions; a late submission MUST be flagged as `late` and MUST be retained in the user's history.
- **FR-027**: System MUST NOT reclassify a late submission as a missed session. A late submission is a submission, not a missing record.
- **FR-028**: System MUST NOT count a late submission as an on-time submission in any consistency or activity calculation.
- **FR-029**: System MUST perform the on-time/late computation against the user's configured time zone, never the server's local time.
- **FR-030**: System MUST preserve the distinction between scheduled study duration, the actual submission timestamp, and the submission status.
- **FR-031**: System MUST allow the user to retrieve and review previously submitted summaries, including late submissions, with the original status preserved.

#### Daily Reading and Writing Practice (US-5)
- **FR-032**: After a daily summary is persisted, System MUST generate reading material and writing exercises grounded in that summary and the user's documented learning history.
- **FR-033**: The generation request MUST include the user's CEFR level, the submitted summary, the relevant prior summaries/concepts from the user's history, and the activity purpose.
- **FR-034**: The generated material MUST be evaluated by the content-evaluation model (FR-038 through FR-046) before being delivered to the user.
- **FR-035**: System MUST retain each daily material with the corresponding approved/rejected status of the evaluation, the evaluation reasoning summary, and the link to the source summary.
- **FR-036**: System MUST surface the approved daily material to the user through a daily-materials retrieval endpoint.
- **FR-037**: System MUST NOT deliver a daily material whose evaluation result is anything other than `approved`.

#### Content Generation and Evaluation Workflow (US-12)
- **FR-038**: System MUST implement two distinct AI responsibilities: a Content Generation Model and a Content Evaluation Model, with no shared internal state and no shared prompts.
- **FR-039**: The Content Generation Model MUST receive as inputs: the user's CEFR level, the relevant learning-history context, the activity purpose (e.g., reading comprehension, written expression), and the time-period objective (daily, weekly, monthly, recommendation).
- **FR-040**: The Content Evaluation Model MUST assess the generated material against proficiency-level criteria including vocabulary complexity, grammatical structures, sentence length and complexity, reading comprehension demands, writing task requirements, and relevance to the user's documented objectives.
- **FR-041**: The Content Evaluation Model MUST return a structured result with a verdict (`approved` or `rejected`), a per-criterion assessment, and a rationale.
- **FR-042**: System MUST prevent any material with a non-`approved` verdict from being delivered to a user.
- **FR-043**: System MUST trigger a corrective process on rejection: regenerate → re-evaluate, bounded by a configured retry limit.
- **FR-044**: System MUST NOT deliver unapproved material after the retry limit is reached; the system MUST record the failure with diagnostic detail.
- **FR-044a**: System MUST treat transient AI provider failures (network error, rate limit, 5xx) as inputs to the same corrective-revision loop defined in FR-043. The user experiences a delay; the bound is reached only when the provider remains unavailable, at which point the system records the failure and does not deliver unapproved material.
- **FR-045**: System MUST store the evaluation result alongside the generated material for later auditability.
- **FR-046**: System MUST ensure that a generated material is delivered exactly once, after the approval verdict, and that the same material is not re-evaluated for re-delivery.

#### Weekly and Monthly Summaries (US-6, US-7)
- **FR-047**: System MUST generate a weekly summary that lists the on-time, late, and missing daily-record counts, the recorded study time, the consistency indicators, and a synthesis of the knowledge documented in the period, for each user on a defined cadence.
- **FR-048**: System MUST generate a weekly reading and writing material that integrates concepts from the week's summaries, subject to the content evaluation gate.
- **FR-049**: System MUST generate a monthly summary that consolidates weekly activity and produces monthly-level consistency indicators, total study time, and a synthesis of the knowledge documented in the month.
- **FR-050**: System MUST generate a monthly reading and writing material that integrates concepts from the month's weekly materials, subject to the content evaluation gate.
- **FR-051**: Weekly period boundaries MUST be Monday 00:00 to next Monday 00:00 in the user's time zone (ISO-8601). Monthly period boundaries MUST be the calendar month in the user's time zone. Both are deterministic and not per-user configurable in this release.
- **FR-052**: System MUST retain weekly and monthly summaries and their associated materials for later retrieval.

#### Learning History Retrieval (US-8)
- **FR-053**: System MUST allow a user to retrieve their daily summaries and associated materials for a specified day.
- **FR-054**: System MUST allow a user to retrieve their weekly summaries and integrated materials for a specified week.
- **FR-055**: System MUST allow a user to retrieve their monthly summaries and cumulative materials for a specified month.
- **FR-056**: System MUST return late submissions in history queries with their `late` status preserved.
- **FR-057**: System MUST preserve the relationship between a record and its associated materials: the materials returned for a given day/week/month are the materials that were generated for that period, not regenerated on demand.
- **FR-058**: System MUST restrict history queries to the requesting user's own data.

#### Personalized AI Learning Assistant (US-9)
- **FR-059**: System MUST provide a text-based conversational endpoint backed by an AI model.
- **FR-060**: The assistant MUST use the user's CEFR level to calibrate the linguistic difficulty of its responses.
- **FR-061**: The assistant MUST use relevant items from the user's documented learning history as context when generating responses.
- **FR-062**: The assistant MUST address the user by their preferred name.
- **FR-063**: The assistant MUST be able to explain vocabulary, grammatical structures, and concepts documented in the user's history.
- **FR-064**: The assistant MUST be able to recommend additional practice based on the user's learning context.
- **FR-065**: System MUST reject any non-text input (audio, image, etc.) — the initial release is text-based.
- **FR-066**: System MUST retain assistant conversation history per user and MUST restrict retrieval to the requesting user.

#### Progress Indicators (US-10)
- **FR-067**: System MUST provide three distinct progress dimensions: reading, writing, and learning consistency.
- **FR-068**: System MUST compute reading-related indicators from the available reading activity signals.
- **FR-069**: System MUST compute writing-related indicators from the available writing activity signals.
- **FR-070**: System MUST compute consistency/activity indicators from on-time vs late submission mix, scheduled session adherence, and frequency of recorded activity over time.
- **FR-071**: System MUST communicate uncertainty when there is insufficient evidence of skill development, and MUST NOT present activity metrics as proficiency scores.
- **FR-072**: System MUST NOT use language that presents any of the three indicator dimensions as a formal assessment of English proficiency.

#### Motivation and Progressive Challenges (US-11)
- **FR-073**: System MUST recognize user achievements (e.g., on-time streaks, weekly targets) and surface a recognition message.
- **FR-074**: System MUST recommend reading or writing challenges appropriate to the user's CEFR level and demonstrated progress.
- **FR-075**: System MUST NOT recommend a challenge that exceeds the user's current CEFR level by more than one level.
- **FR-076**: System MUST allow the user to access a recommended challenge as a daily, weekly, or monthly material, subject to the same content evaluation gate.
- **FR-077**: System MUST recommend refinements (longer passages, more demanding writing) within the same level once the user has reached the highest supported CEFR level.

#### Configurable Feature Availability (US-13)
- **FR-078**: System MUST read feature-availability configuration at request time and gate the corresponding user flow accordingly.
- **FR-079**: When a feature is disabled, the corresponding user flow MUST return a clear "not currently available" message rather than a generic error.
- **FR-080**: System MUST support a global configuration switch for each gated feature.
- **FR-081**: System MUST allow the configuration to evolve to support per-user feature availability (the exact model is to be decided in planning).

#### Cross-cutting (Auth, Privacy, Observability, Auditability)
- **FR-082**: System MUST authenticate every request to a user-protected endpoint.
- **FR-083**: System MUST authorize each request against the requesting user's identity; cross-user access MUST be rejected.
- **FR-084**: System MUST log every reminder attempt, summary submission, content generation, content evaluation, and assistant turn with enough structure to diagnose failures.
- **FR-085**: System MUST log the on-time/late decision with the inputs (session end time, submission time, time zone) used to compute it, for auditability.
- **FR-086**: System MUST log the content evaluation result with verdict, criteria, and rationale for every material.

### Key Entities *(include if feature involves data)*

- **User**: A registered learner. Attributes include name, email, CEFR level (A1–C2), time zone, preferred name, and the timestamps of profile changes. Relationships: owns schedules, sessions, summaries, materials, and assistant threads.
- **User Profile History**: An append-only log of changes to a User's profile (name, email, CEFR, time zone). Relationships: belongs to a User.
- **External Learning Platform**: A name/URL pair registered by a user for virtual-modality sessions. Attributes: name, URL, owner user. Relationships: may be referenced by many scheduled sessions.
- **Schedule**: A user's recurring learning configuration. Attributes: start time, end time, recurrence pattern, modality. Relationships: belongs to a User, expands into one or more Sessions.
- **Session**: A concrete planned learning event produced by expanding a Schedule. Attributes: scheduled start time, scheduled end time, modality, modality-specific information, computed reminder time. Relationships: belongs to a Schedule; may have zero or one Daily Summary; may have zero or one Daily Material.
- **Daily Summary**: A user's written record of what they learned for a given Session. Attributes: session reference, content, submission timestamp, submission status (`on_time` or `late`). Relationships: belongs to a User; references a Session; is the source context for a Daily Material.
- **Daily Material**: Reading and writing exercises generated from a Daily Summary. Attributes: reading content, writing exercises, generation timestamp, evaluation verdict, evaluation rationale. Relationships: belongs to a User; references a Daily Summary.
- **Weekly Summary**: A consolidation of a user's daily activity for a defined week. Attributes: week boundary timestamps, on-time count, late count, missing count, study time, consistency indicators, weekly synthesis, weekly material reference. Relationships: belongs to a User; aggregates multiple Daily Summaries.
- **Weekly Material**: Reading and writing exercises that integrate concepts from a week's summaries. Attributes: reading content, writing exercises, evaluation verdict, evaluation rationale. Relationships: belongs to a User; references a Weekly Summary.
- **Monthly Summary**: A consolidation of a user's weekly activity for a defined month. Attributes: month boundary timestamps, weekly counts, total study time, consistency indicators, monthly synthesis, monthly material reference. Relationships: belongs to a User; aggregates Weekly Summaries.
- **Monthly Material**: Reading and writing exercises that integrate concepts from a month's weekly materials. Attributes: reading content, writing exercises, evaluation verdict, evaluation rationale. Relationships: belongs to a User; references a Monthly Summary.
- **Assistant Thread**: A user's conversation with the AI assistant. Attributes: messages, timestamps, retrieved context references. Relationships: belongs to a User.
- **Content Evaluation**: The structured output of the Content Evaluation Model. Attributes: target material reference, verdict (`approved`/`rejected`), per-criterion assessment, rationale, evaluation timestamp. Relationships: references a generated Material.
- **Feature Availability Config**: A configuration object that gates user flows. Attributes: feature identifier, enabled/disabled state, scope (global, per-user — to be defined in planning). Relationships: read at request time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new visitor can complete registration, declare a CEFR level, and configure a basic schedule in under 5 minutes.
- **SC-002**: 100% of submitted daily summaries are persisted with a submission timestamp and a derived submission status; no submission is lost, regardless of the path (on-time, late, or in-flight failure recovery).
- **SC-003**: 100% of AI-generated daily, weekly, and monthly materials that are delivered to users carry an `approved` evaluation verdict; zero unapproved materials are surfaced.
- **SC-004**: The corrective revision loop terminates within a bounded number of retries for 100% of generation requests; unapproved material is never delivered as a fallback.
- **SC-005**: For 100% of submissions, the on-time/late status is computed against the user's configured time zone; the server's local time is not used for any deadline decision.
- **SC-006**: 100% of late submissions remain retrievable in the user's history with their `late` status preserved; late submissions are never silently reclassified as missed.
- **SC-007**: The system correctly produces and delivers a reminder email five minutes before the scheduled start time of a session in at least 95% of attempts under nominal conditions, with all failures (sent, suppressed, failed) recorded in a structured log.
- **SC-008**: The weekly and monthly summaries correctly reflect the actual on-time/late/missing mix of the underlying daily summaries in 100% of cases; consistency indicators count on-time submissions as on-time only.
- **SC-009**: The assistant's response difficulty is calibrated to the user's CEFR level in 100% of evaluations (verified by sampling and review), and the assistant addresses the user by their preferred name.
- **SC-010**: A user can retrieve the history of any past day, week, or month and see the correct summaries, materials, and statuses (including late submissions) in under 3 seconds for the typical case.
- **SC-011**: 100% of cross-user data access attempts (history, summary, material, or assistant thread from another user) are rejected as unauthorized.
- **SC-012**: 100% of gated features return a clear "not currently available" message when disabled in configuration, rather than failing silently or returning a generic error.
- **SC-013**: Progress indicators are presented as three separate dimensions (reading, writing, consistency) and never described as proficiency scores or formal certification in 100% of responses.
- **SC-014**: Recommended challenges do not exceed the user's current CEFR level by more than one level in 100% of recommendations.
- **SC-015**: Every critical workflow event (reminder, submission, generation, evaluation, assistant turn) produces a structured log entry that can be used to diagnose failures end-to-end.

## Assumptions

- **A-1 (Authentication)**: The system uses a standard, registered-user authentication mechanism (account-bound credentials). The exact mechanism (email+password, magic link, OAuth) is to be decided in planning.
- **A-2 (Duplicate submissions)**: One session accepts at most one persisted daily summary, and the first submission is final. Subsequent attempts to submit, edit, or replace the summary are rejected; the original wording, submission timestamp, and submission status are preserved. This guarantees that the user can review their own writing as it was at the time of submission, which is a core part of how they see their own progress over time. (See FR-024a and US-4 acceptance scenario 3a.)
- **A-3 (Submissions before the session starts)**: A summary submitted before the session's scheduled start time is accepted, classified as `on_time` if it falls within the end + 30 minute window, and tagged with a `submitted_before_session_start` flag so downstream pipelines can decide whether to use the record immediately or wait. This preserves the user's ability to capture notes while the experience is fresh, while keeping the daily material, weekly, and monthly flows free to defer generation until the session actually concludes. (See FR-025a.)
- **A-4 (Email delivery)**: The system integrates with a third-party transactional email provider. The provider, retry policy, and bounce handling are decided in planning.
- **A-5 (External platform URLs)**: Reachability of external platform URLs is not validated by the system. The URL is stored as provided and used as-is in reminders.
- **A-6 (Time zone)**: The system requires a time zone at registration. Daylight-saving transitions follow the IANA tz database; sessions and reminders are scheduled using the user's tz and are not reclassified retroactively.
- **A-7 (CEFR certification disclaimer)**: The system surfaces a "not a formal certification" notice in profile and progress views to support FR-008 and FR-072.
- **A-8 (Feature availability scope)**: The configuration model in this release supports a global on/off switch per gated feature. Per-user overrides are an explicit future direction (FR-081) and not in the initial release.
- **A-9 (Content generation inputs)**: The "concepts the user has previously documented" passed to the generator are limited to a bounded context window (e.g., the most recent N summaries, or a retrieved subset). The exact retrieval strategy is decided in planning and is documented as a deferred engineering decision in the constitution.
- **A-10 (Retry bound)**: The corrective-revision bound (FR-043) defaults to a small number (e.g., 3) and is configurable per environment. The exact default is decided in planning.
- **A-11 (Scope of "weekly" and "monthly")**: Weekly period boundaries are Monday 00:00 to next Monday 00:00 in the user's time zone (ISO-8601). Monthly period boundaries are the calendar month in the user's time zone. The boundary is deterministic and not per-user configurable in this release. (See FR-051.)
- **A-12 (Initial-release text-only)**: Audio, image, and other non-text modalities are out of scope per the product definition. Any user attempt to upload non-text is rejected with a clear "not supported" message.
- **A-13 (Audit log retention)**: Audit logs are retained for a period that meets legal and operational needs; the exact retention period is decided in planning.
- **A-14 (No multi-tenant data)**: The initial release assumes single-tenant data isolation; multi-tenant isolation is a future concern.
- **A-15 (No integration with external LMS)**: The system does not query external learning platforms for attendance, grades, or curriculum. This matches the product's out-of-scope section.
- **A-16 (No account deletion in this release)**: The initial release does not support user-initiated account deletion. Personal data, learning history, and generated materials are retained for the life of the account. Account deletion, including any data-portability or right-to-be-forgotten flow, is a forward concern tracked outside this spec. (See FR-008a.)
- **A-17 (AI provider transient failures share the corrective loop)**: Transient AI provider failures (network error, rate limit, 5xx) are absorbed by the same corrective-revision loop defined in FR-043. The bound is reached only when the provider remains unavailable, after which the system records the failure and does not deliver unapproved material. The user experiences a delay; no separate transient-failure counter is maintained. (See FR-044a.)

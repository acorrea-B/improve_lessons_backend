<!--
# Sync Impact Report

**Version change**: 0.0.0 → 1.0.0 (initial ratification; no prior version existed)
**Bump type**: MAJOR (initial adoption — establishes the first canonical principles for the project)

## Modified principles
None (no prior principles existed). All ten principles are newly created.

## Added sections
- Core Principles (I–X): CEFR-Aligned Content Difficulty, Two-Model Content Generation and Evaluation, Personalization from Documented Learning History, Reliable Learning Records and Submission Integrity, Activity Metrics Are Not Proficiency Evidence, Time-Zone Consistent Scheduling, Progressive, Evidence-Based Difficulty Adaptation, User Motivation and Positive Reinforcement, Separation of Responsibilities, Observability and Failure Containment.
- Non-Functional Standards (Reliability, Data Integrity, Security and Privacy, Scalability, Maintainability, Content Quality).
- Implementation Scope and Technology Neutrality.
- Development Workflow and Compliance Gates.
- Governance (amendment procedure, versioning policy, compliance review).

## Removed sections
None.

## Deferred items (TODO placeholders intentionally retained)
None. All placeholders from the resolved template have been replaced with concrete text.

## Follow-up notes
- The user input was a complete project definition and software requirements specification. It was treated as governance content and incorporated into the constitution.
- No feature implementation, code generation, refactoring, building, or deployment requests were present in the user input, so no deferred non-governance intents exist and no `Next Actions` section is required.
- This Sync Impact Report is temporary scratch material for human review of the amendment and is expected to be removed before the amended constitution file is committed.
-->

# Improve Lessons Backend Constitution
<!-- Project governance for the improve_lessons_backend API: a backend for a personalized, structured, and progressive English-learning platform. -->

## Core Principles

### I. CEFR-Aligned Content Difficulty (NON-NEGOTIABLE)
Every piece of AI-generated learning material MUST be strictly aligned with the user's declared Common European Framework of Reference for Languages (CEFR) level (A1, A2, B1, B2, C1, C2). Material that significantly exceeds or under-shoots the learner's level MUST NOT be delivered. Difficulty must progress gradually; abrupt increases in vocabulary complexity, grammatical sophistication, text length, or writing demand are prohibited without an evidence basis in the user's documented learning progress. Pedagogical relevance and appropriate challenge take precedence over content volume or novelty.

**Rationale:** Material that misaligns with a learner's level causes confusion, frustration, loss of confidence, and eventual abandonment. The platform's long-term value depends on keeping each activity within the learner's productive zone.

### II. Two-Model Content Generation and Evaluation
The system MUST implement a content workflow that uses two distinct AI responsibilities with clear separation of concerns:

- A **Content Generation Model** produces learning materials using the user's proficiency level, documented learning history, the requested activity purpose, and the relevant time-period objectives.
- A **Content Evaluation Model** independently assesses the generated material against proficiency-level criteria (vocabulary complexity, grammatical structures, sentence length and complexity, reading comprehension demands, writing task requirements, and relevance to documented objectives).

Generated content MUST NOT be delivered as an approved learning resource until the evaluation model has approved it. A failed evaluation MUST trigger a corrective process that produces a revised version and resubmits it for evaluation. The system MUST define a bounded handling strategy for repeated validation failures so that unsuitable content is never delivered through an uncontrolled retry loop.

**Rationale:** Generating and evaluating with a single model invites self-approval and lets misalignment slip through. Independent evaluation is the primary mechanism that protects content quality and the learner's experience.

### III. Personalization from Documented Learning History
All AI-generated learning materials (daily, weekly, monthly) and assistant responses MUST be grounded in the user's documented learning history. The system MUST treat previously submitted daily summaries, vocabulary, grammar concepts, and activity patterns as primary context for content generation and contextual explanations. Generic, decontextualized, or boilerplate content is prohibited for any user-facing learning artifact.

**Rationale:** Personalization is the mechanism that turns generic exercises into a learning experience that reinforces what the user actually studied. Without grounding, content becomes a chore rather than reinforcement.

### IV. Reliable Learning Records and Submission Integrity
The system MUST preserve every submitted daily learning summary, the precise submission timestamp, and the derived submission status (`on_time` or `late`) as part of an immutable learning record. Late submissions MUST be accepted, explicitly identified as late, retained indefinitely, and remain available for future consultation and for downstream material generation. A late submission MUST NOT be silently reclassified as a missed session; the system MUST NOT infer that the user did not study simply because the submission was late. The distinction between scheduled study duration, the submission timestamp, and the submission status MUST be preserved end-to-end.

**Rationale:** Trust in the user's learning history depends on the system capturing exactly what the user documented and exactly when. Conflating timestamps, statuses, or reinterpreting late as missed corrupts the data that drives all downstream personalization and reporting.

### V. Activity Metrics Are Not Proficiency Evidence
The system MUST clearly separate learning activity metrics (time spent, sessions recorded, on-time vs late submissions, schedule adherence) from language proficiency indicators. The system MUST NOT present activity metrics as evidence of reading or writing proficiency. Progress indicators MUST distinguish three dimensions: Reading, Writing, and Learning Consistency. Where the system lacks sufficient evidence of actual skill development, it MUST communicate uncertainty rather than overstate skill gains.

**Rationale:** Confusing "showed up and documented" with "improved at English" misleads users, undermines intrinsic motivation, and corrupts the platform's pedagogical credibility. Activity and proficiency are measured on different axes.

### VI. Time-Zone Consistent Scheduling
All scheduled learning sessions, email notifications, summary submission deadlines, weekly/monthly period boundaries, and submission-status evaluations MUST be interpreted and evaluated using the user's configured local time zone. The system MUST persist a time zone per user and MUST apply it consistently across every scheduling, notification, and deadline decision. A submission deadline of "30 minutes after the scheduled end time" MUST be evaluated against the user's local clock.

**Rationale:** Reminders and deadlines that drift relative to the user's wall clock are worse than no reminders — they erode trust and cause real missed sessions. Time-zone correctness is a correctness requirement, not a UX nicety.

### VII. Progressive, Evidence-Based Difficulty Adaptation
The system MUST support a progressive learning path from A1 through C2. Difficulty increases MUST be gradual, evidence-based, and subject to the same content-validation rules defined in Principle II. The system MUST NOT raise the difficulty of an activity in a way that lacks an appropriate basis in the user's demonstrated progress. Recommended challenges (longer passages, more detailed writing, multi-concept integration, increased written expression complexity) MUST be appropriate to the user's current proficiency and demonstrated abilities. The system MUST prioritize sustainable progress and confidence building over abrupt acceleration.

**Rationale:** Sustainable progress keeps learners engaged for months, not days. The platform's success metric is the long arc from A1 to C2, not the impressiveness of any single generated activity.

### VIII. User Motivation and Positive Reinforcement
The system MUST recognize user achievements, highlight improvements, and recommend new learning challenges that are appropriate to the user's current proficiency level and demonstrated abilities. Recommendations MUST prioritize sustainable progress, confidence building, and continued engagement. The system MUST NOT introduce cognitive overload, discouragement, or abrupt difficulty increases.

**Rationale:** Motivation is what keeps the user returning to the next scheduled session. The platform's pedagogical quality and the user's continued engagement are co-dependent.

### IX. Separation of Responsibilities
The system MUST organize its functionality into components with clearly defined responsibilities and interfaces. At minimum, the following responsibilities MUST be separated: content generation, content evaluation, scheduling and notifications, summary intake and submission-status determination, learning-record persistence, reporting and recommendations, and the personalized AI assistant. Cross-cutting concerns (authentication, authorization, observability, configuration) MUST be explicit and shared through well-defined interfaces rather than duplicated per component.

**Rationale:** Clear boundaries make the system testable, maintainable, and auditable. They are also the prerequisite for independently evolving the generation and evaluation models without regressing quality.

### X. Observability and Failure Containment
The system MUST provide sufficient structured logging and monitoring to identify failures in notification delivery, summary submission, content generation, content evaluation, and other critical workflows. Failures MUST be contained so that a temporary problem in one workflow does not result in uncontrolled delivery of unapproved content, loss of learning records, or incorrect submission-status evaluation. The corrective retry loop for failed content validation MUST be bounded.

**Rationale:** AI orchestration, scheduled jobs, and email delivery are all failure-prone. The system must fail safely, surface the failure clearly, and never deliver unapproved content as a fallback.

## Non-Functional Standards

The system MUST satisfy the following non-functional standards at all times:

- **Reliability.** Scheduled notifications, summary submissions, learning-material generation, and validation workflows must be processed reliably. Failures must be handled so that temporary problems do not result in the uncontrolled delivery of unapproved content or the unintended loss of learning records.
- **Data Integrity.** User learning records, submission timestamps, submission statuses, and associated learning materials must remain internally consistent. The relationship between a scheduled session and its submitted summary must remain sufficiently clear to support accurate reporting and downstream material generation.
- **Security and Privacy.** User information and learning history must be protected through appropriate authentication, authorization, and data-protection mechanisms. Access to personal learning records MUST be restricted to authorized users and authorized internal processes.
- **Scalability.** The system MUST support an increasing number of users, scheduled sessions, notification requests, and AI content-generation operations without architectural rewrites.
- **Maintainability.** Each component MUST have a clearly defined responsibility and a stable interface so that functionality can be tested, maintained, and extended as requirements evolve.
- **Content Quality.** Relevance, accessibility, and proficiency-level alignment of generated learning materials are first-class quality requirements. Content validation MUST be treated as a critical quality gate, not an optional enhancement.

## Implementation Scope and Technology Neutrality

This constitution establishes the expected system behavior, functional responsibilities, business rules, and quality attributes of the `improve_lessons_backend`. The constitution intentionally does NOT prescribe specific implementation technologies, frameworks, or architectural solutions. The following decisions are deferred to the implementation phase and MUST be made in a way that supports the principles above without prematurely constraining the design:

- Database technology and persistence architecture.
- Internal data models and database schema.
- AI orchestration framework and integration mechanisms for the two-model content workflow.
- Context retrieval and management strategies for the personalized AI assistant.
- Background job scheduling and notification infrastructure.
- API authentication mechanisms and authorization architecture.
- Internal component organization, packaging, and deployment strategy.

Any technology decision that conflicts with a principle above is invalid regardless of its other merits.

## Development Workflow and Compliance Gates

The following gates MUST be satisfied for every change to the system:

- **Principle Compliance Review.** Every change MUST be reviewed against each of the ten Core Principles and the Non-Functional Standards. A change that violates a principle MUST NOT be merged.
- **Content Validation Gate.** Any change that touches the content-generation or content-evaluation workflow MUST include tests that demonstrate that a failing evaluation blocks delivery and that a bounded retry strategy terminates.
- **Submission-Status Gate.** Any change that touches summary intake, scheduling, or notifications MUST include tests that confirm the on-time vs late determination respects the user's time zone and the configured 30-minute submission window.
- **Time-Zone Gate.** Any change that touches scheduling, notifications, deadlines, or weekly/monthly period boundaries MUST include tests in at least two distinct time zones.
- **Activity-vs-Proficiency Gate.** Any change that touches progress indicators or reports MUST NOT introduce language that presents activity metrics as proficiency evidence.
- **Data Integrity Gate.** Any change that touches learning-record persistence MUST demonstrate that late submissions remain accessible, retain their late status, and continue to flow into downstream material generation.
- **Security Gate.** Any change that touches authentication, authorization, or personal data MUST be reviewed for access-control correctness and protection of learning history.
- **Observability Gate.** Any change that touches a critical workflow (notifications, summary submission, content generation, content evaluation) MUST include structured logging that supports failure diagnosis.

## Governance

This constitution is the supreme governance document for the `improve_lessons_backend` project. It supersedes all other practices, conventions, and ad-hoc decisions. Where a conflict exists between this constitution and any other artifact (specification, plan, task, code review, or implementation choice), this constitution prevails.

**Amendment Procedure.**
1. Propose the amendment in writing, identifying the principle(s) affected, the rationale, and the impact on existing functionality.
2. Record the proposed change in a Sync Impact Report appended to the constitution file.
3. Update the constitution in a single, atomic commit. Update the version, ratification, and last-amended metadata.
4. Re-run the principle compliance review against the amended constitution before resuming feature work.

**Versioning Policy.** The constitution follows semantic versioning:
- **MAJOR** — backward-incompatible governance changes: removal or redefinition of a principle.
- **MINOR** — addition of a new principle or material expansion of existing guidance.
- **PATCH** — clarifications, wording improvements, and non-semantic refinements.

**Compliance Review.** All pull requests, code reviews, and design proposals MUST verify compliance with the ten Core Principles and the Non-Functional Standards. Complexity that is not justified by a principle or a documented requirement MUST be rejected. Where runtime guidance is needed beyond this constitution, refer to the project's specifications, plans, and tasks.

**Version**: 1.0.0 | **Ratified**: 2026-10-13 | **Last Amended**: 2026-10-13

# PawCare AI - Development Workflow

Status: Draft / Active Workflow  
Purpose: Define the PDCA loop for AI-assisted development, code changes, tests, documentation updates, and git commits.
Depends On: `docs/constitution.md`, `docs/state_schema.md`, `docs/agents_definition.md`, `docs/guidelines.md`, `docs/test_cases.md`
Dependency Rule: Code changes must preserve safety rules, state contracts, agent boundaries, guideline grounding, and test coverage.

This project uses a lightweight PDCA loop so AI-assisted development stays deliberate, testable, and easy to roll back.

---

## 1. Core Rule

Think before changing. Change in small steps. Check after each step. Commit stable checkpoints.

Every meaningful change should have:

- a clear purpose
- known affected layers
- relevant tests
- safety review
- small git checkpoint

---

## 2. PDCA Loop

### Plan

Before changing code, identify:

- What user/product behavior is being added or changed?
- Which backend layer is affected?
- Which docs are affected?
- Which test cases should pass or be added?
- Does the change affect safety, diagnosis, medication advice, or guideline grounding?

Do not start broad rewrites without answering these questions.

### Do

Implement in small, reversible steps.

Rules:

- Keep changes scoped to the affected layer.
- Do not mix unrelated refactors with behavior changes.
- Do not let Worker Agents mutate global State directly.
- Do not add recommendation behavior without `source_guideline_ids`.
- Do not bypass Safety Agent for user-facing outputs.

### Check

After implementation:

- Run tests.
- Confirm schema validation still works.
- Confirm safety constraints still hold.
- Confirm new behavior maps to `docs/test_cases.md`.
- Confirm new recommendation logic cites `docs/guidelines.md`.
- Confirm final user response does not expose internal fields like `proposed_update`.

Minimum command:

```bash
pytest -q
```

### Act

After checks pass:

- Update documentation if behavior changed.
- Add or update test cases if a new scenario was introduced.
- Commit a small checkpoint.
- Push when the checkpoint is stable.

---

## 3. Layer Ownership

| Layer | Purpose | Change When |
| --- | --- | --- |
| `schemas` | Pydantic contracts and typed state | State shape, enum, response shape changes |
| `knowledge` | Guideline Knowledge Base | Recommendation grounding changes |
| `skills` | Narrow structured tools | Extraction, retrieval, or transformation logic changes |
| `agents` | Specialist reasoning workers | Health, behavior, safety, communication logic changes |
| `coordinator` | Orchestration and global State merging | Routing, active context, merge policy changes |
| `services` | Product-facing workflows | User-facing flow or response behavior changes |
| `storage` | Persistence | Redis/Postgres/session storage changes |
| `api` | HTTP interface | FastAPI routes or request/response API changes |
| `evaluation` | Automated scenario testing | 50+ scenario runner and metrics changes |

The existing regression tests act as a lightweight golden set for core behavior.
The formal JSON Golden Data Set is the drift check used when agent, prompt,
retrieval, care-context, or safety behavior changes.

---

## 4. Safety Checklist

Before merging or committing recommendation behavior, verify:

- No diagnosis is produced.
- No medication dosage is produced.
- No "don't worry" / "it will be fine" style over-reassurance is produced.
- `source_guideline_ids` is present for safety-relevant output.
- Moderate or higher risk includes escalation conditions.
- User-facing response hides internal `agent_outputs` and `proposed_update`.
- Worker Agents return `proposed_update`; Coordinator owns global State merges.

---

## 5. Git Discipline

Use small commits.

Good examples:

```text
Add Pydantic state schema
Add rule-based LogExtractor skill
Add BehaviorAgent social stress evaluation
Add guideline knowledge base
Add LogProcessingService user response layer
```

Avoid:

```text
big update
fix stuff
misc changes
```

Suggested rhythm:

```text
1 feature or layer change
-> tests pass
-> commit
-> push
```

If something breaks, prefer reverting a small commit over untangling a large uncommitted change set.

---

## 6. When To Update Docs

Update `docs/state_schema.md` when:

- a State field changes
- an enum changes
- active context changes
- response shape changes

Update `docs/agents_definition.md` when:

- an agent responsibility changes
- handoff changes
- Worker isolation changes
- Coordinator merge rules change

Update `docs/guidelines.md` when:

- a new recommendation rule is added
- a new guideline ID is used
- source grounding changes

Update `docs/test_cases.md` when:

- a new user scenario is supported
- a safety failure mode is found
- a regression needs to be locked down

Update `docs/constitution.md` only when:

- safety policy changes
- tone rules change
- non-diagnostic boundaries change

---

## 7. AI Collaboration Prompt

When asking an AI coding assistant to change the project, prefer this format:

```text
Goal:
Add [feature].

Relevant docs:
- docs/constitution.md
- docs/state_schema.md
- docs/guidelines.md
- docs/test_cases.md

Constraints:
- Preserve Worker isolation.
- Return structured output.
- Add tests.
- Run pytest.
- Keep the change small.
```

This keeps the AI from guessing the project rules from memory.

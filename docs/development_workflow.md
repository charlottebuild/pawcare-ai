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

The Golden Data Set is contract-based rather than word-for-word. Each scenario
stores a realistic user message, pet profile, target layer, category, priority,
metrics, and expected safety/product contract. The runner checks risk
classification, guideline grounding, forbidden diagnostic or medication wording,
care-context retrieval, and API privacy boundaries. This lets the project
measure drift without making every response sentence brittle.

Interview summary:

> I built a contract-based Golden Dataset for PawCare instead of relying on
> manual testing. Each case contains a realistic user message, pet profile,
> target layer, and expected safety contract. I do not require exact wording
> because AI responses can change, but I check the important guarantees: risk
> level, guideline grounding, forbidden diagnostic language, care-context
> retrieval, and API privacy boundaries.
>
> The dataset is grouped by category, such as health triage, condition triage,
> behavior safety, normal updates, and care-context retrieval. The runner
> replays cases through both the core service layer and the FastAPI product
> layer, then reports pass rates by category and metric. This lets me detect
> drift when I change agents, retrieval, prompts, or symptom parsing.
>
> For example, cases like "cat didn't pee all day," "poo blood," "eye injury,"
> or "could it be salivary mucocele" must trigger the right urgency and
> references, while normal updates like "ate breakfast normally" must not
> over-trigger scary care cards. So the golden set protects both safety and
> user experience.

Evaluation observability:

- Relevance is measured through semantic contracts: correct guideline IDs for
  final responses and correct care-context domains for professional references
  or similar cases.
- Hallucination safety is measured as a guardrail pass rate for forbidden
  diagnosis, medication, over-reassurance, or unsafe case-based claims. This is
  not a full human-labeled hallucination-rate benchmark.
- Latency is measured as end-to-end case duration in the golden runner. TTFT is
  not measured until the product adds streaming responses.
- Cost telemetry is optional. Local deterministic runs report unavailable usage;
  OpenAI-backed summarization or screening can record provider usage when the
  response includes token counts.
- Streaming is status-event streaming, not raw medical token streaming. The
  product may emit safe progress events before the final answer, but the final
  user-facing response is sent only after the Coordinator and SafetyAgent have
  finished.
- LLM response polishing is optional and limited to wording. It can rewrite the
  already structured `UserResponse.message`, but it cannot change status, risk
  band, guideline IDs, or escalation conditions. Unsafe polish output falls back
  to the deterministic response.

Interview summary:

> I evaluate AI behavior with both quality contracts and operational telemetry.
> The Golden Dataset checks semantic contracts like risk triage, guideline
> grounding, forbidden diagnostic language, retrieval relevance, and API
> boundaries. Then the eval runner records latency and optional LLM usage, so I
> can detect both behavioral regressions and cost or performance regressions
> after prompt, retrieval, or agent changes. I am careful not to call this a
> full human-labeled hallucination benchmark or true TTFT measurement until the
> app has token-level streaming instrumentation. For now, PawCare streams safe
> workflow status events and sends final medical guidance only after safety
> review.

MCP sidecar:

- `pawcare.mcp_server` exposes PawCare capabilities as local MCP tools for
  external AI clients and coding agents.
- `PawCareMCPToolRegistry` is the controlled allowlist for MCP tools. Each tool
  declares a description, permission, handler, and safety metadata.
- The MCP layer is read-only in v1. It can screen abnormal signals, retrieve
  care context, preview a safe response, and run the Golden Dataset.
- MCP tools must not append observations, mutate pet profiles, write SQLite
  state, crawl third-party platforms, or expose internal `agent_outputs`,
  `proposed_update`, or `safety_review` payloads.
- Product traffic still flows through FastAPI and `PetMessageService`; MCP is a
  structured tool interface beside the product API, not a replacement.

Interview summary:

> I added a local MCP sidecar so PawCare's stable safety and retrieval
> capabilities can be called by external AI clients as structured tools. The
> tools are registered through an explicit allowlist with permission metadata,
> not dynamic discovery. They are intentionally read-only: they can screen
> abnormal signals, retrieve non-diagnostic care context, preview the safe
> response chain, and run the Golden Dataset, but they cannot mutate user pet
> records or bypass the Coordinator/Safety workflow. This gives the project
> MCP-style extensibility while preserving deterministic safety boundaries.

Long-term memory maintenance:

- `python -m pawcare.memory.summary_worker --db pawcare.local.sqlite3` rebuilds
  daily, weekly, and monthly pet summaries from SQLite observations.
- The command supports full database rebuilds, per-user rebuilds, per-pet
  rebuilds, and dry runs.
- It is intentionally offline/manual in v1. Future cron jobs, FastAPI
  background tasks, or production queues should reuse the same rebuild function
  rather than duplicating summary logic.

Interview summary:

> PawCare has the summary worker logic implemented as an offline rebuild
> command. I chose this before adding a production scheduler because the current
> app is SQLite-backed and local-first. The important part is that raw
> observations can be compressed into daily, weekly, and monthly pet memory
> summaries; production scheduling is a deployment concern that can be added
> later with cron or a queue once the infrastructure exists.

Semantic care-context cache:

- PawCare may cache non-diagnostic care context for semantically similar symptom
  queries, using canonical signals plus pet context.
- Cached payloads can include professional references, similar cases, context
  summary, and the non-diagnostic notice.
- Cached payloads must not include final `UserResponse` fields such as status,
  risk band, guideline IDs, escalation conditions, or user-facing final
  medical guidance.

Interview summary:

> I use semantic caching for retrieval context, not final medical decisions.
> Similar symptom queries like "poo blood" and "bloody stool" can reuse the same
> professional references, similar cases, and context summary, which avoids
> repeating retrieval and summarization work. But the final response still runs
> through the current pet state, Coordinator, and SafetyAgent, so cached context
> cannot replace triage or escalation logic.

Cost benchmark:

- `python -m pawcare.evaluation.cost_benchmark` runs a local semantic-cache
  benchmark over repeated care-context scenarios.
- The report includes cache hit rate, avoided retrieval calls, avoided
  summarizer calls, estimated context tokens saved, and latency.
- Token savings are deterministic estimates for comparison, not OpenAI billing
  data.

Interview summary:

> I do not just assume semantic caching saves money. I benchmark it. The local
> cost runner replays repeated symptom questions, measures cache hits and
> misses, estimates avoided retrieval/summarization payload tokens, and reports
> latency. This lets me discuss cost optimization with concrete engineering
> telemetry while being honest that v1 estimates context-token savings rather
> than real provider billing.

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

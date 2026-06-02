# PawCare AI - Model Spec Index

Status: Draft / Active Guidelines  
Principle: LLMs are non-deterministic components. Engineering rigor is non-negotiable.

PawCare AI is a multi-agent, skill-driven dog care assistant for real-world dog sitting scenarios. It models each dog as a long-running entity with structured logs, behavioral baselines, social observations, and safety-aware recommendations.

This root file is intentionally short so AI coding tools can load it quickly. The detailed project rules live in `docs/`.

Start with `docs/manifest.md` for the full document map.

---

## Read First

1. `docs/constitution.md`
   - Non-diagnostic rule
   - Safety-first bias
   - Grounding requirement
   - Tone and behavior policy

2. `docs/state_schema.md`
   - Shared state object
   - JSON contracts
   - Dog, event, pattern, handoff, and recommendation structures
   - Social context fields such as body language, resource guarding, and multi-dog interaction signals

3. `docs/agents_definition.md`
   - Orchestrator-Worker pattern
   - Care Coordinator responsibilities
   - Health, Behavior, Safety, and Communication Agent boundaries
   - Handoff and active-context rules

4. `docs/test_cases.md`
   - Edge cases for health, behavior, social interaction, safety, and schema validation
   - Required evaluation set before changing agent or skill behavior

5. `docs/guidelines.md`
   - Approved guideline IDs for health, medication safety, post-op recovery, social behavior, and owner communication
   - Required source layer for grounded recommendations

6. `docs/development_workflow.md`
   - PDCA loop for AI-assisted development
   - Small-step implementation, test checks, documentation updates, and git discipline

---

## North Star

PawCare AI should help pet sitters become more observant, consistent, and prepared.

It must not diagnose. It must not provide medication instructions. It must not invent unsupported breed or medical claims. It should help humans notice patterns, communicate clearly, and escalate when safety calls for it.

---

## Try It Locally

Install the package with dev dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the full test suite:

```bash
pytest -q
```

Run the product demo entrypoint:

```bash
PYTHONPATH=backend/src python -m pawcare.demo "Mochi barely touched breakfast."
```

The demo seeds one user with two pets, sends a message for `dog_mochi`, returns the safe user-facing response, and reports which observations were stored.

Run the local app with SQLite persistence:

```bash
uvicorn --factory pawcare.api:create_local_app --reload
```

Then open `http://127.0.0.1:8000/app`. The local app stores users, pet profiles, and observations in `pawcare.local.sqlite3` so friend-testing data survives process restarts.

The FastAPI app factory is available at `pawcare.api:create_app`. That default factory still uses an in-memory repository for tests and demos; `create_local_app` is the local/friend-testing entrypoint.

---

## Vibe Coding Rule

Before changing agent behavior, skill contracts, workflow state, or recommendation logic:

1. Update `docs/state_schema.md` if any state shape changes.
2. Update `docs/agents_definition.md` if any agent responsibility changes.
3. Update `docs/constitution.md` if any safety or tone rule changes.
4. Update `docs/guidelines.md` if recommendation grounding changes.
5. Add or update edge cases in `docs/test_cases.md` when behavior changes.
6. Follow `docs/development_workflow.md`: Plan, Do, Check, Act, then commit small.

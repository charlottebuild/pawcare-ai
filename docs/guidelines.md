# PawCare AI - Guideline Knowledge Base

Status: Draft / Active Knowledge Source  
Purpose: Define approved guideline IDs that agents may cite in `source_guideline_ids`.
Depends On: `docs/constitution.md`, `docs/state_schema.md`, `docs/agents_definition.md`
Dependency Rule: Guidelines support risk classification, monitoring, and escalation language. They must not be used to produce diagnosis or medication dosage advice.

This file is the approved care-knowledge layer for PawCare AI. Agents should cite these IDs instead of relying on unsupported model knowledge.

---

## 1. Guideline Taxonomy

| Type | Purpose | Primary Users |
| --- | --- | --- |
| `health_observation` | General symptoms and physical observations | Health Agent, Coordinator |
| `medication_safety` | Medication side-effect and unsafe-medication rules | Health Agent, Safety Agent |
| `post_op_recovery` | Surgery and recovery monitoring | Health Agent, future Recovery Agent |
| `behavior_social_safety` | Stress, play, resource guarding, social conflict | Behavior Agent |
| `owner_communication` | Safe owner-facing wording | Communication Agent, Safety Agent |

---

## 2. Health Observation Guidelines

### GL_STOOL_001

Type: `health_observation`  
Topic: Stool quality and diarrhea monitoring  
Signals:

- soft stool
- loose stool
- watery diarrhea
- repeated diarrhea
- bloody stool
- black or tarry stool
- stool frequency change

Guidance:

- A single soft stool with normal appetite and energy may be monitored.
- Repeated watery diarrhea, bloody stool, black/tarry stool, or diarrhea with lethargy, vomiting, or appetite loss should increase risk and trigger owner/vet escalation language.

Allowed recommendation:

```text
Monitor stool quality and frequency. If diarrhea repeats, becomes bloody or black/tarry, or appears with vomiting, lethargy, or appetite loss, contact the owner or a veterinarian.
```

Forbidden:

```text
This is definitely just a stomach bug.
```

Sources:

- FDA, Veterinary NSAID side-effect monitoring: https://www.fda.gov/animal-veterinary/product-safety-information/veterinary-nonsteroidal-anti-inflammatory-drugs-nsaids
- FDA, Pain relievers for pets and digestive side effects: https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets

### GL_APPETITE_002

Type: `health_observation`  
Topic: Appetite decrease  
Signals:

- eating less
- skipped meal
- refused food
- suddenly lower appetite

Guidance:

- Appetite changes must be compared against baseline.
- A food-motivated dog refusing food is more concerning than a dog with a variable appetite.
- Appetite loss combined with vomiting, diarrhea, lethargy, medication use, or post-op recovery should increase risk.

Allowed recommendation:

```text
Record the next meal, energy level, water intake, stool, and vomiting status. Notify the owner if appetite remains below baseline or appears with other concerning signs.
```

### GL_VOMITING_001

Type: `health_observation`  
Topic: Vomiting monitoring  
Signals:

- vomiting
- repeated vomiting
- vomiting with diarrhea
- vomiting with lethargy
- vomiting with appetite loss

Guidance:

- Vomiting should be recorded with frequency, timing, appetite, energy, and stool context.
- Vomiting combined with diarrhea, lethargy, refusal to eat/drink, or worsening condition should trigger escalation language.

Allowed recommendation:

```text
Record vomiting frequency and monitor appetite, water intake, stool, and energy. If vomiting repeats, worsens, or appears with diarrhea, lethargy, or refusal to eat/drink, contact the owner or a veterinarian.
```

Sources:

- FDA, NSAID side effects include vomiting and digestive signs: https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets

### GL_LETHARGY_001

Type: `health_observation`  
Topic: Activity decrease and lethargy  
Signals:

- lying down more than usual
- decreased activity
- unwilling to walk
- won't get up
- unusually tired

Guidance:

- Activity decrease should be compared against baseline.
- Lethargy combined with vomiting, diarrhea, appetite loss, medication use, or post-op recovery should raise risk.

Allowed recommendation:

```text
Compare activity to baseline and monitor whether the pet can rise, walk, eat, drink, and respond normally. Escalate if activity remains reduced or combines with other concerning signs.
```

### GL_LAMENESS_001

Type: `health_observation`  
Topic: Limping and weight-bearing  
Signals:

- limping
- unwilling to put paw down
- non-weight-bearing
- trouble rising
- stiffness
- sudden mobility decrease

Guidance:

- Limping and non-weight-bearing should be compared to baseline and recent activity.
- Sudden non-weight-bearing, worsening lameness, pain signs, or post-op lameness changes should trigger owner/vet escalation language.

Allowed recommendation:

```text
Record which limb is affected, whether the pet can bear weight, when it started, and whether pain, swelling, or activity decrease is present. Contact the owner or veterinarian if lameness is sudden, severe, worsening, or post-operative.
```

Sources:

- ACVS, Cranial cruciate ligament disease signs include lameness, stiffness, pain, and difficulty rising: https://www.acvs.org/es/small-animal/partial-acl-injury/

---

## 3. Medication Safety Guidelines

### GL_NSAID_SIDE_EFFECT_001

Type: `medication_safety`  
Topic: NSAID side-effect monitoring  
Signals:

- vomiting
- diarrhea
- bloody stool
- black or tarry stool
- decreased appetite
- decreased activity
- yellow gums, skin, or eyes

Guidance:

- NSAIDs can cause digestive, kidney, and liver side effects.
- If side-effect signs appear while taking NSAIDs, the system should recommend contacting the owner/veterinarian.
- The system must not give dose changes or medication stop/start instructions unless quoting owner/vet instructions already recorded in state. Even then, it should direct confirmation with the veterinarian.

Allowed recommendation:

```text
Because these signs appeared during medication use, contact the owner or veterinarian promptly and follow the prescribing veterinarian's instructions.
```

Forbidden:

```text
Give a lower dose tomorrow.
```

Sources:

- FDA, Veterinary NSAIDs and reported side effects: https://www.fda.gov/animal-veterinary/product-safety-information/veterinary-nonsteroidal-anti-inflammatory-drugs-nsaids
- FDA, What to monitor while pets take NSAIDs: https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets

### GL_MEDICATION_SAFETY_001

Type: `medication_safety`  
Topic: No human medication or dosage advice  
Signals:

- user asks about human medication
- user asks dosage
- user asks whether to give OTC pain reliever
- user asks to adjust prescribed medication

Guidance:

- Do not provide medication dosage.
- Do not recommend human OTC medication.
- Recommend contacting the owner or veterinarian for medication decisions.

Allowed recommendation:

```text
I can't provide medication or dosage instructions. Contact the owner or veterinarian before giving or changing any medication.
```

Sources:

- FDA, no over-the-counter NSAIDs for dogs/cats are FDA-approved and pet owners should talk with a veterinarian: https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets

---

## 4. Post-Op Recovery Guidelines

### GL_ACL_POSTOP_001

Type: `post_op_recovery`  
Topic: ACL/CCL recovery monitoring  
Signals:

- recent ACL/CCL/TPLO/TTA surgery
- limping
- non-weight-bearing
- stiffness
- trouble rising
- decreased activity
- pain signs

Guidance:

- Post-operative care at home is critical.
- Activity restriction is commonly part of recovery after cruciate surgery.
- Continued or worsening lameness, pain, inability to bear weight, sudden deterioration, or signs of complications should trigger owner/vet escalation language.

Allowed recommendation:

```text
Record weight-bearing, pain signs, activity level, and any sudden changes. If the pet cannot bear weight, worsens, or seems painful, contact the owner or surgical veterinarian.
```

Sources:

- ACVS, cranial cruciate ligament disease aftercare and complications: https://www.acvs.org/es/small-animal/partial-acl-injury/

### GL_POSTOP_INCISION_001

Type: `post_op_recovery`  
Topic: Incision and surgical-site monitoring  
Signals:

- redness
- swelling
- discharge
- bleeding
- odor
- licking incision
- opening incision
- fever-like signs

Guidance:

- Surgical incision changes should be documented and escalated to the owner/veterinarian.
- The system must not diagnose infection.

Allowed recommendation:

```text
Record incision appearance and prevent licking if this is part of the vet's instructions. Contact the owner or veterinarian if redness, swelling, discharge, bleeding, odor, opening, or worsening pain appears.
```

### GL_ACTIVITY_RESTRICTION_001

Type: `post_op_recovery`  
Topic: Activity restriction during recovery  
Signals:

- running
- jumping
- stairs
- rough play
- off-leash activity
- post-op overactivity

Guidance:

- If post-op instructions include activity restriction, the system should monitor and remind sitters to avoid unapproved running, jumping, stairs, and rough play.
- The system should not invent a specific rehab plan.

Allowed recommendation:

```text
Follow the veterinarian's activity restriction instructions. Avoid unapproved running, jumping, stairs, or rough play during the restricted period.
```

Sources:

- ACVS, post-operative activity restriction after cruciate surgery: https://www.acvs.org/es/small-animal/partial-acl-injury/

---

## 5. Behavior and Social Safety Guidelines

### GL_SOCIAL_STRESS_001

Type: `behavior_social_safety`  
Topic: Subtle stress signals  
Signals:

- lip licking
- yawning
- whale eye
- freezing
- stiff body
- turning away
- avoidance
- tucked or lowered tail
- ears back

Guidance:

- Subtle stress signals should be preserved in state.
- Lack of growling does not prove comfort.
- Increase distance or reduce pressure when repeated stress signals appear.

### GL_RESOURCE_GUARDING_001

Type: `behavior_social_safety`  
Topic: Resource proximity and guarding  
Signals:

- food, chew, toy, bed, crate, doorway, human attention, or water bowl involved
- freezing near a resource
- stiff body near a resource
- hovering or blocking
- growling
- air snap

Guidance:

- Resource contexts increase social risk.
- Separate pets around high-value resources when stress or escalation signs appear.
- Do not label the pet as permanently aggressive from a single event.

### GL_SOCIAL_PLAY_001

Type: `behavior_social_safety`  
Topic: Appropriate play signals  
Signals:

- play bow
- loose body
- turn-taking
- chase-and-pause
- ability to disengage

Guidance:

- Reassuring play signals may lower risk when no stress, injury, or one-sided pressure is present.
- Continue monitoring and interrupt if play becomes one-sided or stress signals appear.

### GL_SOCIAL_SAFETY_001

Type: `behavior_social_safety`  
Topic: Escalating social conflict  
Signals:

- growling
- snapping
- air snap
- lunging
- bite
- yelp
- inability to relax after separation

Guidance:

- Escalation signals should trigger immediate management and owner notification language.
- Separate pets calmly and avoid shared resources until reviewed.

---

## 6. Owner Communication Guidelines

### GL_OWNER_COMMUNICATION_001

Type: `owner_communication`  
Topic: Owner-facing update structure  
Guidance:

- State what was observed.
- State what is being monitored.
- State what would trigger escalation.
- Avoid diagnosis and unsupported certainty.

### GL_NON_DIAGNOSTIC_LANGUAGE_001

Type: `owner_communication`  
Topic: Non-diagnostic wording  
Guidance:

- Use risk profile and observed signs.
- Do not name a disease as fact.

Allowed:

```text
These signs match a higher-risk profile and should be discussed with a veterinarian.
```

Forbidden:

```text
Your dog has parvo.
```

### GL_ESCALATION_LANGUAGE_001

Type: `owner_communication`  
Topic: Escalation wording  
Guidance:

- For moderate or higher risk, include concrete escalation conditions.
- Avoid "don't worry" and "it will be fine."

Allowed:

```text
If symptoms continue, worsen, or combine with lethargy, vomiting, blood, or refusal to eat/drink, contact the owner or veterinarian.
```

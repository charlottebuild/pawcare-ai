from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GuidelineType(str, Enum):
    health_observation = "health_observation"
    medication_safety = "medication_safety"
    post_op_recovery = "post_op_recovery"
    behavior_social_safety = "behavior_social_safety"
    owner_communication = "owner_communication"


class Guideline(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: GuidelineType
    topic: str
    signals: tuple[str, ...] = Field(default_factory=tuple)
    guidance: str
    allowed_recommendation: str | None = None
    forbidden_examples: tuple[str, ...] = Field(default_factory=tuple)
    sources: tuple[str, ...] = Field(default_factory=tuple)


GUIDELINES: tuple[Guideline, ...] = (
    Guideline(
        id="GL_STOOL_001",
        type=GuidelineType.health_observation,
        topic="Stool quality and diarrhea monitoring",
        signals=(
            "soft_stool",
            "loose_stool",
            "watery_diarrhea",
            "repeated_diarrhea",
            "bloody_stool",
            "black_tarry_stool",
            "stool_frequency_change",
        ),
        guidance=(
            "A single soft stool with normal appetite and energy may be monitored. "
            "Repeated watery diarrhea, bloody stool, black/tarry stool, or diarrhea "
            "with lethargy, vomiting, or appetite loss should increase risk."
        ),
        allowed_recommendation=(
            "Monitor stool quality and frequency. If diarrhea repeats, becomes bloody "
            "or black/tarry, or appears with vomiting, lethargy, or appetite loss, "
            "contact the owner or a veterinarian."
        ),
        forbidden_examples=("This is definitely just a stomach bug.",),
        sources=(
            "https://www.fda.gov/animal-veterinary/product-safety-information/veterinary-nonsteroidal-anti-inflammatory-drugs-nsaids",
            "https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets",
        ),
    ),
    Guideline(
        id="GL_APPETITE_002",
        type=GuidelineType.health_observation,
        topic="Appetite decrease",
        signals=("eating_less", "skipped_meal", "refused_food", "low_appetite"),
        guidance=(
            "Appetite changes must be compared against baseline. Appetite loss combined "
            "with vomiting, diarrhea, lethargy, medication use, or post-op recovery "
            "should increase risk."
        ),
        allowed_recommendation=(
            "Record the next meal, energy level, water intake, stool, and vomiting status. "
            "Notify the owner if appetite remains below baseline or appears with other concerning signs."
        ),
    ),
    Guideline(
        id="GL_VOMITING_001",
        type=GuidelineType.health_observation,
        topic="Vomiting monitoring",
        signals=("vomiting", "repeated_vomiting", "vomiting_with_diarrhea", "vomiting_with_lethargy"),
        guidance=(
            "Vomiting should be recorded with frequency, timing, appetite, energy, and stool context. "
            "Vomiting combined with diarrhea, lethargy, refusal to eat/drink, or worsening condition "
            "should trigger escalation language."
        ),
        allowed_recommendation=(
            "Record vomiting frequency and monitor appetite, water intake, stool, and energy. "
            "If vomiting repeats, worsens, or appears with diarrhea, lethargy, or refusal to eat/drink, "
            "contact the owner or a veterinarian."
        ),
        sources=(
            "https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets",
        ),
    ),
    Guideline(
        id="GL_LETHARGY_001",
        type=GuidelineType.health_observation,
        topic="Activity decrease and lethargy",
        signals=("decreased_activity", "lethargy", "wont_get_up", "unusually_tired"),
        guidance=(
            "Activity decrease should be compared against baseline. Lethargy combined with "
            "vomiting, diarrhea, appetite loss, medication use, or post-op recovery should raise risk."
        ),
        allowed_recommendation=(
            "Compare activity to baseline and monitor whether the pet can rise, walk, eat, drink, "
            "and respond normally. Escalate if activity remains reduced or combines with other concerning signs."
        ),
    ),
    Guideline(
        id="GL_LAMENESS_001",
        type=GuidelineType.health_observation,
        topic="Limping and weight-bearing",
        signals=("limping", "non_weight_bearing", "trouble_rising", "stiffness", "sudden_mobility_decrease"),
        guidance=(
            "Limping and non-weight-bearing should be compared to baseline and recent activity. "
            "Sudden non-weight-bearing, worsening lameness, pain signs, or post-op lameness changes "
            "should trigger owner/vet escalation language."
        ),
        allowed_recommendation=(
            "Record which limb is affected, whether the pet can bear weight, when it started, "
            "and whether pain, swelling, or activity decrease is present. Contact the owner or veterinarian "
            "if lameness is sudden, severe, worsening, or post-operative."
        ),
        sources=("https://www.acvs.org/es/small-animal/partial-acl-injury/",),
    ),
    Guideline(
        id="GL_NSAID_SIDE_EFFECT_001",
        type=GuidelineType.medication_safety,
        topic="NSAID side-effect monitoring",
        signals=(
            "vomiting",
            "diarrhea",
            "bloody_stool",
            "black_tarry_stool",
            "decreased_appetite",
            "decreased_activity",
            "yellow_gums_skin_eyes",
        ),
        guidance=(
            "NSAIDs can cause digestive, kidney, and liver side effects. If side-effect signs appear "
            "while taking NSAIDs, recommend contacting the owner or veterinarian. Do not give dose changes."
        ),
        allowed_recommendation=(
            "Because these signs appeared during medication use, contact the owner or veterinarian promptly "
            "and follow the prescribing veterinarian's instructions."
        ),
        forbidden_examples=("Give a lower dose tomorrow.",),
        sources=(
            "https://www.fda.gov/animal-veterinary/product-safety-information/veterinary-nonsteroidal-anti-inflammatory-drugs-nsaids",
            "https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets",
        ),
    ),
    Guideline(
        id="GL_MEDICATION_SAFETY_001",
        type=GuidelineType.medication_safety,
        topic="No human medication or dosage advice",
        signals=("human_medication_request", "dosage_request", "otc_pain_reliever_request"),
        guidance=(
            "Do not provide medication dosage, recommend human OTC medication, or suggest medication changes. "
            "Recommend contacting the owner or veterinarian."
        ),
        allowed_recommendation=(
            "I can't provide medication or dosage instructions. Contact the owner or veterinarian before giving "
            "or changing any medication."
        ),
        sources=(
            "https://www.fda.gov/animal-veterinary/animal-health-literacy/get-facts-about-pain-relievers-pets",
        ),
    ),
    Guideline(
        id="GL_ACL_POSTOP_001",
        type=GuidelineType.post_op_recovery,
        topic="ACL/CCL recovery monitoring",
        signals=("acl_surgery", "ccl_surgery", "tplo", "tta", "limping", "non_weight_bearing", "pain_signs"),
        guidance=(
            "Post-operative care at home is critical. Continued or worsening lameness, pain, inability to bear "
            "weight, sudden deterioration, or signs of complications should trigger owner/vet escalation language."
        ),
        allowed_recommendation=(
            "Record weight-bearing, pain signs, activity level, and any sudden changes. If the pet cannot bear "
            "weight, worsens, or seems painful, contact the owner or surgical veterinarian."
        ),
        sources=("https://www.acvs.org/es/small-animal/partial-acl-injury/",),
    ),
    Guideline(
        id="GL_POSTOP_INCISION_001",
        type=GuidelineType.post_op_recovery,
        topic="Incision and surgical-site monitoring",
        signals=("redness", "swelling", "discharge", "bleeding", "odor", "licking_incision", "opening_incision"),
        guidance=(
            "Surgical incision changes should be documented and escalated to the owner/veterinarian. "
            "Do not diagnose infection."
        ),
        allowed_recommendation=(
            "Record incision appearance and prevent licking if this is part of the vet's instructions. "
            "Contact the owner or veterinarian if redness, swelling, discharge, bleeding, odor, opening, "
            "or worsening pain appears."
        ),
    ),
    Guideline(
        id="GL_ACTIVITY_RESTRICTION_001",
        type=GuidelineType.post_op_recovery,
        topic="Activity restriction during recovery",
        signals=("running", "jumping", "stairs", "rough_play", "off_leash_activity", "post_op_overactivity"),
        guidance=(
            "If post-op instructions include activity restriction, monitor and remind sitters to avoid unapproved "
            "running, jumping, stairs, and rough play. Do not invent a specific rehab plan."
        ),
        allowed_recommendation=(
            "Follow the veterinarian's activity restriction instructions. Avoid unapproved running, jumping, stairs, "
            "or rough play during the restricted period."
        ),
        sources=("https://www.acvs.org/es/small-animal/partial-acl-injury/",),
    ),
    Guideline(
        id="GL_CONDITION_GI_001",
        type=GuidelineType.health_observation,
        topic="GI condition triage",
        signals=("condition_gi", "vomiting", "diarrhea", "low_appetite", "gastroenteritis_question", "parvo_question"),
        guidance=(
            "GI signs can have many causes. Discuss possible categories such as dietary upset, gastroenteritis, "
            "parasites, foreign material, medication side effects, or infectious disease with a veterinarian. "
            "Do not diagnose a disease from the app."
        ),
        allowed_recommendation=(
            "I can't diagnose from the app, but vomiting, diarrhea, appetite change, blood, black stool, lethargy, "
            "or dehydration are reasons to contact a veterinarian. Record timing, frequency, stool quality, appetite, "
            "water intake, energy, medication use, and possible exposures."
        ),
        forbidden_examples=("Your dog has gastroenteritis.", "This is parvo."),
    ),
    Guideline(
        id="GL_CONDITION_ORAL_NECK_001",
        type=GuidelineType.health_observation,
        topic="Oral or neck swelling triage",
        signals=("condition_oral_neck", "drooling", "jaw_lump", "neck_lump", "salivary_mucocele_question", "oral_pain"),
        guidance=(
            "Drooling, oral pain, jaw swelling, or neck swelling should be framed as possible categories to discuss "
            "with a veterinarian, such as salivary mucocele, dental/oral disease, trauma, abscess, lymph node swelling, "
            "or another mass. Do not diagnose the cause."
        ),
        allowed_recommendation=(
            "I can't diagnose from the app. Record the swelling location, size, firmness, whether it moves, pain, "
            "drooling, eating or swallowing changes, breath odor, and speed of growth. Vet evaluation is appropriate, "
            "and urgent care is warranted if breathing, swallowing, bleeding, severe pain, or rapid enlargement appears."
        ),
        forbidden_examples=("Your dog has a salivary mucocele.",),
    ),
    Guideline(
        id="GL_CONDITION_MOBILITY_001",
        type=GuidelineType.health_observation,
        topic="Mobility condition triage",
        signals=("condition_mobility", "limping", "non_weight_bearing", "pain_signs", "post_op_context"),
        guidance=(
            "Mobility questions should identify possible categories for veterinary discussion, such as strain, joint "
            "injury, paw injury, post-operative complication, or pain, without diagnosing."
        ),
        allowed_recommendation=(
            "Record which limb, weight-bearing ability, pain signs, swelling, activity changes, timing, and recent injury "
            "or surgery. Contact a veterinarian promptly for sudden non-weight-bearing, worsening pain, or post-op decline."
        ),
    ),
    Guideline(
        id="GL_CONDITION_SKIN_LUMP_001",
        type=GuidelineType.health_observation,
        topic="Skin and lump triage",
        signals=("condition_skin_lump", "itching", "red_skin", "skin_lump", "swelling", "skin_mass_question"),
        guidance=(
            "Skin irritation and lumps can have many causes. Mention possible categories for veterinary discussion, "
            "such as allergy, insect bite, infection, cyst, trauma, or mass, without diagnosing."
        ),
        allowed_recommendation=(
            "Record size, location, color, texture, itchiness, pain, discharge, growth speed, and photos over time. "
            "Contact a veterinarian if it grows quickly, bleeds, drains, is painful, or the pet seems unwell."
        ),
        forbidden_examples=("This lump is cancer.",),
    ),
    Guideline(
        id="GL_CONDITION_URINARY_001",
        type=GuidelineType.health_observation,
        topic="Urinary condition triage",
        signals=("condition_urinary", "frequent_urination", "blood_in_urine", "straining_to_urinate", "cannot_urinate", "uti_question"),
        guidance=(
            "Urinary signs should be treated conservatively. Blood, straining, frequent urination, accidents, or inability "
            "to urinate can require veterinary evaluation. Inability to urinate is urgent."
        ),
        allowed_recommendation=(
            "I can't diagnose a UTI or other urinary disease from the app. Record frequency, amount, straining, blood, "
            "accidents, water intake, discomfort, and whether urine is passing. Seek urgent veterinary care if the pet "
            "cannot urinate or repeatedly strains with little or no urine."
        ),
        forbidden_examples=("Your dog has a UTI.",),
    ),
    Guideline(
        id="GL_CONDITION_RESPIRATORY_001",
        type=GuidelineType.health_observation,
        topic="Respiratory condition triage",
        signals=("condition_respiratory", "coughing", "breathing_effort", "wheezing", "rapid_breathing", "respiratory_distress"),
        guidance=(
            "Coughing and breathing changes can reflect many categories. Labored breathing, blue/pale gums, collapse, "
            "or severe distress should be treated as urgent. Do not diagnose respiratory disease."
        ),
        allowed_recommendation=(
            "I can't diagnose from the app. Record cough timing, frequency, triggers, breathing rate at rest, gum color, "
            "energy, appetite, and exposure history. Seek urgent veterinary care for labored breathing, blue/pale gums, "
            "collapse, or severe/worsening breathing effort."
        ),
    ),
    Guideline(
        id="GL_SOCIAL_STRESS_001",
        type=GuidelineType.behavior_social_safety,
        topic="Subtle stress signals",
        signals=("lip_licking", "yawning", "whale_eye", "freezing", "stiff_body", "turning_away", "avoidance"),
        guidance=(
            "Subtle stress signals should be preserved in state. Lack of growling does not prove comfort. "
            "Increase distance or reduce pressure when repeated stress signals appear."
        ),
    ),
    Guideline(
        id="GL_RESOURCE_GUARDING_001",
        type=GuidelineType.behavior_social_safety,
        topic="Resource proximity and guarding",
        signals=("resource_present", "freezing_near_resource", "stiff_body_near_resource", "hovering", "blocking", "growling", "air_snap"),
        guidance=(
            "Resource contexts increase social risk. Separate pets around high-value resources when stress or escalation "
            "signs appear. Do not label the pet as permanently aggressive from a single event."
        ),
    ),
    Guideline(
        id="GL_SOCIAL_PLAY_001",
        type=GuidelineType.behavior_social_safety,
        topic="Appropriate play signals",
        signals=("play_bow", "loose_body", "turn_taking", "chase_and_pause", "can_disengage"),
        guidance=(
            "Reassuring play signals may lower risk when no stress, injury, or one-sided pressure is present. "
            "Continue monitoring and interrupt if play becomes one-sided or stress signals appear."
        ),
    ),
    Guideline(
        id="GL_SOCIAL_SAFETY_001",
        type=GuidelineType.behavior_social_safety,
        topic="Escalating social conflict",
        signals=("growling", "snapping", "air_snap", "lunging", "bite", "yelp", "cannot_relax_after_separation"),
        guidance=(
            "Escalation signals should trigger immediate management and owner notification language. "
            "Separate pets calmly and avoid shared resources until reviewed."
        ),
    ),
    Guideline(
        id="GL_OWNER_COMMUNICATION_001",
        type=GuidelineType.owner_communication,
        topic="Owner-facing update structure",
        guidance=(
            "State what was observed, what is being monitored, and what would trigger escalation. "
            "Avoid diagnosis and unsupported certainty."
        ),
    ),
    Guideline(
        id="GL_NON_DIAGNOSTIC_LANGUAGE_001",
        type=GuidelineType.owner_communication,
        topic="Non-diagnostic wording",
        guidance="Use risk profile and observed signs. Do not name a disease as fact.",
        allowed_recommendation=(
            "These signs match a higher-risk profile and should be discussed with a veterinarian."
        ),
        forbidden_examples=("Your dog has parvo.",),
    ),
    Guideline(
        id="GL_ESCALATION_LANGUAGE_001",
        type=GuidelineType.owner_communication,
        topic="Escalation wording",
        guidance=(
            "For moderate or higher risk, include concrete escalation conditions. Avoid 'don't worry' "
            "and 'it will be fine.'"
        ),
        allowed_recommendation=(
            "If symptoms continue, worsen, or combine with lethargy, vomiting, blood, or refusal to eat/drink, "
            "contact the owner or veterinarian."
        ),
    ),
)


GUIDELINES_BY_ID: dict[str, Guideline] = {guideline.id: guideline for guideline in GUIDELINES}


def get_guideline(guideline_id: str) -> Guideline:
    return GUIDELINES_BY_ID[guideline_id]


def find_guidelines_by_signals(signals: set[str]) -> list[Guideline]:
    return [
        guideline
        for guideline in GUIDELINES
        if signals.intersection(guideline.signals)
    ]


def find_guidelines_by_type(guideline_type: GuidelineType) -> list[Guideline]:
    return [guideline for guideline in GUIDELINES if guideline.type == guideline_type]

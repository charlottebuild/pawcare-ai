from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pawcare.schemas.state import (
    BodyLanguageSignal,
    EntityInvolved,
    EntityType,
    HandlerIntervention,
    HandlerInterventionResult,
    HandlerInterventionType,
    Initiator,
    InteractionDistance,
    InteractionType,
    Movement,
    Observation,
    ObservationCategory,
    Posture,
    ResourceInvolved,
    ResourceType,
    SocialContext,
    SocialSignals,
    Source,
    Species,
    VocalizationSignal,
)
from pawcare.skills.symptom_understanding import (
    TRIAGE_INTENT_TERMS,
    URINARY_OBSTRUCTION_TERMS,
    contains_any,
    normalize_user_text,
)


@dataclass(frozen=True)
class ExtractedObservationBatch:
    observations: list[Observation]
    missing_information: list[str]


class LogExtractor:
    """Rule-based baseline extractor for turning sitter notes into observations.

    This is intentionally conservative. It extracts only signals that are visible in
    the text and leaves nuanced interpretation to specialist agents.
    """

    def extract(
        self,
        *,
        dog_id: str,
        raw_text: str,
        timestamp: str,
        species: Species = Species.dog,
        source: Source = Source.user_log,
    ) -> ExtractedObservationBatch:
        text = normalize_user_text(raw_text)
        observations: list[Observation] = []
        missing_information: list[str] = []

        social_observation = self._extract_social_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if social_observation is not None:
            observations.append(social_observation)

        food_observation = self._extract_food_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if food_observation is not None:
            observations.append(food_observation)
            missing_information.extend(["water_intake", "energy_level"])

        stool_observation = self._extract_stool_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if stool_observation is not None:
            observations.append(stool_observation)

        vomiting_observation = self._extract_vomiting_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if vomiting_observation is not None:
            observations.append(vomiting_observation)
            missing_information.extend(["vomiting_frequency", "energy_level"])

        mobility_observation = self._extract_mobility_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if mobility_observation is not None:
            observations.append(mobility_observation)
            missing_information.extend(["affected_limb", "pain_signs"])

        medication_observation = self._extract_medication_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if medication_observation is not None:
            observations.append(medication_observation)

        energy_observation = self._extract_energy_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if energy_observation is not None:
            observations.append(energy_observation)

        condition_triage_observation = self._extract_condition_triage_observation(
            raw_text=raw_text,
            text=text,
            timestamp=timestamp,
            species=species,
            source=source,
            sequence=len(observations) + 1,
        )
        if condition_triage_observation is not None:
            observations.append(condition_triage_observation)

        if not observations:
            observations.append(
                self._base_observation(
                    sequence=1,
                    timestamp=timestamp,
                    species=species,
                    source=source,
                    category=ObservationCategory.other,
                    raw_text=raw_text,
                    confidence=0.4,
                    health_context={"unparsed": True},
                )
            )

        return ExtractedObservationBatch(
            observations=observations,
            missing_information=sorted(set(missing_information)),
        )

    def _extract_social_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        body_language = self._extract_body_language(text=text, species=species)
        vocalization = self._extract_vocalization(text)
        resource = self._extract_resource(text)
        entity = self._extract_entity(text)
        interaction_type = self._infer_interaction_type(text=text, resource=resource)

        has_social_signal = bool(body_language or vocalization or resource.present or entity)
        if not has_social_signal:
            return None

        signals = SocialSignals(
            body_language=body_language or [BodyLanguageSignal.unknown],
            vocalization=vocalization or [VocalizationSignal.unknown],
            posture=self._infer_posture(body_language),
            movement=self._infer_movement(body_language, text),
        )

        social_context = SocialContext(
            interaction_type=interaction_type,
            initiator=self._infer_initiator(text),
            distance=self._infer_distance(text),
            resource_involved=resource,
            signals=signals,
            handler_intervention=self._extract_handler_intervention(text),
        )

        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.social_interaction,
            raw_text=raw_text,
            confidence=0.82,
            entity_involved=entity,
            social_context=social_context,
            severity_score=self._infer_social_severity(signals=signals, resource=resource),
            source_guideline_ids=self._social_guideline_ids(signals=signals, resource=resource),
        )

    def _extract_food_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        low_food_terms = [
            "didn't eat",
            "didn't have breakfast",
            "didn't have lunch",
            "didn't have dinner",
            "did not eat",
            "did not have breakfast",
            "did not have lunch",
            "did not have dinner",
            "barely touched",
            "barely ate",
            "skipped",
            "refused food",
            "not eating",
            "没吃",
            "不吃",
            "没怎么吃",
            "食欲低",
            "剩饭",
        ]
        normal_food_terms = ["ate normally", "ate dinner", "吃饭正常", "正常吃"]
        if not self._contains_any(text, low_food_terms + normal_food_terms):
            return None

        value = "normal" if self._contains_any(text, normal_food_terms) else "low"
        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.food_intake,
            raw_text=raw_text,
            confidence=0.86,
            health_context={"food_intake": value},
            severity_score=5 if value == "low" else 2,
            source_guideline_ids=["GL_APPETITE_002"],
        )

    def _extract_stool_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        stool_terms = [
            "poop",
            "poo",
            "stool",
            "diarrhea",
            "便便",
            "拉屎",
            "软便",
            "腹泻",
            "拉稀",
            "blood in stool",
            "bloody stool",
            "poop blood",
            "poo blood",
            "blood in poop",
            "blood in poo",
            "black stool",
            "tarry stool",
            "血便",
            "黑便",
        ]
        no_stool_terms = ["hasn't pooped", "no poop", "没拉", "没拉屎", "不上厕所"]
        if not self._contains_any(text, stool_terms + no_stool_terms):
            return None

        stool_quality = "absent"
        if self._contains_any(
            text,
            [
                "bloody stool",
                "blood in stool",
                "poop blood",
                "pooped blood",
                "pooping blood",
                "poo blood",
                "pooed blood",
                "pooing blood",
                "blood in poop",
                "blood in poo",
                "血便",
                "便血",
            ],
        ):
            stool_quality = "bloody"
        elif self._contains_any(text, ["black stool", "tarry stool", "黑便"]):
            stool_quality = "black_tarry"
        elif self._contains_any(text, ["soft", "软便"]):
            stool_quality = "soft"
        elif self._contains_any(text, ["watery", "diarrhea", "腹泻", "拉稀"]):
            stool_quality = "watery"
        elif self._contains_any(text, ["normal", "firm", "正常", "成形"]):
            stool_quality = "firm"

        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.stool,
            raw_text=raw_text,
            confidence=0.84,
            health_context={"stool_quality": stool_quality},
            severity_score=8 if stool_quality in {"bloody", "black_tarry"} else 6 if stool_quality == "watery" else 3,
            source_guideline_ids=["GL_STOOL_001"],
        )

    def _extract_vomiting_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        if not self._contains_any(text, ["vomit", "threw up", "throw up", "throwing up", "呕吐", "吐了"]):
            return None

        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.vomiting,
            raw_text=raw_text,
            confidence=0.88,
            health_context={"vomiting_reported": True},
            severity_score=7,
            source_guideline_ids=["GL_VOMITING_001"],
        )

    def _extract_mobility_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        mobility_terms = [
            "limp",
            "limping",
            "leg",
            "back leg",
            "hind leg",
            "strength",
            "exercise",
            "exercice",
            "rehab",
            "rehabilitation",
            "physical therapy",
            "struggle",
            "reluctant",
            "doctor wants",
            "vet wants",
            "won't put",
            "cannot put",
            "not putting",
            "non weight",
            "non-weight",
            "can't bear weight",
            "acl",
            "ccl",
            "tplo",
            "tta",
            "跛",
            "瘸",
            "不负重",
            "脚不着地",
            "手术",
            "康复",
            "复健",
            "锻炼",
            "运动",
            "不愿意",
        ]
        if not self._contains_any(text, mobility_terms):
            return None

        non_weight_bearing = self._contains_any(
            text,
            [
                "won't put",
                "cannot put",
                "not putting",
                "non weight",
                "non-weight",
                "can't bear weight",
                "不负重",
                "脚不着地",
            ],
        )
        rehab_context = self._contains_any(
            text,
            [
                "exercise",
                "exercice",
                "rehab",
                "rehabilitation",
                "physical therapy",
                "doctor wants",
                "vet wants",
                "康复",
                "复健",
                "锻炼",
            ],
        )
        post_op_context = self._contains_any(
            text,
            ["acl", "ccl", "tplo", "tta", "surgery", "post-op", "术后", "手术"],
        ) or (rehab_context and self._contains_any(text, ["leg", "recover", "strength", "腿"]))
        context = {
            "mobility": "limping",
            "weight_bearing": "non_weight_bearing" if non_weight_bearing else "partial_weight_bearing",
            "post_op_context": post_op_context,
        }
        if rehab_context:
            context["rehab_exercise"] = True

        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.mobility,
            raw_text=raw_text,
            confidence=0.84,
            health_context=context,
            severity_score=8 if non_weight_bearing and post_op_context else 6,
            source_guideline_ids=["GL_LAMENESS_001", "GL_ACL_POSTOP_001"] if post_op_context else ["GL_LAMENESS_001"],
        )

    def _extract_medication_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        medication_terms = ["nsaid", "rimadyl", "carprofen", "meloxicam", "pain med", "pain medication", "止痛药", "消炎药", "药"]
        if not self._contains_any(text, medication_terms):
            return None

        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.medication_note,
            raw_text=raw_text,
            confidence=0.78,
            health_context={"nsaid_or_pain_med_context": True},
            severity_score=5,
            source_guideline_ids=["GL_NSAID_SIDE_EFFECT_001", "GL_MEDICATION_SAFETY_001"],
        )

    def _extract_energy_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        low_energy_terms = [
            "low energy",
            "very low energy",
            "lethargic",
            "lying down more",
            "won't get up",
            "tired",
            "没精神",
            "不起来",
            "一直躺着",
        ]
        normal_energy_terms = ["seems normal", "played normally", "正常", "玩得正常"]
        if not self._contains_any(text, low_energy_terms + normal_energy_terms):
            return None

        value = "normal" if self._contains_any(text, normal_energy_terms) else "low"
        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=ObservationCategory.energy,
            raw_text=raw_text,
            confidence=0.76,
            health_context={"energy_level": value},
            severity_score=6 if value == "low" else 2,
            source_guideline_ids=["GL_LETHARGY_001"] if value == "low" else [],
        )

    def _extract_condition_triage_observation(
        self,
        *,
        raw_text: str,
        text: str,
        timestamp: str,
        species: Species,
        source: Source,
        sequence: int,
    ) -> Observation | None:
        asked_condition = self._asked_condition(text)
        has_question_intent = self._contains_any(text, TRIAGE_INTENT_TERMS)
        domain = self._condition_domain(text)
        known_diagnosis = self._known_diagnosis_context(text)
        condition_concern_only = False
        if domain is None and known_diagnosis is not None:
            domain = known_diagnosis["domain"]
        if domain is None and asked_condition is not None and has_question_intent:
            domain = self._condition_domain_from_condition(asked_condition)
            condition_concern_only = True
        if domain is None:
            return None

        context = self._condition_context(text=text, domain=domain)
        if condition_concern_only:
            context["condition_concern_only"] = True
            context["asked_condition"] = asked_condition
        if known_diagnosis is not None:
            context["known_diagnosis_context"] = True
            context["known_diagnosis"] = known_diagnosis["condition"]
            context["diagnosis_source"] = known_diagnosis["source"]
        category = {
            "gi": ObservationCategory.stool,
            "oral_neck": ObservationCategory.other,
            "mobility": ObservationCategory.mobility,
            "skin_lump": ObservationCategory.other,
            "urinary": ObservationCategory.urination,
            "respiratory": ObservationCategory.other,
        }[domain]
        guideline_ids = {
            "gi": ["GL_CONDITION_GI_001"],
            "oral_neck": ["GL_CONDITION_ORAL_NECK_001"],
            "mobility": ["GL_CONDITION_MOBILITY_001", "GL_LAMENESS_001"],
            "skin_lump": ["GL_CONDITION_SKIN_LUMP_001"],
            "urinary": ["GL_CONDITION_URINARY_001"],
            "respiratory": ["GL_CONDITION_RESPIRATORY_001"],
        }[domain]
        if domain == "mobility" and context.get("post_op_context"):
            guideline_ids.append("GL_ACL_POSTOP_001")

        return self._base_observation(
            sequence=sequence,
            timestamp=timestamp,
            species=species,
            source=source,
            category=category,
            raw_text=raw_text,
            confidence=0.76,
            health_context=context,
            severity_score=8 if context.get("urgent_red_flag") else 6,
            source_guideline_ids=guideline_ids,
        )

    def _condition_domain(self, text: str) -> str | None:
        has_question_intent = self._contains_any(text, TRIAGE_INTENT_TERMS)
        domains = [
            ("respiratory", ["cough", "coughing", "breathing", "breath", "wheezing", "喘", "咳", "呼吸"]),
            ("urinary", ["urine", "pee", "peeing", "urinate", "urinating", "blood in urine", "litter box", "猫砂盆", "尿", "尿血"]),
            (
                "oral_neck",
                [
                    "drool",
                    "drooling",
                    "excess saliva",
                    "too much saliva",
                    "saliva dripping",
                    "jaw",
                    "chin",
                    "neck",
                    "under jaw",
                    "under chin",
                    "mouth",
                    "oral",
                    "流口水",
                    "下巴",
                    "脖子",
                    "口腔",
                ],
            ),
            ("skin_lump", ["skin", "itch", "itching", "scratch", "scratching", "lump", "bump", "mass", "swelling", "皮肤", "痒", "包", "肿块"]),
            ("mobility", ["limp", "limping", "leg", "paw", "walk", "walking", "post-op", "腿", "跛", "瘸", "术后"]),
            ("gi", ["vomit", "diarrhea", "stool", "poop", "appetite", "吐", "拉稀", "腹泻", "便便"]),
        ]
        for domain, terms in domains:
            red_flag_triggers_triage = domain in {"urinary", "respiratory"} and self._condition_red_flag_present(text, domain)
            if self._contains_any(text, terms) and (has_question_intent or red_flag_triggers_triage):
                return domain
        return None

    def _condition_context(self, *, text: str, domain: str) -> dict[str, object]:
        context: dict[str, object] = {
            "condition_triage": True,
            "condition_domain": domain,
            "asked_condition": self._asked_condition(text),
            "possible_categories": self._possible_categories(domain),
            "red_flags": self._red_flags(text, domain),
            "record_fields": self._record_fields(domain),
        }
        if domain == "urinary" and self._contains_any(
            text,
            self._urinary_obstruction_terms(),
        ):
            context["urinary_obstruction"] = True
            context["urgent_red_flag"] = True
        if domain == "respiratory" and self._contains_any(
            text,
            ["hard to breathe", "trouble breathing", "labored breathing", "blue gums", "collapse", "breathing hard", "呼吸困难", "喘不过气"],
        ):
            context["respiratory_distress"] = True
            context["urgent_red_flag"] = True
        if domain == "oral_neck" and self._contains_any(text, ["drool", "drooling", "swallow", "breathing", "流口水", "吞咽"]):
            context["oral_neck_function_change"] = True
        if domain == "mobility" and self._contains_any(text, ["post-op", "surgery", "acl", "ccl", "术后", "手术"]):
            context["post_op_context"] = True
        return context

    def _condition_red_flag_present(self, text: str, domain: str) -> bool:
        return bool(self._red_flags(text, domain))

    def _asked_condition(self, text: str) -> str | None:
        condition_terms = [
            "gastroenteritis",
            "parvo",
            "salivary mucocele",
            "salivary cyst",
            "salivary gland cyst",
            "salivary gland cysts",
            "uti",
            "urinary tract infection",
            "infection",
            "肠胃炎",
            "细小",
            "唾液腺囊肿",
            "尿路感染",
        ]
        for term in condition_terms:
            if term in text:
                return term
        return None

    def _known_diagnosis_context(self, text: str) -> dict[str, str] | None:
        diagnosis_terms = [
            "vet diagnosed",
            "vet said",
            "doctor diagnosed",
            "doctor said",
            "confirmed by vet",
            "diagnosed with",
            "diagnosis is",
            "医生说",
            "兽医说",
            "确诊",
            "诊断",
        ]
        if not self._contains_any(text, diagnosis_terms):
            return None
        condition = self._asked_condition(text)
        if condition is None:
            return None
        return {
            "condition": condition,
            "domain": self._condition_domain_from_condition(condition),
            "source": "veterinarian",
        }

    def _condition_domain_from_condition(self, condition: str) -> str:
        domain_by_condition = {
            "gastroenteritis": "gi",
            "parvo": "gi",
            "salivary mucocele": "oral_neck",
            "salivary cyst": "oral_neck",
            "salivary gland cyst": "oral_neck",
            "salivary gland cysts": "oral_neck",
            "uti": "urinary",
            "urinary tract infection": "urinary",
            "infection": "urinary",
            "肠胃炎": "gi",
            "细小": "gi",
            "唾液腺囊肿": "oral_neck",
            "尿路感染": "urinary",
        }
        return domain_by_condition.get(condition, "gi")

    def _possible_categories(self, domain: str) -> list[str]:
        return {
            "gi": ["dietary upset", "gastroenteritis", "parasites", "foreign material", "medication side effects", "infectious disease"],
            "oral_neck": ["salivary mucocele", "dental or oral disease", "trauma", "abscess", "lymph node swelling", "another mass"],
            "mobility": ["strain", "joint injury", "paw injury", "post-operative complication", "pain"],
            "skin_lump": ["allergy", "insect bite", "skin infection", "cyst", "trauma", "mass"],
            "urinary": ["urinary tract irritation or infection", "bladder stones", "inflammation", "urinary blockage"],
            "respiratory": ["airway irritation", "respiratory infection", "heart or lung concern", "allergy", "foreign material"],
        }[domain]

    def _red_flags(self, text: str, domain: str) -> list[str]:
        flags_by_domain = {
            "gi": [
                ("vomiting repeats", ["repeated vomiting", "vomiting again", "vomit multiple", "一直吐"]),
                ("bloody or black/tarry stool", ["bloody stool", "blood in stool", "black stool", "tarry stool", "血便", "黑便"]),
                ("lethargy or refusal to eat/drink", ["letharg", "won't eat", "refuses food", "refuses water", "不吃", "不喝"]),
            ],
            "oral_neck": [
                ("trouble swallowing or breathing", ["trouble swallowing", "can't swallow", "breathing", "吞咽", "呼吸"]),
                ("rapid swelling or severe pain", ["rapid", "getting bigger", "grow fast", "grows fast", "growing fast", "pain", "疼", "变大"]),
            ],
            "mobility": [
                ("non-weight-bearing or worsening pain", ["non weight", "non-weight", "can't bear weight", "worse", "pain", "不负重", "疼"]),
            ],
            "skin_lump": [
                ("rapid growth, bleeding, discharge, or pain", ["rapid", "growing", "bleeding", "discharge", "pain", "流血", "流脓", "疼"]),
            ],
            "urinary": [
                (
                    "cannot urinate or repeated straining with little urine",
                    self._urinary_obstruction_terms()
                    + ["few drops", "little urine", "only a few drops"],
                ),
                ("blood in urine", ["blood in urine", "bloody urine", "尿血"]),
            ],
            "respiratory": [
                ("labored breathing, blue/pale gums, collapse, or severe distress", ["hard to breathe", "trouble breathing", "labored breathing", "blue gums", "pale gums", "collapse", "breathing hard", "呼吸困难"]),
            ],
        }
        return [
            label
            for label, terms in flags_by_domain[domain]
            if self._contains_any(text, terms)
        ]

    def _urinary_obstruction_terms(self) -> list[str]:
        return URINARY_OBSTRUCTION_TERMS + [
            "few drops",
            "little urine",
            "only a few drops",
        ]

    def _record_fields(self, domain: str) -> list[str]:
        return {
            "gi": ["vomiting frequency", "stool quality", "appetite", "water intake", "energy", "medication use", "possible exposures"],
            "oral_neck": ["location", "size", "firmness", "mobility", "pain", "drooling", "eating or swallowing changes", "growth speed"],
            "mobility": ["affected limb", "weight-bearing ability", "pain signs", "swelling", "activity change", "recent injury or surgery"],
            "skin_lump": ["size", "location", "color", "texture", "itchiness", "pain", "discharge", "growth speed", "photos"],
            "urinary": ["frequency", "amount", "straining", "blood", "accidents", "water intake", "whether urine is passing"],
            "respiratory": ["cough timing", "frequency", "triggers", "resting breathing rate", "gum color", "energy", "appetite", "exposures"],
        }[domain]

    def _base_observation(
        self,
        *,
        sequence: int,
        timestamp: str,
        species: Species,
        source: Source,
        category: ObservationCategory,
        raw_text: str,
        confidence: float,
        entity_involved: EntityInvolved | None = None,
        social_context: SocialContext | None = None,
        health_context: dict[str, object] | None = None,
        severity_score: int | None = None,
        source_guideline_ids: list[str] | None = None,
    ) -> Observation:
        return Observation(
            observation_id=f"obs_{sequence:03d}",
            timestamp=timestamp,
            source=source,
            category=category,
            species=species,
            raw_text=raw_text,
            confidence=confidence,
            entity_involved=entity_involved,
            social_context=social_context,
            health_context=health_context,
            severity_score=severity_score,
            source_guideline_ids=source_guideline_ids or [],
        )

    def _extract_body_language(
        self, *, text: str, species: Species
    ) -> list[BodyLanguageSignal]:
        shared_mapping = {
            BodyLanguageSignal.lip_licking: ["lip lick", "licked her lips", "舔嘴", "舔唇"],
            BodyLanguageSignal.yawning: ["yawn", "打哈欠"],
            BodyLanguageSignal.whale_eye: ["whale eye", "露眼白"],
            BodyLanguageSignal.frozen: ["froze", "frozen", "very still", "僵住", "不动"],
            BodyLanguageSignal.stiff_body: ["stiff", "tense", "身体僵", "紧绷"],
            BodyLanguageSignal.play_bow: ["play bow", "邀玩"],
            BodyLanguageSignal.loose_body: ["loose", "wiggly", "放松"],
            BodyLanguageSignal.turning_away: ["turned her head away", "turning away", "转头"],
            BodyLanguageSignal.avoidance: ["avoid", "躲开", "回避"],
            BodyLanguageSignal.lowered_tail: ["lowered tail", "tail down", "尾巴下垂"],
            BodyLanguageSignal.tail_tucked: ["tucked tail", "tail tucked", "夹尾巴"],
            BodyLanguageSignal.ears_back: ["ears back", "耳朵后贴", "耳朵向后"],
            BodyLanguageSignal.hackles_raised: ["hackles", "炸毛"],
            BodyLanguageSignal.air_snap: ["air snap", "snapped in the air", "空咬"],
            BodyLanguageSignal.blocking: ["blocking", "挡住"],
            BodyLanguageSignal.hovering: ["hovering", "守着"],
        }
        cat_mapping = {
            BodyLanguageSignal.puffed_tail: ["puffed tail", "tail puffed", "尾巴炸毛"],
            BodyLanguageSignal.arched_back: ["arched back", "拱背"],
            BodyLanguageSignal.flattened_ears: ["flattened ears", "ears flattened", "飞机耳"],
            BodyLanguageSignal.hiding: ["hiding", "躲起来"],
            BodyLanguageSignal.hissing: ["hissing", "哈气"],
            BodyLanguageSignal.swatting: ["swatting", "拍打"],
        }

        mapping = dict(shared_mapping)
        if species == Species.cat:
            mapping.update(cat_mapping)

        return self._extract_enum_values(text=text, mapping=mapping)

    def _extract_vocalization(self, text: str) -> list[VocalizationSignal]:
        mapping = {
            VocalizationSignal.growl: ["growl", "growled", "低吼"],
            VocalizationSignal.bark: ["bark", "barked", "叫"],
            VocalizationSignal.high_pitched_bark: ["high-pitched bark", "尖叫"],
            VocalizationSignal.whine: ["whine", "whined", "呜咽"],
            VocalizationSignal.snarl: ["snarl", "snarled", "龇牙低吼"],
            VocalizationSignal.yelp: ["yelp", "yelped", "惨叫"],
            VocalizationSignal.silent: ["silent", "no growling", "没叫", "没有叫"],
        }
        return self._extract_enum_values(text=text, mapping=mapping)

    def _extract_entity(self, text: str) -> EntityInvolved | None:
        if self._contains_any(text, ["large dog", "larger dog", "big dog", "大狗"]):
            return EntityInvolved(type=EntityType.large_dog, relative_size="larger")
        if self._contains_any(text, ["small dog", "小狗"]):
            return EntityInvolved(type=EntityType.small_dog, relative_size="smaller")
        if self._contains_any(text, ["other dog", "another dog", "另一只狗"]):
            return EntityInvolved(type=EntityType.dog)
        if self._contains_any(text, ["human", "person", "stranger", "人", "陌生人"]):
            return EntityInvolved(type=EntityType.human)
        return None

    def _extract_resource(self, text: str) -> ResourceInvolved:
        resource_terms = {
            ResourceType.food: ["food", "food bowl", "饭", "食物"],
            ResourceType.treat: ["treat", "零食"],
            ResourceType.chew: ["chew", "chewy", "咬胶"],
            ResourceType.toy: ["toy", "玩具"],
            ResourceType.bed: ["bed", "床"],
            ResourceType.crate: ["crate", "笼子"],
            ResourceType.water_bowl: ["water bowl", "水碗"],
            ResourceType.human_attention: ["attention", "抱", "摸"],
            ResourceType.doorway: ["doorway", "门口"],
        }
        for resource_type, terms in resource_terms.items():
            if self._contains_any(text, terms):
                return ResourceInvolved(present=True, type=resource_type, ownership="unknown")
        return ResourceInvolved(present=False, type=ResourceType.none)

    def _infer_interaction_type(
        self, *, text: str, resource: ResourceInvolved
    ) -> InteractionType:
        if resource.present and self._contains_any(text, ["growl", "snapped", "低吼", "空咬"]):
            return InteractionType.resource_conflict
        if resource.present:
            return InteractionType.resource_proximity
        if self._contains_any(text, ["play bow", "play", "chasing", "玩", "追逐"]):
            return InteractionType.play
        if self._contains_any(text, ["stared", "staring", "盯"]):
            return InteractionType.staring
        if self._contains_any(text, ["came near", "approached", "靠近"]):
            return InteractionType.greeting
        return InteractionType.unknown

    def _infer_initiator(self, text: str) -> Initiator:
        if self._contains_any(text, ["other dog", "large dog", "larger dog", "大狗", "另一只狗"]):
            return Initiator.other_dog
        if self._contains_any(text, ["human", "person", "stranger", "人", "陌生人"]):
            return Initiator.human
        return Initiator.unclear

    def _infer_distance(self, text: str) -> InteractionDistance:
        if self._contains_any(text, ["across the room", "房间另一边"]):
            return InteractionDistance.across_room
        if self._contains_any(text, ["came near", "near", "approached", "靠近"]):
            return InteractionDistance.near
        if self._contains_any(text, ["contact", "touched", "碰到"]):
            return InteractionDistance.direct_contact
        return InteractionDistance.unknown

    def _infer_posture(self, body_language: Iterable[BodyLanguageSignal]) -> Posture:
        signals = set(body_language)
        if BodyLanguageSignal.frozen in signals:
            return Posture.frozen
        if BodyLanguageSignal.stiff_body in signals:
            return Posture.stiff
        if BodyLanguageSignal.loose_body in signals:
            return Posture.loose
        if BodyLanguageSignal.crouching in signals:
            return Posture.cowered
        return Posture.unknown

    def _infer_movement(
        self, body_language: Iterable[BodyLanguageSignal], text: str
    ) -> Movement:
        signals = set(body_language)
        if BodyLanguageSignal.turning_away in signals:
            return Movement.turning_away
        if BodyLanguageSignal.avoidance in signals:
            return Movement.avoidant
        if self._contains_any(text, ["approached", "came near", "靠近"]):
            return Movement.approach
        if BodyLanguageSignal.frozen in signals:
            return Movement.still
        return Movement.unknown

    def _extract_handler_intervention(self, text: str) -> HandlerIntervention:
        if self._contains_any(text, ["separated", "分开"]):
            return HandlerIntervention(
                occurred=True,
                type=HandlerInterventionType.separated_dogs,
                result=HandlerInterventionResult.deescalated,
            )
        if self._contains_any(text, ["increased distance", "拉开距离"]):
            return HandlerIntervention(
                occurred=True,
                type=HandlerInterventionType.increased_distance,
                result=HandlerInterventionResult.deescalated,
            )
        if self._contains_any(text, ["removed the chew", "removed resource", "拿走"]):
            return HandlerIntervention(
                occurred=True,
                type=HandlerInterventionType.removed_resource,
                result=HandlerInterventionResult.deescalated,
            )
        return HandlerIntervention()

    def _infer_social_severity(
        self, *, signals: SocialSignals, resource: ResourceInvolved
    ) -> int:
        body = set(signals.body_language)
        vocals = set(signals.vocalization)
        if VocalizationSignal.growl in vocals or BodyLanguageSignal.air_snap in body:
            return 8 if resource.present else 7
        if BodyLanguageSignal.frozen in body and resource.present:
            return 6
        if BodyLanguageSignal.lip_licking in body or BodyLanguageSignal.yawning in body:
            return 4
        if BodyLanguageSignal.play_bow in body and BodyLanguageSignal.loose_body in body:
            return 2
        return 3

    def _social_guideline_ids(
        self, *, signals: SocialSignals, resource: ResourceInvolved
    ) -> list[str]:
        guideline_ids = ["GL_SOCIAL_STRESS_001"]
        if resource.present:
            guideline_ids.append("GL_RESOURCE_GUARDING_001")
        if BodyLanguageSignal.play_bow in set(signals.body_language):
            guideline_ids.append("GL_SOCIAL_PLAY_001")
        return guideline_ids

    def _extract_enum_values(
        self, *, text: str, mapping: dict[object, list[str]]
    ) -> list:
        values = []
        for value, terms in mapping.items():
            if self._contains_any(text, terms):
                values.append(value)
        return values

    def _contains_any(self, text: str, terms: Iterable[str]) -> bool:
        return contains_any(text, terms)

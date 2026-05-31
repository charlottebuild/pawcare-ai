from __future__ import annotations

import re
from typing import Iterable


TRIAGE_INTENT_TERMS = [
    "what is wrong",
    "what happened",
    "what might",
    "what can it be",
    "could it be",
    "is it",
    "is there any problem",
    "any problem",
    "should i worry",
    "i am worried",
    "i'm worried",
    "concerned",
    "可能是",
    "会不会是",
    "是不是",
    "怎么了",
    "什么病",
    "有点担心",
    "担心",
    "奇怪吗",
    "要紧吗",
]

URINARY_OBSTRUCTION_TERMS = [
    "can't pee",
    "cant pee",
    "couldn't pee",
    "couldnt pee",
    "cannot pee",
    "didn't pee",
    "did not pee",
    "no pee",
    "no urine",
    "not peeing",
    "cannot urinate",
    "can't urinate",
    "couldn't urinate",
    "didn't urinate",
    "straining",
    "little or no urine",
    "didn't pee all day",
    "did not pee all day",
    "尿不出",
    "没尿",
    "一天没尿",
    "没有尿",
]

SIMILAR_CASE_TERM_GROUPS = {
    "acl": ["acl", "ccl", "cruciate"],
    "patellar_luxation": ["patella", "luxating", "kneecap", "膝盖", "髌骨"],
    "post_op": ["post-op", "post op", "surgery", "术后", "手术"],
    "non_weight_bearing": [
        "non-weight-bearing",
        "not weight bearing",
        "won't put",
        "wont put",
        "not putting",
        "不敢把脚放",
        "不落地",
        "跛",
        "limp",
        "limping",
    ],
    "rehab_reluctance": ["exercise", "rehab", "康复", "复健", "struggle"],
    "head_withdrawal": ["head", "shrink", "缩头", "歪头", "tilt"],
    "drooling": ["drool", "drooling", "流口水"],
    "oral_mass": ["mouth", "oral", "tongue", "舌头", "口腔", "肿瘤", "mass"],
    "tongue_lump": ["under tongue", "舌下", "tongue lump"],
    "salivary_gland": ["salivary", "mucocele", "唾液"],
    "vomiting": ["vomit", "vomiting", "throwing up", "throw up", "吐"],
    "diarrhea": ["diarrhea", "loose stool", "拉稀", "软便"],
    "bloody_stool": ["bloody stool", "blood in stool", "便血"],
    "gi": ["gastroenteritis", "gi", "stomach", "肠胃"],
    "urinary": ["urine", "pee", "urinary", "尿"],
    "bloody_urine": ["blood in urine", "bloody urine", "尿血"],
    "cannot_pee": URINARY_OBSTRUCTION_TERMS,
    "respiratory": ["cough", "coughing", "breathing", "respiratory", "咳", "呼吸"],
    "breathing_hard": ["breathing hard", "labored breathing", "呼吸困难"],
    "skin_lump": ["skin lump", "lump", "bump", "itching", "皮肤", "肿块"],
}


def normalize_user_text(value: str) -> str:
    """Normalize real user wording while keeping the original raw text elsewhere."""

    text = value.lower()
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .replace("´", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    text = re.sub(r"\b(couldnt|didnt|doesnt|dont|cant|wont)'", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_match_text(value: str) -> str:
    text = normalize_user_text(value)
    text = text.replace("'", "")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized_text = normalize_match_text(text)
    return any(normalize_match_text(term) in normalized_text for term in terms)


def extract_canonical_terms(
    text: str,
    term_groups: dict[str, list[str]] | None = None,
) -> set[str]:
    groups = term_groups or SIMILAR_CASE_TERM_GROUPS
    return {
        canonical
        for canonical, terms in groups.items()
        if contains_any(text, terms)
    }


def normalize_identifier(value: str) -> str:
    return normalize_match_text(value).replace(" ", "_")

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AbnormalSignalRecord:
    """Structured trigger for user-described signs that deserve care context."""

    signal_id: str
    species: tuple[str, ...]
    domain: str
    canonical_terms: tuple[str, ...]
    user_phrases: tuple[str, ...]
    risk_hint: str
    reference_ids: tuple[str, ...]
    case_ids: tuple[str, ...]
    safe_language: str


def seed_abnormal_signal_records() -> list[AbnormalSignalRecord]:
    return [
        AbnormalSignalRecord(
            signal_id="cat_no_urination_24h",
            species=("cat",),
            domain="urinary",
            canonical_terms=("cannot_pee", "urinary"),
            user_phrases=(
                "didn't pee all day",
                "did not pee all day",
                "hasn't gone to the bathroom",
                "has not gone to the bathroom",
                "not gone to the bathroom",
                "no bathroom",
                "一天没尿",
                "两天没尿",
                "没上厕所",
                "一天没上厕所",
                "两天没上厕所",
                "24小时没上厕所",
            ),
            risk_hint="urgent",
            reference_ids=("ref_urinary_cornell_001",),
            case_ids=("case_urinary_001",),
            safe_language=(
                "Little or no urine can be a urinary red flag, especially for cats. "
                "This should trigger urgent vet discussion, not a diagnosis."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="pet_cannot_urinate",
            species=("dog", "cat"),
            domain="urinary",
            canonical_terms=("cannot_pee", "urinary"),
            user_phrases=(
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
                "little or no urine",
                "尿不出",
                "没尿",
                "没有尿",
            ),
            risk_hint="urgent",
            reference_ids=("ref_urinary_cornell_001",),
            case_ids=("case_urinary_001",),
            safe_language=(
                "Trouble passing urine can be urgent. The app should surface urinary "
                "care context and encourage veterinary contact."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="bloody_or_black_stool",
            species=("dog", "cat"),
            domain="gi",
            canonical_terms=("bloody_stool", "gi"),
            user_phrases=(
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
                "black stool",
                "tarry stool",
                "便血",
                "血便",
                "黑便",
            ),
            risk_hint="urgent",
            reference_ids=("ref_gi_merck_001",),
            case_ids=("case_gi_001",),
            safe_language=(
                "Blood or black/tarry stool is a digestive red flag. The app can suggest "
                "recording stool, energy, vomiting, and possible exposures before vet contact."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="non_weight_bearing_limb",
            species=("dog", "cat"),
            domain="mobility",
            canonical_terms=("non_weight_bearing", "pain"),
            user_phrases=(
                "non-weight-bearing",
                "not weight bearing",
                "won't put",
                "wont put",
                "not putting",
                "脚落不了地",
                "不能落地",
                "不敢落地",
                "一只脚落不了地",
                "不落地",
                "跛",
                "limp",
                "limping",
            ),
            risk_hint="discuss_soon",
            reference_ids=("ref_mobility_acvs_001", "ref_mobility_patella_cornell_001"),
            case_ids=("case_acl_postop_001", "case_patella_001"),
            safe_language=(
                "Not bearing weight or a sudden limp should trigger mobility context, "
                "especially after surgery or injury."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="breathing_effort",
            species=("dog", "cat"),
            domain="respiratory",
            canonical_terms=("breathing_hard", "respiratory"),
            user_phrases=(
                "breathing hard",
                "labored breathing",
                "breathing looks labored",
                "trouble breathing",
                "hard to breathe",
                "呼吸困难",
            ),
            risk_hint="urgent",
            reference_ids=("ref_respiratory_merck_001",),
            case_ids=("case_respiratory_001",),
            safe_language=(
                "Increased breathing effort is an urgent red flag. Care context should "
                "prioritize vet contact and observation details."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="oral_or_tongue_lump",
            species=("dog", "cat"),
            domain="oral_neck",
            canonical_terms=("oral_mass", "tongue_lump"),
            user_phrases=("mouth lump", "oral mass", "tongue lump", "under tongue", "舌下", "舌头肿块", "口腔肿块"),
            risk_hint="discuss_soon",
            reference_ids=("ref_oral_acvs_001", "ref_oral_merck_001"),
            case_ids=("case_oral_neck_001",),
            safe_language=(
                "A mouth or tongue-area lump should be discussed with a veterinarian. "
                "The app should ask the user to record size, location, eating changes, and photos."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="skin_lump_or_rapid_skin_change",
            species=("dog", "cat"),
            domain="skin_lump",
            canonical_terms=("skin_lump",),
            user_phrases=("skin lump", "lump", "bump", "itching", "皮肤", "肿块"),
            risk_hint="discuss_if_persistent",
            reference_ids=("ref_skin_merck_001",),
            case_ids=("case_skin_lump_001",),
            safe_language=(
                "New or changing lumps should trigger context about documenting size, "
                "location, growth speed, irritation, and photos."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="vomiting",
            species=("dog", "cat"),
            domain="gi",
            canonical_terms=("vomiting", "gi"),
            user_phrases=("vomit", "vomiting", "throwing up", "throw up", "吐"),
            risk_hint="monitor_or_escalate",
            reference_ids=("ref_gi_merck_001",),
            case_ids=("case_gi_001",),
            safe_language=(
                "Vomiting should trigger GI care context when paired with concern, repetition, "
                "blood, low energy, appetite loss, or other abnormal signs."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="seizure_or_convulsion",
            species=("dog", "cat"),
            domain="neurologic",
            canonical_terms=("seizure", "convulsion", "neurologic"),
            user_phrases=(
                "seizure",
                "seizures",
                "convulsion",
                "convulsing",
                "fit",
                "shaking uncontrollably",
                "collapsed and shaking",
                "抽搐",
                "癫痫",
                "发作",
                "倒地抽",
            ),
            risk_hint="urgent",
            reference_ids=("ref_neurologic_merck_001",),
            case_ids=("case_seizure_001",),
            safe_language=(
                "Seizure-like activity should trigger neurologic emergency context. "
                "The app should ask the user to record duration, recovery, and repeated episodes."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="abdominal_distension_or_bloat",
            species=("dog", "cat"),
            domain="abdominal",
            canonical_terms=("abdominal_distension", "bloat", "unproductive_vomiting"),
            user_phrases=(
                "bloated",
                "bloat",
                "swollen belly",
                "distended belly",
                "hard belly",
                "trying to vomit but nothing comes out",
                "unproductive vomiting",
                "腹胀",
                "肚子胀",
                "肚子很硬",
                "想吐吐不出来",
            ),
            risk_hint="urgent",
            reference_ids=("ref_abdominal_bloat_vca_001", "ref_abdominal_bloat_cornell_001"),
            case_ids=("case_bloat_001",),
            safe_language=(
                "A swollen or hard abdomen with retching can be an emergency pattern. "
                "The app should surface bloat/GDV discussion context without diagnosing."
            ),
        ),
        AbnormalSignalRecord(
            signal_id="eye_injury_or_vision_loss",
            species=("dog", "cat"),
            domain="eye",
            canonical_terms=("eye_injury", "vision_loss", "eye_pain"),
            user_phrases=(
                "eye injury",
                "hurt eye",
                "eye trauma",
                "eye scratch",
                "eye bulging",
                "eye popped out",
                "sudden blindness",
                "can't see",
                "cannot see",
                "眼睛受伤",
                "眼睛被抓",
                "眼球突出",
                "突然看不见",
                "看不见",
            ),
            risk_hint="urgent",
            reference_ids=("ref_eye_emergency_vca_001",),
            case_ids=("case_eye_injury_001",),
            safe_language=(
                "Eye trauma, bulging, or sudden vision change should trigger urgent eye-care context. "
                "The app should avoid home treatment instructions and recommend vet evaluation."
            ),
        ),
    ]


def abnormal_signal_term_groups() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for record in seed_abnormal_signal_records():
        for term in record.canonical_terms:
            groups.setdefault(term, [])
            for phrase in record.user_phrases:
                if phrase not in groups[term]:
                    groups[term].append(phrase)
    return groups


def abnormal_care_context_terms() -> set[str]:
    return {
        term
        for record in seed_abnormal_signal_records()
        for term in record.canonical_terms
    }

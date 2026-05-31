from pawcare.skills.symptom_understanding import contains_any, normalize_match_text


def test_normalizes_mistyped_contractions_for_matching() -> None:
    assert normalize_match_text("NiaoNiao couldnt' pee today") == "niaoniao couldnt pee today"
    assert contains_any("NiaoNiao couldnt' pee today", ["couldn't pee"])
    assert contains_any("NiaoNiao didnt pee all day", ["didn't pee all day"])


def test_normalizes_punctuation_without_losing_chinese_symptoms() -> None:
    assert contains_any("猫猫一天没尿，很担心", ["一天没尿"])
    assert contains_any("猫猫一天没尿，很担心", ["担心"])


def test_broad_time_phrase_alone_is_not_a_urinary_signal() -> None:
    assert not contains_any("she was playful all day long", ["didn't pee all day"])

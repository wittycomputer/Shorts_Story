import re

import pytest

from korean_speech import normalize_for_speech, speech_sentences


@pytest.mark.parametrize("original,expected", [
    ("브렌트유는 106.65달러, 1.8% 올랐습니다.", "브렌트유는 백육 점 육오 달러, 일 점 팔 퍼센트 올랐습니다."),
    ("WTI는 93.74달러로 2.0% 상승했습니다.", "더블유티아이는 구십삼 점 칠사 달러로 이 점 영 퍼센트 상승했습니다."),
    ("2026년 10월 12일에는 13명, 300명입니다.", "이천이십육년 시월 십이일에는 열세 명, 삼백 명입니다."),
    ("21사단에 20명과 21명이 있습니다.", "이십일사단에 스무 명과 스물한 명이 있습니다."),
    ("2026-06-10에 $106.65를 기록했습니다.", "이천이십육 년 유월 십 일에 백육 점 육오 달러를 기록했습니다."),
    ("AI와 DB를 PC에서 Firebase로 연결합니다.", "에이아이와 디비를 피씨에서 파이어베이스로 연결합니다."),
    ("FFmpeg: 3D 영상을 만듭니다.", "에프에프엠펙: 쓰리디 영상을 만듭니다."),
    ("-0.05%와 +2.0%입니다.", "마이너스 영 점 영오 퍼센트와 플러스 이 점 영 퍼센트입니다."),
    ("1.2%p, 25bp", "일 점 이 퍼센트 포인트, 이십오 베이시스 포인트"),
    ("시속 10km와 3.5kg", "시속 십 킬로미터와 삼 점 오 킬로그램"),
])
def test_reading_forms_preserve_numeric_precision_and_common_names(original, expected):
    assert normalize_for_speech(original) == expected


def test_numeric_changes_and_ranges_keep_both_endpoints_and_unit():
    assert normalize_for_speech("88.6→81.9로 하락했습니다.") == "팔십팔 점 육에서 팔십일 점 구로 하락했습니다."
    assert normalize_for_speech("85→90달러로 높였습니다.") == "팔십오 달러에서 구십 달러로 높였습니다."
    assert normalize_for_speech("자금의 3~5% 이내입니다.") == "자금의 삼 퍼센트에서 오 퍼센트 이내입니다."
    assert normalize_for_speech("3-5% 이내입니다.") == "삼 퍼센트에서 오 퍼센트 이내입니다."
    assert normalize_for_speech("3~5%로 늘었습니다.") == "삼 퍼센트에서 오 퍼센트로 늘었습니다."
    assert normalize_for_speech("3-5%로 늘었습니다.") == "삼 퍼센트에서 오 퍼센트로 늘었습니다."
    assert normalize_for_speech("3~5명으로 늘었습니다.") == "삼 명에서 오 명으로 늘었습니다."


def test_counter_month_readings_are_contextual():
    assert normalize_for_speech("6월 10월 6개 10개 12시 13시") == "유월 시월 여섯 개 열 개 열두 시 십삼 시"
    assert normalize_for_speech("1개월 2개월 1분 3초") == "일개월 이개월 일분 삼초"


def test_thousands_decimal_zero_and_identifiers_retain_their_information():
    assert normalize_for_speech("1,300.050달러") == "천삼백 점 영오영 달러"
    assert normalize_for_speech("0007") == "영 영 영 칠"
    # A version is not guessed as a decimal or a date.
    assert normalize_for_speech("v1.2.3") == "v1.2.3"
    assert normalize_for_speech("Qwen3") == "큐웬삼"


def test_native_counter_never_consumes_a_currency_or_other_word_prefix():
    assert normalize_for_speech("21달러와 21 달러, 21달") == "이십일 달러와 이십일 달러, 스물한 달"
    assert normalize_for_speech("2대대와 2개월, 1개념") == "이대대와 이개월, 일개념"
    assert normalize_for_speech("13명이 한 시간 동안 기다립니다.") == "열세 명이 한 시간 동안 기다립니다."
    assert normalize_for_speech("30대 남성과 차량 30대") == "삼십 대 남성과 차량 서른 대"
    assert normalize_for_speech("2026년10월12일") == "이천이십육년시월십이일"


@pytest.mark.parametrize("original,expected", [
    ("1mW와 1MW", "일 밀리와트와 일 메가와트"),
    ("2mWh와 2MWh, 3kWh", "이 밀리와트시와 이 메가와트시, 삼 킬로와트시"),
    ("8Mb와 8MB, 1Gb와 1GB", "팔 메가비트와 팔 메가바이트, 일 기가비트와 일 기가바이트"),
    ("1mg, 1Mg", "일 밀리그램, 일 메가그램"),
    ("1mm와 1Mm", "일 밀리미터와 일 메가미터"),
    ("1mL와 1ML", "일 밀리리터와 일 메가리터"),
    ("1m와 1M", "일 미터와 1M"),
])
def test_si_prefixes_and_bit_byte_case_never_change_the_quantity(original, expected):
    assert normalize_for_speech(original) == expected


def test_unknown_si_casing_is_not_guessed_as_a_different_unit():
    assert normalize_for_speech("1mw, 1gb, 1mwh") == "1mw, 1gb, 1mwh"
    assert normalize_for_speech("1mW, 1MW, 1mWh, 1MWh") == "일 밀리와트, 일 메가와트, 일 밀리와트시, 일 메가와트시"


def test_comma_enumerations_read_every_number_without_breaking_grouped_amounts():
    assert normalize_for_speech("항목1,2,3입니다.") == "항목일,이,삼입니다."
    assert normalize_for_speech("1,2,3과 1,300, 12,345,678.050달러") == "일,이,삼과 천삼백, 천이백삼십사만 오천육백칠십팔 점 영오영 달러"
    assert normalize_for_speech("버전 v1.2.3과 1.8%입니다.") == "버전 v1.2.3과 일 점 팔 퍼센트입니다."


def test_tts_sentences_do_not_break_a_decimal_or_a_complete_long_sentence():
    first = "브렌트유는 배럴당 106.65달러로 1.8% 올랐으며, 중동 지역의 공급 차질 우려가 가격에 반영됐습니다."
    second = "WTI는 93.74달러였습니다."
    assert len(first) > 40
    assert speech_sentences(first + " " + second) == [first, second]


def test_dotted_abbreviations_and_quoted_sentences_are_kept_together():
    assert speech_sentences('U.S. 시장입니다. Dr. Kim은 "좋습니다!"라고 말했습니다.') == [
        "U.S. 시장입니다.", 'Dr. Kim은 "좋습니다!"라고 말했습니다.']
    assert normalize_for_speech("U.S. GDP는 늘었습니다.") == "유에스 지디피는 늘었습니다."


def test_sentence_boundaries_work_without_spaces_and_keep_original_caption_text():
    original = "106.65달러입니다.다음은 1.8%입니다! 마지막입니다?"
    pieces = speech_sentences(original)
    assert pieces == ["106.65달러입니다.", "다음은 1.8%입니다!", "마지막입니다?"]
    assert "".join(pieces).replace(" ", "") == original.replace(" ", "")
    assert original == "106.65달러입니다.다음은 1.8%입니다! 마지막입니다?"


def test_excessively_long_narration_splits_at_clauses_without_losing_words():
    original = ("원문에 있는 내용을 이어서 자연스럽게 설명합니다, " * 18).rstrip(", ") + "."
    pieces = speech_sentences(original)
    assert len(pieces) > 1
    assert all(len(piece) <= 300 for piece in pieces)
    assert re.sub(r"\s", "", "".join(pieces)) == re.sub(r"\s", "", original)
    assert all(piece.endswith((",", ".")) for piece in pieces)


def test_indivisible_tokens_are_never_sliced_to_fit_subtitle_width():
    original = "가" * 350 + "."
    assert speech_sentences(original) == [original]
    assert speech_sentences("   ") == []
    with pytest.raises(ValueError):
        speech_sentences("문장입니다.", max_length=0)

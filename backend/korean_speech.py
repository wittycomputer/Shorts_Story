"""Conservative Korean reading forms for TTS, separate from displayed captions.

The functions here never change a project's source or narration.  Call
``normalize_for_speech`` only for text passed to the speech model, and keep the
original ``speech_sentences`` strings for captions.  This is not a general
Korean grapheme-to-phoneme engine; ambiguous names and identifiers are retained.
"""
from __future__ import annotations

import re
import unicodedata


_DIGITS = "영일이삼사오육칠팔구"
_SMALL_UNITS = ("", "십", "백", "천")
_LARGE_UNITS = ("", "만", "억", "조", "경", "해", "자", "양", "구", "간", "정")
_NUMBER = r"[+\-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_NATIVE_ONES = ("", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉")
_NATIVE_TENS = ("", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔")
_COUNTERS = ("시간", "번째", "켤레", "송이", "봉지", "마리", "가지", "명", "개", "살", "잔",
             "권", "대", "곳", "번", "채", "병", "박", "달", "시")
_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (
    "에이", "비", "씨", "디", "이", "에프", "지", "에이치", "아이", "제이", "케이", "엘", "엠",
    "엔", "오", "피", "큐", "알", "에스", "티", "유", "브이", "더블유", "엑스", "와이", "지")))
_WORDS = {
    "hugging face": "허깅 페이스", "huggingface": "허깅 페이스", "firebase": "파이어베이스",
    "firestore": "파이어스토어", "flutter": "플러터", "ffmpeg": "에프에프엠펙",
    "qwen": "큐웬", "nvidia": "엔비디아", "groq": "그록", "reuters": "로이터",
    "yahoo": "야후", "chatgpt": "챗지피티", "openai": "오픈에이아이",
    "3d": "쓰리디", "2d": "투디",
}
_UNITS = {
    "%p": "퍼센트 포인트", "%": "퍼센트", "bp": "베이시스 포인트",
    "km/h": "킬로미터", "m/s": "미터", "km": "킬로미터", "cm": "센티미터",
    "mm": "밀리미터", "Mm": "메가미터", "m": "미터",
    "kg": "킬로그램", "mg": "밀리그램", "Mg": "메가그램", "g": "그램",
    "mL": "밀리리터", "ml": "밀리리터", "ML": "메가리터", "Ml": "메가리터", "L": "리터", "l": "리터",
    "GB": "기가바이트", "Gb": "기가비트", "MB": "메가바이트", "Mb": "메가비트",
    "kB": "킬로바이트", "KB": "킬로바이트", "kb": "킬로비트", "Kb": "킬로비트",
    "Wh": "와트시", "kWh": "킬로와트시", "MWh": "메가와트시", "mWh": "밀리와트시", "GWh": "기가와트시",
    "W": "와트", "kW": "킬로와트", "MW": "메가와트", "mW": "밀리와트", "GW": "기가와트",
    "°C": "도", "°c": "도", "℃": "도", "°F": "도", "°f": "도", "℉": "도",
}
# SI prefixes and bit/byte symbols are case-sensitive: mW != MW, Mb != MB.
# An unknown casing is retained, rather than guessed as a different quantity.
_UNIT_PATTERN = "|".join(re.escape(unit) for unit in sorted(_UNITS, key=len, reverse=True))
_RANGE_UNIT = r"(?:달러|유로|파운드|위안|엔|원|퍼센트|%p|%|명|개|년|개월|일|분|초|배|도)"
_AFTER_COUNTER = r"(?=$|[\s.,!?。！？;:)\]}·…%\"'’”]|(?:입니다|입니까|이었다|였|으로|로|은|는|이|가|을|를|과|와|에|의|도|만|씩|마다|정도|가량|부터|까지|미만|초과|이상|이하))"


def _integer(value: str) -> str:
    digits = value.replace(",", "")
    if len(digits) > 1 and digits.startswith("0"):
        return " ".join(_DIGITS[int(char)] for char in digits)
    if len(digits) > 4 * len(_LARGE_UNITS):
        return " ".join(_DIGITS[int(char)] for char in digits)
    number = int(digits)
    if number == 0:
        return _DIGITS[0]
    groups = []
    group_index = 0
    while number:
        number, group = divmod(number, 10000)
        if group:
            syllables = []
            for position in range(3, -1, -1):
                digit = group // (10 ** position) % 10
                if digit:
                    syllables.append(("" if digit == 1 and position else _DIGITS[digit]) + _SMALL_UNITS[position])
            # Korean reads 10,000 as "만" rather than "일만".
            spoken = "".join(syllables)
            if spoken == "일" and group_index == 1:
                spoken = ""
            groups.append(spoken + _LARGE_UNITS[group_index])
        group_index += 1
    return " ".join(reversed(groups))


def _number(value: str) -> str:
    sign = ""
    if value.startswith(("-", "+")):
        sign = "마이너스 " if value[0] == "-" else "플러스 "
        value = value[1:]
    whole, dot, fraction = value.partition(".")
    spoken = _integer(whole)
    if dot:
        spoken += " 점 " + "".join(_DIGITS[int(char)] for char in fraction)
    return sign + spoken


def _with_direction(value: str) -> str:
    last = value.rstrip()[-1]
    final = (ord(last) - 0xAC00) % 28 if 0xAC00 <= ord(last) <= 0xD7A3 else 0
    return value + ("으로" if final not in (0, 8) else "로")


def _range(match: re.Match) -> str:
    left, left_unit, marker, right, right_unit = match.group("left", "lu", "marker", "right", "ru")
    unit = left_unit or right_unit or ""
    first = _number(left) + (" " + unit if unit else "")
    second = _number(right) + (" " + (right_unit or unit) if right_unit or unit else "")
    first, second = first.replace("%p", "퍼센트 포인트").replace("%", "퍼센트"), second.replace("%p", "퍼센트 포인트").replace("%", "퍼센트")
    direction = match.groupdict().get("direction") or ""
    return first + "에서 " + (_with_direction(second) if marker == "→" else second + direction)


def _counter(match: re.Match) -> str:
    raw, counter = match.group("number", "counter")
    value = int(raw)
    if counter == "월":
        spoken = {6: "유", 10: "시"}.get(value, _integer(raw))
        return spoken + "월"
    if counter == "번째" and value == 1:
        return "첫 번째"
    # "30대 남성" is an age group, while "차량 30대" is a count.
    if counter == "대" and value % 10 == 0 and re.match(r"\s*(?:남성|여성|청년|직장인|연령|초반|중반|후반|층)", match.string[match.end():]):
        return _integer(raw) + " 대"
    if 0 < value < 100 and (counter != "시" or value <= 12):
        tens, ones = divmod(value, 10)
        spoken = _NATIVE_TENS[tens] + _NATIVE_ONES[ones]
        if value == 20:
            spoken = "스무"
    else:
        spoken = _integer(raw)
    return spoken + " " + counter


def normalize_for_speech(text: str) -> str:
    """Read unambiguous numbers, units and common abbreviations in Korean.

    The input is not modified. Decimal digits (including trailing zeroes) are
    spoken individually, rather than discarded by a Korean-only tokenizer.
    """
    text = unicodedata.normalize("NFC", text).replace("−", "-")
    # An explicit year removes the month/day ambiguity of short slash dates.
    def date(match: re.Match) -> str:
        year, month, day = map(int, match.groups())
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return match.group(0)
        month_text = {6: "유", 10: "시"}.get(month, _integer(str(month)))
        return f"{_integer(str(year))} 년 {month_text}월 {_integer(str(day))} 일"
    text = re.sub(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)", date, text)
    # In numeric expressions an arrow means a change; a tilde means a range.
    ranges = (rf"(?<![A-Za-z\d.,])(?P<left>{_NUMBER})\s*(?P<lu>{_RANGE_UNIT})?\s*"
              rf"(?P<marker>→|~|∼|–)\s*(?P<right>{_NUMBER})\s*(?P<ru>{_RANGE_UNIT})?(?P<direction>으?로)?")
    text = re.sub(ranges, _range, text)
    # A hyphen is treated as a range only with a shared unit, not an identifier.
    hyphen_range = (rf"(?<![A-Za-z\d.,])(?P<left>{_NUMBER})\s*(?P<lu>{_RANGE_UNIT})?\s*"
                    rf"(?P<marker>-)\s*(?P<right>{_NUMBER})\s*(?P<ru>{_RANGE_UNIT})(?![A-Za-z])")
    text = re.sub(hyphen_range, _range, text)
    currencies = {"US$": "달러", "USD": "달러", "$": "달러", "KRW": "원", "₩": "원",
                  "EUR": "유로", "€": "유로", "GBP": "파운드", "£": "파운드", "JPY": "엔", "CNY": "위안"}
    currency_pattern = "|".join(re.escape(unit) for unit in sorted(currencies, key=len, reverse=True))
    text = re.sub(rf"(?<![A-Za-z])({currency_pattern})\s*({_NUMBER})",
                  lambda m: _number(m[2]) + " " + currencies[m[1]], text)
    def unit(match: re.Match) -> str:
        value, suffix = match.group(1), match.group(2)
        prefix = "시속 " if suffix == "km/h" else "초속 " if suffix == "m/s" else "섭씨 " if suffix in ("°C", "°c", "℃") else "화씨 " if suffix in ("°F", "°f", "℉") else ""
        return prefix + _number(value) + " " + _UNITS[suffix]
    text = re.sub(rf"(?<![A-Za-z\d])({_NUMBER})\s*({_UNIT_PATTERN})(?![A-Za-z])", unit, text)
    # An explicit currency is Sino-Korean. In particular, the native counter
    # 달 (month) must never match the beginning of 달러 (dollar).
    text = re.sub(rf"(?<![A-Za-z\d.,])({_NUMBER})\s*(달러|유로|파운드|위안|엔|원)",
                  lambda m: _number(m[1]) + " " + m[2], text)
    text = re.sub(r"(?<![+\-\dA-Za-z.,])(?P<number>\d+)\s*(?P<counter>월)", _counter, text)
    counters = "|".join(sorted((*_COUNTERS, "월"), key=len, reverse=True))
    # 개월 is a Sino-Korean unit, not the native counter 개 followed by 월.
    text = re.sub(rf"(?<![+\-\dA-Za-z.,])(?P<number>\d+)\s*(?P<counter>{counters}){_AFTER_COUNTER}", _counter, text)
    # Words must be matched before generic capital-letter spelling.
    words = "|".join(re.escape(word) for word in sorted(_WORDS, key=len, reverse=True))
    text = re.sub(rf"(?<![A-Za-z])(?:{words})(?![A-Za-z])", lambda m: _WORDS[m[0].lower()], text, flags=re.IGNORECASE)
    text = re.sub(r"(?<![A-Za-z])(?:[A-Z]\.){2,}(?![A-Za-z])",
                  lambda m: "".join(_LETTERS[c] for c in m[0] if c != "."), text)
    text = re.sub(r"(?<![A-Za-z])[A-Z]{2,10}(?![A-Za-z])", lambda m: "".join(_LETTERS[c] for c in m[0]), text)
    # Avoid inventing readings for version strings / alphanumeric identifiers.
    text = re.sub(rf"(?<![A-Za-z\d.])({_NUMBER})(?![A-Za-z\d]|\.\d)", lambda m: _number(m[1]), text)
    text = re.sub(r"[·ㆍ]", ", ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_long_sentence(sentence: str, max_length: int) -> list[str]:
    """Use clause/word boundaries only; never slice the middle of a word."""
    result = []
    while len(sentence) > max_length:
        window = sentence[:max_length + 1]
        clauses = list(re.finditer(r"[,，;；:：]\s*|(?:지만|으며|하며|이고|때문에)\s+", window))
        if clauses and clauses[-1].end() >= max_length // 2:
            end = clauses[-1].end()
        else:
            spaces = list(re.finditer(r"\s+", window))
            if spaces:
                end = spaces[-1].end()
            else:
                # The next whitespace can exceed the soft limit, preserving an
                # indivisible word, identifier or number exactly.
                next_space = re.search(r"\s+", sentence[max_length:])
                if next_space is None:
                    break
                end = max_length + next_space.end()
        result.append(sentence[:end].strip())
        sentence = sentence[end:].strip()
    if sentence:
        result.append(sentence)
    return result


def speech_sentences(text: str, max_length: int = 300) -> list[str]:
    """Return original complete sentences for TTS, preserving decimal numbers.

    ``max_length`` is a soft safety limit for unusually long input, independent
    of subtitle line width. Ordinary 1–2 sentence scene narration is not cut
    into 40-character utterances. Dates, decimals and common dotted English
    abbreviations are kept intact.
    """
    if max_length <= 0:
        raise ValueError("The sentence length limit must be positive.")
    protected = set()
    for pattern in (r"\d+(?:\.\d+)+", r"(?:[A-Za-z]\.){2,}",
                    r"(?i)\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc)\."):
        for match in re.finditer(pattern, text):
            protected.update(i for i in range(match.start(), match.end()) if text[i] == ".")
    sentences, start, index = [], 0, 0
    while index < len(text):
        char = text[index]
        inside_word = (char == "." and 0 < index < len(text) - 1
                       and text[index - 1].isascii() and text[index - 1].isalnum()
                       and text[index + 1].isascii() and text[index + 1].isalnum())
        if char in ".!?。！？" and index not in protected and not inside_word:
            end = index + 1
            while end < len(text) and text[end] in ".!?。！？\"'’”」』)]}":
                end += 1
            # A quoted exclamation is still part of the surrounding Korean
            # sentence: '"좋습니다!"라고 말했습니다.' must stay one utterance.
            if end > index + 1 and re.match(r"(?:라고|라며|라는|라니|하고|하며|이라고|이라며|이라는)", text[end:]):
                index = end
                continue
            sentence = text[start:end].strip()
            if sentence:
                sentences.extend(_split_long_sentence(sentence, max_length))
            start, index = end, end
        else:
            index += 1
    if text[start:].strip():
        sentences.extend(_split_long_sentence(text[start:].strip(), max_length))
    return sentences

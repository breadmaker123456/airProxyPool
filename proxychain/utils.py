from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

COUNTRY_CODE_TO_NAME = {
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "NL": "Netherlands",
    "SE": "Sweden",
    "NO": "Norway",
    "FI": "Finland",
    "DK": "Denmark",
    "IS": "Iceland",
    "IE": "Ireland",
    "IT": "Italy",
    "ES": "Spain",
    "PT": "Portugal",
    "PL": "Poland",
    "RU": "Russia",
    "UA": "Ukraine",
    "RO": "Romania",
    "HU": "Hungary",
    "CZ": "Czech Republic",
    "SK": "Slovakia",
    "CH": "Switzerland",
    "AT": "Austria",
    "BE": "Belgium",
    "LU": "Luxembourg",
    "CN": "China",
    "TW": "Taiwan",
    "HK": "Hong Kong",
    "MO": "Macau",
    "JP": "Japan",
    "KR": "South Korea",
    "SG": "Singapore",
    "MY": "Malaysia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "ID": "Indonesia",
    "PH": "Philippines",
    "IN": "India",
    "BT": "Bhutan",
    "BD": "Bangladesh",
    "NP": "Nepal",
    "MM": "Myanmar",
    "AU": "Australia",
    "NZ": "New Zealand",
    "BR": "Brazil",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "MX": "Mexico",
    "ZA": "South Africa",
    "AE": "United Arab Emirates",
    "QA": "Qatar",
    "SA": "Saudi Arabia",
    "IL": "Israel",
    "TR": "Turkey",
    "IR": "Iran",
    "IQ": "Iraq",
    "EG": "Egypt",
    "NG": "Nigeria",
    "KE": "Kenya",
}

CHINESE_NAME_TO_CODE = {
    "中国": "CN",
    "香港": "HK",
    "澳門": "MO",
    "澳门": "MO",
    "台湾": "TW",
    "台灣": "TW",
    "日本": "JP",
    "韩国": "KR",
    "南韓": "KR",
    "韩国": "KR",
    "新加坡": "SG",
    "马来西亚": "MY",
    "馬來西亞": "MY",
    "泰国": "TH",
    "泰國": "TH",
    "越南": "VN",
    "印尼": "ID",
    "菲律宾": "PH",
    "菲律賓": "PH",
    "印度": "IN",
    "美国": "US",
    "美國": "US",
    "加拿大": "CA",
    "英国": "GB",
    "英國": "GB",
    "法国": "FR",
    "法國": "FR",
    "德国": "DE",
    "德國": "DE",
    "俄罗斯": "RU",
    "俄羅斯": "RU",
    "澳大利亚": "AU",
    "澳大利亞": "AU",
    "阿根廷": "AR",
    "捷克": "CZ",
    "瑞典": "SE",
    "瑞士": "CH",
    "西班牙": "ES",
    "葡萄牙": "PT",
}

ALIAS_TO_CODE = {
    "UNITED STATES": "US",
    "UNITED KINGDOM": "GB",
    "GREAT BRITAIN": "GB",
    "ENGLAND": "GB",
    "SCOTLAND": "GB",
    "WALES": "GB",
    "SOUTH KOREA": "KR",
    "NORTH KOREA": "KP",
    "KOREA": "KR",
    "HONGKONG": "HK",
    "HONG KONG": "HK",
    "TAIWAN": "TW",
    "MACAU": "MO",
    "UAE": "AE",
    "EMIRATES": "AE",
    "U.S.": "US",
    "USA": "US",
    "US": "US",
    "UK": "GB",
    "VIET NAM": "VN",
    "SAUDI": "SA",
}

COUNTRY_NAME_TO_CODE: dict[str, str] = {}
for code, name in COUNTRY_CODE_TO_NAME.items():
    COUNTRY_NAME_TO_CODE[name.upper()] = code
COUNTRY_NAME_TO_CODE.update(ALIAS_TO_CODE)
COUNTRY_NAME_TO_CODE.update({name.upper(): code for name, code in CHINESE_NAME_TO_CODE.items()})

_FLAG_PATTERN = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
_CODE_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]{2}(?![A-Z0-9])")


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def flag_emoji_to_country_code(flag: str) -> Optional[str]:
    if not flag:
        return None
    if len(flag) < 2:
        return None
    code_points = [ord(ch) for ch in flag]
    # Regional indicator symbols start at 0x1F1E6 representing 'A'
    base = 0x1F1E6
    if any(point < base or point > 0x1F1FF for point in code_points):
        return None
    letters = [chr(point - base + ord("A")) for point in code_points]
    if len(letters) != 2:
        return None
    code = "".join(letters)
    return code if code.isalpha() else None


def _normalise_country_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return COUNTRY_NAME_TO_CODE.get(cleaned.upper())


def derive_country(name: Optional[str], metadata: Mapping[str, Any] | None = None) -> tuple[Optional[str], Optional[str]]:
    """Best-effort extraction of country name and code from proxy metadata."""

    metadata = metadata or {}

    def _normalise_code(raw: Any) -> Optional[str]:
        if not raw:
            return None
        code = str(raw).strip().upper()
        if len(code) != 2:
            return None
        if not code.isalpha():
            return None
        return code

    # Priority 1: explicit code fields
    for key in ("countryCode", "country_code", "code", "cc", "countrycode"):
        code = _normalise_code(metadata.get(key))
        if code:
            return COUNTRY_CODE_TO_NAME.get(code, code), code

    # Priority 2: explicit name fields in metadata
    for key in ("country", "location", "region", "area"):
        val = metadata.get(key)
        if isinstance(val, str):
            mapped_code = COUNTRY_NAME_TO_CODE.get(val.strip().upper())
            if mapped_code:
                return COUNTRY_CODE_TO_NAME.get(mapped_code, mapped_code), mapped_code

    # Priority 3: Chinese name mapping
    if isinstance(metadata.get("country"), str):
        zh_code = CHINESE_NAME_TO_CODE.get(metadata["country"].strip())
        if zh_code:
            return COUNTRY_CODE_TO_NAME.get(zh_code, zh_code), zh_code

    # Priority 4: parse proxy display name
    if name:
        # Emoji flag
        emoji_match = _FLAG_PATTERN.search(name)
        if emoji_match:
            code = flag_emoji_to_country_code(emoji_match.group(0))
            if code:
                return COUNTRY_CODE_TO_NAME.get(code, code), code

        # Bracketed / token codes e.g. [US] US-01
        for token in _CODE_PATTERN.findall(name.upper()):
            if token in COUNTRY_CODE_TO_NAME:
                return COUNTRY_CODE_TO_NAME.get(token, token), token

        # Known aliases from display name
        stripped = re.sub(r"[^\w\u4e00-\u9fff]+", " ", name).strip()
        tokens = filter(None, re.split(r"\s+", stripped))
        for token in tokens:
            mapped = COUNTRY_NAME_TO_CODE.get(token.upper())
            if mapped:
                return COUNTRY_CODE_TO_NAME.get(mapped, mapped), mapped

        # Chinese words embedded in name
        zh_matches = re.findall(r"[\u4e00-\u9fff]{1,3}", name)
        for zh in zh_matches:
            mapped = CHINESE_NAME_TO_CODE.get(zh)
            if mapped:
                return COUNTRY_CODE_TO_NAME.get(mapped, mapped), mapped

    # Fallback: nothing found
    return None, None


def normalise_protocols(protocols: Iterable[str] | None) -> list[str]:
    if protocols is None:
        return []
    result = []
    for item in protocols:
        item = item.strip().lower()
        if not item:
            continue
        result.append(item)
    return result


def parse_protocols_param(raw: str | Iterable[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return normalise_protocols(raw.split(","))
    return normalise_protocols(raw)


def matches_country(query: Optional[str], country_name: Optional[str], country_code: Optional[str]) -> bool:
    if query is None:
        return True
    if not country_name and not country_code:
        return False
    query_clean = query.strip()
    if not query_clean:
        return True
    query_code = COUNTRY_NAME_TO_CODE.get(query_clean.upper())
    if not query_code and len(query_clean) == 2:
        query_code = query_clean.upper()
    if query_code and country_code:
        return query_code == country_code
    if query_code and not country_code:
        return query_code == COUNTRY_NAME_TO_CODE.get(country_name.upper()) if country_name else False
    # No explicit code match, compare names (case-insensitive)
    if country_name and query_clean.lower() in country_name.lower():
        return True
    if country_code and query_clean.upper() == country_code:
        return True
    return False


def bool_from_query(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}

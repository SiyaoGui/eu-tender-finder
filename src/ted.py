"""Query building and result shaping for the TED (Tenders Electronic Daily) Search API v3.

TED is the official EU journal for public procurement. Its search API is public,
free and needs no key: https://docs.ted.europa.eu/api/latest/search.html
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

API_URL = "https://api.ted.europa.eu/v3/notices/search"
PAGE_LIMIT = 250  # TED maximum page size

FIELDS = [
    "publication-number",
    "notice-type",
    "notice-title",
    "title-lot",
    "description-lot",
    "buyer-name",
    "buyer-country",
    "buyer-email",
    "publication-date",
    "deadline-receipt-tender-date-lot",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    "classification-cpv",
    "procedure-type",
    "place-of-performance",
    "document-url-lot",
]

# Notice types that announce an open opportunity (a call for competition).
COMPETITION_TYPES = ["cn-standard", "cn-social", "cn-desg", "subco", "pin-cfc-standard", "pin-cfc-social"]
NOTICE_TYPE_GROUPS = {
    "open_calls": COMPETITION_TYPES,
    "prior_information": ["pin-only", "pin-buyer", "pin-rtl", "pin-tran"],
    "awards": ["can-standard", "can-social", "can-desg", "can-tran", "can-modif"],
}

ISO2_TO_ISO3 = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE", "DK": "DNK",
    "EE": "EST", "FI": "FIN", "FR": "FRA", "DE": "DEU", "GR": "GRC", "EL": "GRC", "HU": "HUN",
    "IE": "IRL", "IT": "ITA", "LV": "LVA", "LT": "LTU", "LU": "LUX", "MT": "MLT", "NL": "NLD",
    "PL": "POL", "PT": "PRT", "RO": "ROU", "SK": "SVK", "SI": "SVN", "ES": "ESP", "SE": "SWE",
    "NO": "NOR", "IS": "ISL", "LI": "LIE", "CH": "CHE", "UK": "GBR", "GB": "GBR",
}

LANG_CODES = {
    "en": "eng", "da": "dan", "de": "deu", "fr": "fra", "sv": "swe", "nl": "nld", "es": "spa",
    "it": "ita", "pl": "pol", "fi": "fin", "pt": "por",
}


class InputError(ValueError):
    """The user input cannot be turned into a valid query."""


def normalize_countries(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        code = str(raw).strip().upper()
        if not code:
            continue
        if len(code) == 2:
            if code not in ISO2_TO_ISO3:
                raise InputError(f"Unknown country code: {raw}")
            code = ISO2_TO_ISO3[code]
        if not re.fullmatch(r"[A-Z]{3}", code):
            raise InputError(f"Country codes must be 2 or 3 letters (DK or DNK), got: {raw}")
        if code not in out:
            out.append(code)
    return out


def normalize_cpv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        digits = re.sub(r"\D", "", str(raw).split("-")[0])
        if not digits:
            continue
        if len(digits) > 8:
            raise InputError(f"CPV codes have 8 digits, got: {raw}")
        code = digits.ljust(8, "0")
        if code not in out:
            out.append(code)
    return out


def _quote(term: str) -> str:
    cleaned = term.replace('"', " ").replace("\\", " ").strip()
    return f'"{cleaned}"'


def build_query(inp: dict[str, Any], today: dt.date | None = None) -> str:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    parts: list[str] = []

    raw_days = inp.get("publishedWithinDays")
    days = 7 if raw_days in (None, "") else int(raw_days)
    if days < 1 or days > 3650:
        raise InputError("publishedWithinDays must be between 1 and 3650")
    since = today - dt.timedelta(days=days - 1)
    parts.append(f"publication-date>={since:%Y%m%d}")

    countries = normalize_countries(inp.get("countries"))
    if countries:
        parts.append(f"buyer-country IN ({' '.join(countries)})")

    cpv = normalize_cpv(inp.get("cpvCodes"))
    if cpv:
        parts.append(f"classification-cpv IN ({' '.join(cpv)})")

    group = inp.get("noticeTypes") or "open_calls"
    if group != "all":
        if group not in NOTICE_TYPE_GROUPS:
            raise InputError(f"noticeTypes must be one of {sorted(NOTICE_TYPE_GROUPS) + ['all']}")
        parts.append(f"notice-type IN ({' '.join(NOTICE_TYPE_GROUPS[group])})")

    keywords = [k for k in (inp.get("keywords") or []) if str(k).strip()]
    if keywords:
        parts.append("(" + " OR ".join(f"FT~{_quote(k)}" for k in keywords) + ")")

    if inp.get("onlyOpenDeadline", True) and group == "open_calls":
        parts.append(f"deadline-receipt-tender-date-lot>={today:%Y%m%d}")

    min_value = inp.get("minEstimatedValue")
    if min_value not in (None, "", 0):
        parts.append(f"estimated-value-lot>={int(float(min_value))}")

    return " AND ".join(parts) + " SORT BY publication-date DESC"


def _pick_lang(value: Any, langs: list[str]) -> str | None:
    """TED returns multilingual fields as {"eng": [...], "dan": [...]}. Pick the best language."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(dict.fromkeys(str(v) for v in value if v)) or None
    if isinstance(value, dict):
        for lang in langs:
            for key in (lang, lang.upper()):
                if value.get(key):
                    return _pick_lang(value[key], langs)
        for v in value.values():
            if v:
                return _pick_lang(v, langs)
    return None


def _uniq(values: Any) -> list[str]:
    if not values:
        return []
    if not isinstance(values, list):
        values = [values]
    return list(dict.fromkeys(str(v) for v in values if v not in (None, "")))


def _date(value: Any) -> str | None:
    vals = _uniq(value)
    if not vals:
        return None
    dates = sorted(v[:10] for v in vals)
    return dates[0]


def _value(values: Any) -> float | None:
    total = 0.0
    found = False
    for v in values or []:
        try:
            total += float(v)
            found = True
        except (TypeError, ValueError):
            continue
    return round(total, 2) if found else None


def shape_notice(n: dict[str, Any], languages: list[str]) -> dict[str, Any]:
    langs = [LANG_CODES.get(l.lower(), l.lower()) for l in languages] + ["eng"]
    pub = n.get("publication-number")
    lot_titles = n.get("title-lot")
    title = _pick_lang(n.get("notice-title"), langs) or _pick_lang(lot_titles, langs)
    currencies = _uniq(n.get("estimated-value-cur-lot"))
    return {
        "noticeId": pub,
        "title": title,
        "buyerName": _pick_lang(n.get("buyer-name"), langs),
        "buyerCountry": ", ".join(_uniq(n.get("buyer-country"))) or None,
        "buyerEmail": ", ".join(_uniq(n.get("buyer-email"))) or None,
        "noticeType": n.get("notice-type"),
        "procedureType": n.get("procedure-type"),
        "publicationDate": _date(n.get("publication-date")),
        "submissionDeadline": _date(n.get("deadline-receipt-tender-date-lot")),
        "estimatedValue": _value(n.get("estimated-value-lot")),
        "currency": currencies[0] if len(currencies) == 1 else (", ".join(currencies) or None),
        "cpvCodes": _uniq(n.get("classification-cpv")),
        "placeOfPerformance": [
            "anywhere" if p.lower().startswith("anyw") else p
            for p in _uniq(n.get("place-of-performance"))
            if len(p) != 3
        ],
        "lotTitles": _uniq((_pick_lang(lot_titles, langs) or "").split("; ")),
        "description": _pick_lang(n.get("description-lot"), langs),
        "tenderDocumentsUrl": (_uniq(n.get("document-url-lot")) or [None])[0],
        "tedUrl": f"https://ted.europa.eu/en/notice/-/detail/{pub}" if pub else None,
        "pdfUrl": f"https://ted.europa.eu/en/notice/{pub}/pdf" if pub else None,
    }

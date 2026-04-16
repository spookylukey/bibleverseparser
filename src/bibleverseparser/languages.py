"""Definition of languages supported for Bible texts."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Language:
    """Metadata for a language."""

    code: str  # 2 letter ISO 639-1 code
    display_name: str


class LANG:
    """Holder for language codes."""

    EN: str = "en"
    TR: str = "tr"
    NL: str = "nl"
    ES: str = "es"
    INTERNAL: str = "internal"


LANGUAGES: list[Language] = [
    Language(code=LANG.EN, display_name="English"),
    Language(code=LANG.NL, display_name="Nederlands"),
    Language(code=LANG.TR, display_name="Türkçe"),
    Language(code=LANG.ES, display_name="Español"),
]

LANGUAGES_LOOKUP: dict[str, Language] = {lang.code: lang for lang in LANGUAGES}


def get_language(code: str) -> Language:
    return LANGUAGES_LOOKUP[code]


DEFAULT_LANGUAGE: Language = get_language(LANG.EN)


def normalize_reference_input_english(query: str) -> str:
    return query.strip().lower()


def normalize_reference_input_turkish(query: str) -> str:
    query = query.strip().replace("'", "")
    query = unicodedata.normalize("NFKD", query)
    query = query.replace("ı", "i")
    query = query.encode("ascii", "ignore").decode("ascii")
    query = query.lower()
    return query


def normalize_reference_input_dutch(query: str) -> str:
    query = query.strip().replace("'", "")
    query = unicodedata.normalize("NFKD", query)
    query = query.encode("ascii", "ignore").decode("ascii")
    query = query.lower()
    return query


def normalize_reference_input_spanish(query: str) -> str:
    query = query.strip().replace("'", "")
    query = unicodedata.normalize("NFKD", query)
    query = query.encode("ascii", "ignore").decode("ascii")
    query = query.lower()
    return query


_NORMALIZE_SEARCH_FUNCS: dict[str, Callable[[str], str]] = {
    LANG.EN: normalize_reference_input_english,
    LANG.TR: normalize_reference_input_turkish,
    LANG.NL: normalize_reference_input_dutch,
    LANG.ES: normalize_reference_input_spanish,
    LANG.INTERNAL: lambda x: x,
}


def normalize_reference_input(language_code: str, query: str) -> str:
    func = _NORMALIZE_SEARCH_FUNCS[language_code]
    return func(query.strip())

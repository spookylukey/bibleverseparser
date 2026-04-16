from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from functools import cache
from typing import Any

from parsy import ParseError, Parser, char_from, generate, regex, string, string_from, whitespace

from .books import (
    get_bible_book_abbreviation_map,
    get_bible_book_name,
    get_bible_book_number,
    get_bible_books,
    is_single_chapter_book,
)
from .constants import BIBLE_BOOK_INFO, BookInfo
from .languages import LANG, normalize_reference_input


@dataclass
class ParsedReference:
    language_code: str
    book_name: str  # Always canonical form
    start_chapter: int | None
    start_verse: int | None
    end_chapter: int | None = None
    end_verse: int | None = None

    def __post_init__(self) -> None:
        self.book_number: int = get_bible_book_number(self.language_code, self.book_name)
        self.internal_book_name: str = get_bible_book_name(LANG.INTERNAL, self.book_number)

        # Normalize to a form where every ParsedReference is potentially a
        # range. This means we can treat ranges and single verses uniformly.
        if self.start_chapter is None and is_single_chapter_book(self.book_number):
            self.start_chapter = 1
            self.end_chapter = 1
        if self.end_chapter is None:
            self.end_chapter = self.start_chapter
        if self.end_verse is None:
            self.end_verse = self.start_verse
        if self.end_chapter is not None and self.start_chapter is not None:
            if self.end_chapter < self.start_chapter:
                raise InvalidVerseReference(
                    f"End chapter {self.end_chapter} is before start chapter {self.start_chapter}"
                )
            if (
                self.end_chapter == self.start_chapter
                and self.end_verse is not None
                and self.start_verse is not None
                and self.end_verse < self.start_verse
            ):
                raise InvalidVerseReference(
                    f"End verse {self.end_verse} is before start verse {self.start_verse}"
                )
        if (
            self.start_chapter is not None
            and self.start_chapter == self.end_chapter
            and self.start_verse == 1
            and self.start_chapter in self.book_info.verse_counts
            and self.end_verse == self.book_info.verse_counts[self.start_chapter]
        ):
            self.start_verse = None
            self.end_verse = None

    def canonical_form(self) -> str:
        """Return the canonical string form of this reference."""
        retval = self.book_name
        if self.start_chapter is not None:
            retval += f" {self.start_chapter}"
            if self.start_verse is not None:
                retval += f":{self.start_verse}"
                if self.end_chapter != self.start_chapter:
                    assert self.end_verse is not None
                    retval += f"-{self.end_chapter}:{self.end_verse}"
                elif self.end_verse != self.start_verse:
                    retval += f"-{self.end_verse}"
        return retval

    def _clone(self, **kwargs: Any) -> ParsedReference:
        return dataclasses.replace(self, **kwargs)

    def translate_to(self, language_code: str) -> ParsedReference:
        """Translate this reference to another language."""
        return self._clone(
            language_code=language_code,
            book_name=get_bible_book_name(language_code, self.book_number),
        )

    def to_internal(self) -> ParsedReference:
        """Translate this reference to internal form."""
        return self.translate_to(LANG.INTERNAL)

    @classmethod
    def from_start_and_end(
        cls, start_parsed_ref: ParsedReference, end_parsed_ref: ParsedReference
    ) -> ParsedReference:
        if start_parsed_ref.language_code != end_parsed_ref.language_code:
            raise InvalidVerseReference(
                f"Language {start_parsed_ref.language_code} != {end_parsed_ref.language_code}"
            )
        if start_parsed_ref.book_name != end_parsed_ref.book_name:
            raise InvalidVerseReference(f"Book {start_parsed_ref.book_name} != {end_parsed_ref.book_name}")

        return cls(
            language_code=start_parsed_ref.language_code,
            book_name=start_parsed_ref.book_name,
            start_chapter=start_parsed_ref.start_chapter,
            start_verse=start_parsed_ref.start_verse,
            end_chapter=end_parsed_ref.end_chapter,
            end_verse=end_parsed_ref.end_verse,
        )

    def is_whole_book(self) -> bool:
        return self.start_chapter is None or (
            is_single_chapter_book(self.book_number) and self.start_verse is None
        )

    def is_whole_chapter(self) -> bool:
        return self.start_chapter is not None and self.start_verse is None

    def whole_book_prefix(self) -> str:
        """Return a prefix string that matches all the verses in the book."""
        return self.book_name + " "

    def is_single_verse(self) -> bool:
        return (
            self.start_verse is not None
            and self.end_chapter == self.start_chapter
            and self.end_verse == self.start_verse
        )

    def is_in_bounds(self) -> bool:
        book_info = self.book_info
        chapter_count = book_info.chapter_count
        if self.is_whole_book():
            return True
        assert self.start_chapter is not None
        assert self.end_chapter is not None
        if self.start_chapter < 1:
            return False
        if self.start_chapter > chapter_count or self.end_chapter > chapter_count:
            return False
        for chapter, verse in [
            (self.start_chapter, self.start_verse),
            (self.end_chapter, self.end_verse),
        ]:
            verse_count = book_info.verse_counts[chapter]
            if verse is None:
                continue
            if verse > verse_count:
                return False
        return True

    def get_start(self) -> ParsedReference:
        if self.is_single_verse():
            return self
        start_chapter = self.start_chapter if self.start_chapter is not None else 1
        start_verse = self.start_verse if self.start_verse is not None else 1
        return self._clone(
            start_chapter=start_chapter,
            start_verse=start_verse,
            end_chapter=start_chapter,
            end_verse=start_verse,
        )

    def get_end(self) -> ParsedReference:
        if self.is_single_verse():
            return self
        end_chapter = self.end_chapter if self.end_chapter is not None else self.book_info.chapter_count
        end_verse = self.end_verse if self.end_verse is not None else self.book_info.verse_counts[end_chapter]
        return self._clone(
            start_chapter=end_chapter,
            start_verse=end_verse,
            end_chapter=end_chapter,
            end_verse=end_verse,
        )

    @property
    def book_info(self) -> BookInfo:
        return BIBLE_BOOK_INFO[self.internal_book_name]

    def to_list(self) -> list[ParsedReference]:
        """Return a list of all single-verse ParsedReferences in this range."""
        start_ref = self.get_start()
        end_ref = self.get_end()
        assert start_ref.book_number == end_ref.book_number
        book_info = self.book_info
        assert start_ref.start_chapter is not None
        assert end_ref.start_chapter is not None
        assert start_ref.start_verse is not None
        assert end_ref.start_verse is not None
        assert start_ref.start_chapter <= end_ref.start_chapter
        if start_ref.start_chapter == end_ref.start_chapter:
            assert start_ref.start_verse <= end_ref.start_verse

        results: list[ParsedReference] = []
        current_ref = start_ref
        while True:
            results.append(current_ref)
            assert current_ref.start_verse is not None
            assert current_ref.start_chapter is not None
            verse_num = current_ref.start_verse + 1
            next_ref = dataclasses.replace(current_ref, start_verse=verse_num, end_verse=verse_num)
            assert next_ref.start_chapter is not None
            verses_in_chapter = book_info.verse_counts[next_ref.start_chapter]
            if next_ref.start_verse is not None and next_ref.start_verse > verses_in_chapter:
                chapter_num = next_ref.start_chapter + 1
                verse_num = 1
                next_ref = dataclasses.replace(
                    next_ref,
                    start_chapter=chapter_num,
                    end_chapter=chapter_num,
                    start_verse=verse_num,
                    end_verse=verse_num,
                )
            assert next_ref.start_chapter is not None
            assert next_ref.start_verse is not None
            if next_ref.start_chapter > end_ref.start_chapter:
                break
            if next_ref.start_chapter == end_ref.start_chapter and next_ref.start_verse > end_ref.start_verse:
                break
            current_ref = next_ref
        return results


class InvalidVerseReference(ValueError):
    pass


# Generic parsing utilities


def dict_map(d: dict[str, str]) -> Parser:
    """Return a parser that matches any key from the dict and returns the corresponding value."""
    return string_from(*d.keys()).map(lambda v: d[v])


# Specific parsing components


@cache
def book_strict(language_code: str) -> Parser:
    """Return a parser for a Bible book, strict mode (canonical only)."""
    return string_from(*get_bible_books(language_code))


@cache
def book_loose(language_code: str) -> Parser:
    """Return a parser for a Bible book, loose mode."""
    return dict_map(get_bible_book_abbreviation_map(language_code)).desc(
        f"Expected Bible book in {language_code}"
    )


number: Parser = regex(r"[0-9]+").map(int)
chapter: Parser = number.desc("chapter number [0-9]+")
verse: Parser = number.desc("verse number [0-9]+")

verse_range_sep: Parser = string("-") | string("\u2013")
chapter_verse_sep: Parser = string(":")
chapter_verse_sep_loose: Parser = char_from(":v.").result(":")

optional_whitespace: Parser = whitespace.optional()
optional_space: Parser = string(" ").optional()
optional_chapter_verse_sep: Parser = chapter_verse_sep.optional()
optional_verse_range_sep: Parser = verse_range_sep.optional()
optional_chapter_verse_sep_loose: Parser = chapter_verse_sep_loose.optional()
optional_chapter: Parser = chapter.optional()
verse_or_chapter: Parser = verse | chapter


def bible_reference_parser_for_lang(language_code: str, strict: bool) -> Parser:
    """Return a Bible reference parser for the language.

    If strict=True, only canonical references are allowed.
    Otherwise looser checks are done, but it is assumed
    that the input is already case normalized.
    """
    if strict:

        @generate
        def bible_reference_strict() -> Any:
            start_chapter: int | None = None
            start_verse: int | None = None
            end_chapter: int | None = None
            end_verse: int | None = None
            book_name: str = yield book_strict(language_code)
            break1 = yield optional_space
            if break1 is not None:
                start_chapter = yield chapter
                sep1 = yield optional_chapter_verse_sep
                if sep1 is not None:
                    start_verse = yield verse
                    sep2 = yield optional_verse_range_sep
                    if sep2 is not None:
                        v_or_c: int = yield verse_or_chapter
                        sep3 = yield optional_chapter_verse_sep
                        if sep3 is None:
                            end_verse = v_or_c
                        else:
                            end_chapter = v_or_c
                            end_verse = yield verse

            return ParsedReference(
                language_code=language_code,
                book_name=book_name,
                start_chapter=start_chapter,
                start_verse=start_verse,
                end_chapter=end_chapter,
                end_verse=end_verse,
            )

        return bible_reference_strict
    else:

        @generate
        def bible_reference_loose() -> Any:
            start_chapter: int | None = None
            start_verse: int | None = None
            end_chapter: int | None = None
            end_verse: int | None = None
            yield optional_whitespace
            book_name: str = yield book_loose(language_code)
            break1 = yield optional_whitespace
            if break1 is not None:
                start_chapter = yield optional_chapter
                yield optional_whitespace
                if start_chapter is not None:
                    sep1 = yield optional_chapter_verse_sep_loose
                    yield optional_whitespace
                    if sep1 is not None:
                        start_verse = yield verse
                        yield optional_whitespace
                        sep2 = yield optional_verse_range_sep
                        if sep2 is not None:
                            yield optional_whitespace
                            v_or_c: int = yield verse_or_chapter
                            yield optional_whitespace
                            sep3 = yield optional_chapter_verse_sep_loose
                            if sep3 is None:
                                end_verse = v_or_c
                            else:
                                end_chapter = v_or_c
                                yield optional_whitespace
                                end_verse = yield verse
            yield optional_whitespace

            return ParsedReference(
                language_code=language_code,
                book_name=book_name,
                start_chapter=start_chapter,
                start_verse=start_verse,
                end_chapter=end_chapter,
                end_verse=end_verse,
            )

        return bible_reference_loose


def parse_validated_localized_reference(language_code: str, localized_reference: str) -> ParsedReference:
    """Parse a validated reference, returning a ParsedReference.

    Raises InvalidVerseReference if there is any error.
    Should be used only for Bible references that already conform
    to the correct format.
    """
    try:
        return bible_reference_parser_for_lang(language_code, True).parse(localized_reference)
    except ParseError as e:
        raise InvalidVerseReference(
            f"Could not parse '{localized_reference}' as bible reference - {e!s}"
        ) from e


def parse_validated_internal_reference(internal_reference: str) -> ParsedReference:
    """Parse a reference in internal form."""
    return parse_validated_localized_reference(LANG.INTERNAL, internal_reference)


def parse_unvalidated_localized_reference(
    language_code: str,
    localized_reference: str,
    allow_whole_book: bool = True,
    allow_whole_chapter: bool = True,
) -> ParsedReference | None:
    """Parse user input as a Bible reference, returning a ParsedReference.

    Returns None if it doesn't look like a reference (doesn't parse),
    or raises InvalidVerseReference if it does but isn't correct
    (for example, if the chapter/verse numbers are out of valid range).

    If allow_whole_chapter==False, will return None for references
    that are whole chapters.

    If allow_whole_book==False, will return None for references
    that are entire books.
    """
    q = normalize_reference_input(language_code, localized_reference)
    try:
        parsed_ref = bible_reference_parser_for_lang(language_code, False).parse(q)
    except ParseError:
        return None
    if not allow_whole_chapter and parsed_ref.is_whole_chapter():
        return None
    if not allow_whole_book and parsed_ref.is_whole_book():
        if parsed_ref.is_whole_chapter() and allow_whole_chapter:
            pass
        else:
            return None
    return parsed_ref


def parse_passage_title_partial_loose(language_code: str, title: str) -> tuple[ParsedReference | None, bool]:
    """If possible, parse the initial part of a title as a bible reference.

    Returns (parsed_ref, True) for a complete parse with no remainder,
    (parsed_ref, False) for a partial parse, or (None, False) on failure.
    """
    title_norm = normalize_reference_input(language_code, title)
    try:
        result = bible_reference_parser_for_lang(language_code, False).parse_partial(title_norm)
        parsed_ref: ParsedReference = result[0]
        remainder = str(result[1])
    except (ParseError, InvalidVerseReference):
        return None, False

    if len(remainder) > 0 and re.match(r"\w", remainder[0]):
        return None, False

    return parsed_ref, (len(remainder.strip()) == 0)


def localize_internal_reference(language_code: str, internal_reference: str) -> str:
    """Convert an internal reference to a localized canonical form."""
    return parse_validated_internal_reference(internal_reference).translate_to(language_code).canonical_form()


def internalize_localized_reference(language_code: str, localized_reference: str) -> str:
    """Convert a localized reference to internal canonical form."""
    return (
        parse_validated_localized_reference(language_code, localized_reference).to_internal().canonical_form()
    )


def parse_break_list(breaks: str) -> list[ParsedReference]:
    """Parse a break list (comma-separated internal references)."""
    try:
        return (bible_reference_parser_for_lang(LANG.INTERNAL, True).sep_by(string(","))).parse(breaks)
    except ParseError as exc:
        raise ValueError(f"'{breaks}' is not a valid list of internal Bible references") from exc

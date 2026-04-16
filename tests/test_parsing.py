import pytest

from bibleverseparser.books import get_bible_book_number, get_bible_books, is_single_chapter_book
from bibleverseparser.languages import LANG, LANGUAGES, normalize_reference_input_turkish
from bibleverseparser.parsing import (
    InvalidVerseReference,
    ParsedReference,
    internalize_localized_reference,
    localize_internal_reference,
    parse_break_list,
    parse_passage_title_partial_loose,
    parse_unvalidated_localized_reference,
    parse_validated_internal_reference,
    parse_validated_localized_reference,
)


def pv(lang: str, ref: str) -> ParsedReference:
    """parse_validated_localized_reference, with extra checks."""
    retval = parse_validated_localized_reference(lang, ref)
    assert retval.canonical_form() == ref
    return retval


def pu(lang: str, query: str, **kwargs: bool) -> ParsedReference | None:
    """parse_unvalidated_localized_reference."""
    return parse_unvalidated_localized_reference(lang, query, **kwargs)


# ---- Basic parsing tests ----


class TestUnparsable:
    def test_unparsable_strict(self) -> None:
        with pytest.raises(InvalidVerseReference):
            pv(LANG.EN, "Garbage")
        with pytest.raises(InvalidVerseReference):
            pv(LANG.EN, "Genesis 1:x")

    def test_unparsable_loose(self) -> None:
        assert pu(LANG.EN, "Garbage") is None
        assert pu(LANG.EN, "Genesis 1:x") is None


class TestBadOrder:
    def test_bad_order_strict(self) -> None:
        with pytest.raises(InvalidVerseReference):
            pv(LANG.EN, "Genesis 1:3-2")
        with pytest.raises(InvalidVerseReference):
            pv(LANG.EN, "Genesis 2:1-1:10")

    def test_bad_order_loose(self) -> None:
        with pytest.raises(InvalidVerseReference):
            pu(LANG.EN, "genesis 1:3-2")
        with pytest.raises(InvalidVerseReference):
            pu(LANG.EN, "genesis 2:1 - 1:10")


# ---- Single references ----


def test_book() -> None:
    parsed = pv(LANG.EN, "Genesis 1")
    assert parsed.book_number == 0
    assert parsed.book_name == "Genesis"
    assert parsed.start_chapter == 1
    assert parsed.end_chapter == 1
    assert parsed.start_verse is None
    assert parsed.end_verse is None
    assert not parsed.is_single_verse()
    assert not parsed.is_whole_book()
    assert parsed.is_whole_chapter()


def test_single_verse_strict() -> None:
    parsed = pv(LANG.EN, "Genesis 1:1")
    _test_single_verse(parsed)


def test_single_verse_loose() -> None:
    parsed = pu(LANG.EN, "Gen 1 v 1")
    assert parsed is not None
    _test_single_verse(parsed)


def _test_single_verse(parsed: ParsedReference) -> None:
    assert parsed.book_number == 0
    assert parsed.book_name == "Genesis"
    assert parsed.start_chapter == 1
    assert parsed.end_chapter == 1
    assert parsed.start_verse == 1
    assert parsed.end_verse == 1
    assert parsed.is_single_verse()
    assert not parsed.is_whole_book()
    assert not parsed.is_whole_chapter()
    assert parsed.get_start() == parsed
    assert parsed.get_end() == parsed


# ---- Verse ranges ----


def test_verse_range_strict() -> None:
    parsed = pv(LANG.EN, "Genesis 1:1-2")
    _test_verse_range(parsed)


def test_verse_range_loose() -> None:
    parsed = pu(LANG.EN, "gen 1 v 1 - 2")
    assert parsed is not None
    _test_verse_range(parsed)

    parsed2 = pu(LANG.EN, "Gen 1:1\u20132")
    assert parsed2 is not None
    _test_verse_range(parsed2)


def _test_verse_range(parsed: ParsedReference) -> None:
    assert parsed.book_number == 0
    assert parsed.book_name == "Genesis"
    assert parsed.start_chapter == 1
    assert parsed.end_chapter == 1
    assert parsed.start_verse == 1
    assert parsed.end_verse == 2
    assert not parsed.is_single_verse()
    assert not parsed.is_whole_book()
    assert not parsed.is_whole_chapter()

    start = parsed.get_start()
    assert start.start_chapter == 1
    assert start.end_chapter == 1
    assert start.start_verse == 1
    assert start.end_verse == 1

    end = parsed.get_end()
    assert end.start_chapter == 1
    assert end.end_chapter == 1
    assert end.start_verse == 2
    assert end.end_verse == 2


def test_verse_range_2_strict() -> None:
    parsed = pv(LANG.EN, "Genesis 1:2-3:4")
    _test_verse_range_2(parsed)


def test_verse_range_2_loose() -> None:
    parsed = pu(LANG.EN, "gen 1v2 - 3v4")
    assert parsed is not None
    _test_verse_range_2(parsed)


def _test_verse_range_2(parsed: ParsedReference) -> None:
    assert parsed.start_chapter == 1
    assert parsed.end_chapter == 3
    assert parsed.start_verse == 2
    assert parsed.end_verse == 4
    assert not parsed.is_single_verse()
    assert not parsed.is_whole_book()
    assert not parsed.is_whole_chapter()

    start = parsed.get_start()
    assert start.start_chapter == 1
    assert start.end_chapter == 1
    assert start.start_verse == 2
    assert start.end_verse == 2

    end = parsed.get_end()
    assert end.start_chapter == 3
    assert end.end_chapter == 3
    assert end.start_verse == 4
    assert end.end_verse == 4


# ---- from_start_and_end ----


def test_from_start_and_end() -> None:
    parsed = pv(LANG.EN, "Genesis 1:2-3:4")
    combined = ParsedReference.from_start_and_end(parsed.get_start(), parsed.get_end())
    assert parsed == combined

    parsed2 = pv(LANG.EN, "Genesis 1:1")
    combined2 = ParsedReference.from_start_and_end(parsed2.get_start(), parsed2.get_end())
    assert parsed2 == combined2

    parsed3 = pv(LANG.EN, "Genesis 1")
    combined3 = ParsedReference.from_start_and_end(parsed3.get_start(), parsed3.get_end())
    assert parsed3 == combined3


# ---- Parametric test: all books in all languages ----


TESTDATA_PARSE_BOOKS = [(lang, book) for lang in LANGUAGES for book in get_bible_books(lang.code)]


@pytest.mark.parametrize("lang,book", TESTDATA_PARSE_BOOKS)
def test_parse_books(lang: object, book: str) -> None:
    from bibleverseparser.languages import Language

    assert isinstance(lang, Language)
    result = pu(lang.code, book, allow_whole_book=True)
    assert result is not None
    r = result.canonical_form()
    book_number = get_bible_book_number(lang.code, book)
    if is_single_chapter_book(book_number):
        assert r == book + " 1"
    else:
        assert r == book


# ---- Single chapter books ----


def test_single_chapter_books() -> None:
    parsed = pu(LANG.EN, "Jude")
    assert parsed is not None
    assert parsed.canonical_form() == "Jude 1"
    assert parsed.is_whole_book()
    assert parsed.is_whole_chapter()


# ---- Constraints ----


def test_constraints() -> None:
    result1 = pu(LANG.EN, "Matt 1", allow_whole_book=False, allow_whole_chapter=True)
    assert result1 is not None
    assert result1.canonical_form() == "Matthew 1"

    assert pu(LANG.EN, "Matt 1", allow_whole_book=False, allow_whole_chapter=False) is None

    result2 = pu(LANG.EN, "Matt", allow_whole_book=True, allow_whole_chapter=True)
    assert result2 is not None
    assert result2.canonical_form() == "Matthew"

    assert pu(LANG.EN, "Matt", allow_whole_book=False, allow_whole_chapter=True) is None

    result3 = pu(LANG.EN, "Jude", allow_whole_book=False, allow_whole_chapter=True)
    assert result3 is not None
    assert result3.canonical_form() == "Jude 1"


# ---- Invalid references ----


def test_invalid_references() -> None:
    with pytest.raises(InvalidVerseReference):
        pv(LANG.EN, "Matthew 2:1-1:2")
    with pytest.raises(InvalidVerseReference):
        pu(LANG.EN, "Matthew 2:1-1:2")


# ---- Turkish references ----


@pytest.mark.parametrize(
    "input_ref,output_ref",
    [
        ("1. Timoteos 3:16", "1. Timoteos 3:16"),
        ("1 Timoteos 3:16", "1. Timoteos 3:16"),
        ("1Timoteos 3:16", "1. Timoteos 3:16"),
        ("1tim 3.16", "1. Timoteos 3:16"),
        ("Yasanın Tekrarı 1", "Yasa'nın Tekrarı 1"),
        ("YARATILIS 2:3", "Yaratılış 2:3"),
        ("YARAT\u0130L\u0130S 2:3", "Yaratılış 2:3"),
        ("yaratilis 2:3", "Yaratılış 2:3"),
        ("colde sayim 4:5", "\u00c7\u00f6lde Sayım 4:5"),
        ("EY\u00dcP 1", "Ey\u00fcp 1"),
    ],
)
def test_turkish_reference_parsing(input_ref: str, output_ref: str) -> None:
    result = pu(LANG.TR, input_ref)
    assert result is not None, f"Failed to parse '{input_ref}'"
    assert result.canonical_form() == output_ref, f"Failure parsing '{input_ref}'"


def test_turkish_reference_normalization() -> None:
    assert (
        normalize_reference_input_turkish(
            "  \u00c2\u00e2\u0130I\u0069\u0131\u00c7\u00e7\u015e\u015f\u00d6\u00f6\u00dc\u00fc\u011e\u011f  "
        )
        == "aaiiiiccssoouugg"
    )


# ---- Dutch references ----


@pytest.mark.parametrize(
    "input_ref,output_ref",
    [
        ("Openbaringen 1:1", "Openbaring 1:1"),
        ("Openb. 1:1", "Openbaring 1:1"),
        ("openb 1:1", "Openbaring 1:1"),
        ("2 Tim\u00f3the\u00fcs 1:3", "2 Timothe\u00fcs 1:3"),
        ("2 Timote\u00fcs 1:3", "2 Timothe\u00fcs 1:3"),
        ("2 Timoteus 1:3", "2 Timothe\u00fcs 1:3"),
        ("Psalmen 1", "Psalm 1"),
        ("Psalmen 1:1", "Psalm 1:1"),
    ],
)
def test_dutch_reference_parsing(input_ref: str, output_ref: str) -> None:
    result = pu(LANG.NL, input_ref)
    assert result is not None, f"Failed to parse '{input_ref}'"
    assert result.canonical_form() == output_ref, f"Failure parsing '{input_ref}'"


def test_dutch_reference_normalization() -> None:
    assert normalize_reference_input_turkish("  \u00c9\u00fc\u00e9\u00dc  ") == "eueu"


# ---- to_list ----


def test_to_list() -> None:
    def assert_list_equal(ref: str, ref_list: list[str]) -> None:
        parsed_ref = pv("en", ref)
        assert parsed_ref.to_list() == [pv("en", r) for r in ref_list]

    assert_list_equal("Genesis 1:1", ["Genesis 1:1"])
    assert_list_equal("Genesis 1:1-2", ["Genesis 1:1", "Genesis 1:2"])
    assert_list_equal(
        "Genesis 1:30-2:2",
        ["Genesis 1:30", "Genesis 1:31", "Genesis 2:1", "Genesis 2:2"],
    )
    assert_list_equal("Genesis 1:30-31", ["Genesis 1:30", "Genesis 1:31"])
    assert_list_equal(
        "Psalm 23",
        [f"Psalm 23:{v}" for v in range(1, 7)],
    )
    assert_list_equal("Jude 1:25", ["Jude 1:25"])


# ---- get_start and get_end ----


def test_get_start_and_get_end() -> None:
    assert pv("en", "Genesis 1:1-2").get_start().canonical_form() == "Genesis 1:1"
    assert pv("en", "Genesis 1:1-2").get_end().canonical_form() == "Genesis 1:2"

    assert pv("en", "Genesis 1").get_start().canonical_form() == "Genesis 1:1"
    assert pv("en", "Genesis 1").get_end().canonical_form() == "Genesis 1:31"

    assert pv("en", "Genesis 1:5-3:10").get_start().canonical_form() == "Genesis 1:5"
    assert pv("en", "Genesis 1:5-3:10").get_end().canonical_form() == "Genesis 3:10"


# ---- to_list_whole_book ----


def test_to_list_whole_book() -> None:
    parsed_ref = pv("en", "Genesis")
    refs = [item.canonical_form() for item in parsed_ref.to_list()]
    assert refs[0] == "Genesis 1:1"
    assert refs[1] == "Genesis 1:2"
    assert refs[-1] == "Genesis 50:26"


# ---- is_in_bounds ----


def test_is_in_bounds() -> None:
    good_ref = pu(LANG.EN, "Gen 1:1")
    assert good_ref is not None
    assert good_ref.is_in_bounds()

    bad_ref_1 = pu(LANG.EN, "Gen 100:1")
    assert bad_ref_1 is not None
    assert not bad_ref_1.is_in_bounds()

    bad_ref_2 = pu(LANG.EN, "Gen 1:100")
    assert bad_ref_2 is not None
    assert not bad_ref_2.is_in_bounds()


def test_is_in_bounds_whole_chapter() -> None:
    good_ref = pu(LANG.EN, "Psalm 117")
    assert good_ref is not None
    assert good_ref.is_in_bounds()


def test_is_in_bounds_chapter_zero() -> None:
    r1 = pu(LANG.EN, "1 Corinthians 0")
    assert r1 is not None
    assert not r1.is_in_bounds()

    r2 = pu(LANG.EN, "1 Corinthians 0:1")
    assert r2 is not None
    assert not r2.is_in_bounds()

    r3 = pu(LANG.EN, "1 Corinthians 0:1-0:2")
    assert r3 is not None
    assert not r3.is_in_bounds()


# ---- Translation and localization ----


def test_translate_to() -> None:
    parsed = pv(LANG.EN, "Genesis 1:1")
    dutch = parsed.translate_to(LANG.NL)
    assert dutch.canonical_form() == "Genesis 1:1"  # Same in Dutch
    assert dutch.language_code == LANG.NL


def test_localize_internal_reference() -> None:
    result = localize_internal_reference(LANG.EN, "BOOK0 1:1")
    assert result == "Genesis 1:1"


def test_internalize_localized_reference() -> None:
    result = internalize_localized_reference(LANG.EN, "Genesis 1:1")
    assert result == "BOOK0 1:1"


def test_to_internal() -> None:
    parsed = pv(LANG.EN, "Genesis 1:1")
    internal = parsed.to_internal()
    assert internal.canonical_form() == "BOOK0 1:1"


# ---- parse_validated_internal_reference ----


def test_parse_validated_internal_reference() -> None:
    parsed = parse_validated_internal_reference("BOOK0 1:1")
    assert parsed.book_number == 0
    assert parsed.start_chapter == 1
    assert parsed.start_verse == 1


# ---- parse_break_list ----


def test_parse_break_list() -> None:
    refs = parse_break_list("BOOK0 1:1,BOOK0 1:2")
    assert len(refs) == 2
    assert refs[0].canonical_form() == "BOOK0 1:1"
    assert refs[1].canonical_form() == "BOOK0 1:2"


def test_parse_break_list_invalid() -> None:
    with pytest.raises(ValueError):
        parse_break_list("garbage")


# ---- parse_passage_title_partial_loose ----


def test_parse_passage_title_partial_loose_complete() -> None:
    parsed, complete = parse_passage_title_partial_loose(LANG.EN, "Genesis 1:1")
    assert parsed is not None
    assert complete is True
    assert parsed.canonical_form() == "Genesis 1:1"


def test_parse_passage_title_partial_loose_partial() -> None:
    parsed, complete = parse_passage_title_partial_loose(LANG.EN, "Genesis 1:1 (NIV)")
    assert parsed is not None
    assert complete is False
    assert parsed.canonical_form() == "Genesis 1:1"


def test_parse_passage_title_partial_loose_garbage() -> None:
    parsed, complete = parse_passage_title_partial_loose(LANG.EN, "not a verse")
    assert parsed is None
    assert complete is False


# ---- whole_book_prefix ----


def test_whole_book_prefix() -> None:
    parsed = pv(LANG.EN, "Genesis 1:1")
    assert parsed.whole_book_prefix() == "Genesis "


# ---- Spanish references ----


@pytest.mark.parametrize(
    "input_ref,output_ref",
    [
        ("Gen 1:1", "G\u00e9nesis 1:1"),
        ("Ap 1:1", "Apocalipsis 1:1"),
        ("Salm 23", "Salmos 23"),
        ("1 Cor 1:1", "1 Corintios 1:1"),
    ],
)
def test_spanish_reference_parsing(input_ref: str, output_ref: str) -> None:
    result = pu(LANG.ES, input_ref)
    assert result is not None, f"Failed to parse '{input_ref}'"
    assert result.canonical_form() == output_ref, f"Failure parsing '{input_ref}'"


# ---- English abbreviation tests ----


@pytest.mark.parametrize(
    "input_ref,output_ref",
    [
        ("Gen 1:1", "Genesis 1:1"),
        ("Gen. 1:1", "Genesis 1:1"),
        ("Ge. 1:1", "Genesis 1:1"),
        ("1 Cor 1:1", "1 Corinthians 1:1"),
        ("1Cor 1:1", "1 Corinthians 1:1"),
        ("Rev 1:1", "Revelation 1:1"),
        ("Rev. 1:1", "Revelation 1:1"),
        ("Ps. 23", "Psalm 23"),
        ("Psalms 23", "Psalm 23"),
        ("Matt 1:1", "Matthew 1:1"),
        ("Mt. 1:1", "Matthew 1:1"),
        ("1 Kgs 1:1", "1 Kings 1:1"),
        ("Song of Songs 1:1", "Song of Solomon 1:1"),
        ("Heb. 11:1", "Hebrews 11:1"),
    ],
)
def test_english_abbreviation_parsing(input_ref: str, output_ref: str) -> None:
    result = pu(LANG.EN, input_ref)
    assert result is not None, f"Failed to parse '{input_ref}'"
    assert result.canonical_form() == output_ref, f"Failure parsing '{input_ref}'"

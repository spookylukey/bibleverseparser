# bibleverseparser

A small Python library that parses Bible verse references (like `Gen 1:1`) into
a canonical form (`Genesis 1:1`).

Supports English, Dutch, Turkish, and Spanish book names, with many common
abbreviations.

## Installation

```bash
pip install bibleverseparser
```

## Quick start

```python
from bibleverseparser import parse_unvalidated_localized_reference

# Parse loose user input
ref = parse_unvalidated_localized_reference("en", "Gen 1:1")
print(ref.canonical_form())  # "Genesis 1:1"

# Handles abbreviations, spacing variations, and different separators
ref = parse_unvalidated_localized_reference("en", "1 Cor 13:4-7")
print(ref.canonical_form())  # "1 Corinthians 13:4-7"

# Returns None for unparseable input
result = parse_unvalidated_localized_reference("en", "not a verse")
assert result is None
```

## Features

- **Loose parsing**: accepts common abbreviations (`Gen`, `Gen.`, `Ge.`, etc.),
  flexible whitespace, and alternative verse/chapter separators (`:`, `v`, `.`)
- **Strict parsing**: validates that a reference is already in canonical form
- **Multi-language**: English (`en`), Dutch (`nl`), Turkish (`tr`), Spanish (`es`)
- **Verse ranges**: `Genesis 1:1-3`, `Genesis 1:2-3:4`
- **Whole chapters**: `Genesis 1`
- **Whole books**: `Genesis`
- **Validation**: checks chapter/verse bounds, correct ordering
- **Translation**: convert references between languages
- **Fully typed**: includes `py.typed` marker and type hints throughout

## API

### `parse_unvalidated_localized_reference(language_code, reference, *, allow_whole_book=True, allow_whole_chapter=True)`

Parse user input. Returns a `ParsedReference` or `None` if it doesn't look like
a reference. Raises `InvalidVerseReference` if it parses but is invalid (e.g.
end verse before start verse).

### `parse_validated_localized_reference(language_code, reference)`

Parse a reference that is expected to be in canonical form. Raises
`InvalidVerseReference` on any error.

### `ParsedReference`

Dataclass with fields:
- `language_code: str`
- `book_name: str` (canonical form)
- `start_chapter: int | None`
- `start_verse: int | None`
- `end_chapter: int | None`
- `end_verse: int | None`

Key methods:
- `canonical_form() -> str`
- `translate_to(language_code) -> ParsedReference`
- `to_internal() -> ParsedReference`
- `is_single_verse() -> bool`
- `is_whole_chapter() -> bool`
- `is_whole_book() -> bool`
- `is_in_bounds() -> bool`
- `get_start() -> ParsedReference`
- `get_end() -> ParsedReference`
- `to_list() -> list[ParsedReference]`

### `localize_internal_reference(language_code, internal_reference) -> str`

Convert an internal reference to a localized canonical string.

### `internalize_localized_reference(language_code, localized_reference) -> str`

Convert a localized reference to an internal canonical string.

## Supported languages

| Code | Language |
|------|----------|
| `en` | English  |
| `nl` | Dutch    |
| `tr` | Turkish  |
| `es` | Spanish  |

## Origin

Extracted from [learnscripture.net](https://github.com/learnscripture/learnscripture.net).

## License

MIT

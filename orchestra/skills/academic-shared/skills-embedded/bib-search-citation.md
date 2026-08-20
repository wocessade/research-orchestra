# Bib Search Citation (Embedded)

**Source:** `bib-search-citation` | **Snapshot:** 2026-06-06
**Pipeline usage:** S6 — local BibTeX library search

## Purpose
Search a local `.bib` file for references by keyword, author, year, or DOI.
Used when the user has an existing BibTeX library and needs to find specific entries.

## Usage
- Read the `.bib` file and parse entries
- Search by: DOI, author name, title keywords, year range
- Return matching entries with full BibTeX
- Flag duplicate entries by DOI
- Check for missing required fields (author, title, journal, year)

## Example Search Commands
```bash
# Search by DOI
python -c "import bib_search; bib_search.lookup('10.1038/s41586-020-2649-2')"

# Search by author + year
python -c "import bib_search; bib_search.search(author='Smith', year=2020)"

# List all entries with missing required fields
python -c "import bib_search; bib_search.validate_completeness()"
```

## Error Handling: Malformed .bib
**Common issues:** Unescaped `%` (comments out the rest of the line in BibTeX), missing comma after field value, braces not balanced in titles. **Fix:** Run `biber --validate-datamodel main` or check with a Python BibTeX parser first. Flag entries that fail to parse — do not silently skip them.

## Field Completeness
Required fields by entry type (minimum for pipeline citation verification):
- `@article`: author, title, journal, year, doi
- `@inproceedings`: author, title, booktitle, year
- `@phdthesis`: author, title, school, year
- `@book`: author/editor, title, publisher, year

Entries missing DOI or two or more required fields → flag for manual verification. Do not invent missing fields.

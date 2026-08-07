#!/usr/bin/env python3
"""Generate a Standard BibTeX file for every publication in _publications.

For each `_publications/*.md` front matter entry this script:
  1. Parses `title`, `permalink`, `venue`, `date`, `category` and `excerpt`.
  2. Rebuilds the `author` field from the text that precedes the first
     `<i>...</i>` marker inside the (HTML) `excerpt`, stripping tags and
     footnote markers.
  3. Emits an `@inproceedings` set when the entry is / reads like a conference
     paper, otherwise an `@article` set, using the last segment of `permalink`
     as the citation key and cleaning / escaping every value for LaTeX/BibTeX.
  4. Writes the result to `files/bibtex/<basename>.bib` — `files/` is already
     listed in `include:` in `_config.yml`, so Jekyll serves it as static
     content at `/files/bibtex/...`.

Additionally it inserts a `bibtexurl:` entry into each markdown front matter
pointing at the generated file using the site-root-relative path that
`_layouts/single.html` renders unmodified.

Only the `bibtexurl` line is added; every other front-matter field (`title`,
`permalink`, `excerpt`, `date`, `venue`, `citation`, ...) is left untouched.

Usage:
    python scripts/generate_bibtex.py
"""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


ROOT = Path(__file__).resolve().parent.parent
PUBS_DIR = ROOT / "_publications"
BIB_DIR = ROOT / "files" / "bibtex"
MD_GLOB = "*.md"


# --------------------------------------------------------------------------- #
# BibTeX helpers
# --------------------------------------------------------------------------- #

def _escape_bib(value: str) -> str:
    """Escape the six characters BibTeX treats as special.

    Order matters (`\\` first or we would double the backslashes we inject).
    Existing LaTeX commands (e.g. `\*`, `\dagger`) stay untouched. Other
    non-ASCII characters are preserved as UTF-8, which modern BibTeX parsers
    accept directly.
    """
    chars = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "%": r"\%",
    }
    return "".join(chars[c] if c in chars else c for c in value)


def _as_val(value: str) -> str:
    return "{" + _escape_bib(value) + "}"


@dataclass
class BibEntry:
    entry_type: str
    key: str
    fields: "dict[str, str]" = field(default_factory=dict)

    def render(self) -> str:
        lines = ["@{0}{{{1},".format(self.entry_type, self.key)]
        # `title` first, then the rest in alphabetical order.
        keys = sorted(self.fields)
        if "title" in keys:
            keys.remove("title")
            keys.insert(0, "title")
        for name in keys:
            lines.append("    {0}={1},".format(name, _as_val(self.fields[name])))
        lines.append("}")
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Front-matter helpers
# --------------------------------------------------------------------------- #

def _dequote_yaml(value: str) -> str:
    """Best-effort recovery of a front-matter string field's content."""
    value = value.strip()
    if not value:
        return value
    if value[0] == '"':
        # Double-quoted YAML scalar.
        if yaml is not None:
            try:
                parsed = yaml.safe_load(value)
                if isinstance(parsed, str):
                    return parsed
            except yaml.YAMLError:
                pass
        return value.strip('"')
    if value[0] == "'":
        # Single-quoted YAML scalar: only '' escapes a quote.
        return value.strip("'").replace("''", "'")
    return value.strip()


def _split_authors(raw: str) -> list[str]:
    """Turn a cleaned, comma-separated author list into `Family, Given` names."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    authors: list[str] = []
    for part in parts:
        toks = part.split()
        if len(toks) >= 2:
            given, family = " ".join(toks[:-1]), toks[-1]
        elif len(toks) == 1:
            given, family = "", toks[0]
        else:
            continue
        if given:
            authors.append("{family}, {given}".format(family=family, given=given))
        else:
            authors.append(family)
    return authors


def _extract_authors(excerpt: str) -> str:
    """Extract the author list from the leading (non-italic) part of `excerpt`."""
    body = _dequote_yaml(excerpt)
    # Everything up to the first <i>...</i> venue marker is the author list.
    if "<i>" in body:
        body = body.split("<i>", 1)[0]
    body = re.sub(r"<[^>]+>", "", body)  # strip tags
    body = html.unescape(body)
    body = re.sub(r"[,;]?\s*et\s+al\.?\s*", "", body)  # "et al." anywhere
    body = re.sub(r"\\\*|\*|\\dagger|†", "", body)
    body = re.sub(r"\s+", " ", body).strip(" ,;&")
    if not body:
        return ""
    authors = _split_authors(body)
    if not authors:
        return ""
    if len(authors) > 15:
        authors = authors[:15]
        authors.append("others")
    return " and ".join(authors)


def _is_conf(category: str, venue: str) -> bool:
    cat = category.strip().lower()
    if cat in {"conferences", "conference", "proceedings"}:
        return True
    if cat in {"manuscripts", "journal", "preprint"}:
        return False
    conf_tokens = (
        "conference",
        "symposium",
        "proceedings",
        "icml",
        "neurips",
        "iccv",
        "cvpr",
        "aaai",
        "iclr",
        "eccv",
        "icassp",
        "miccai",
        "kdd",
        "wacv",
        "vis",
    )
    return any(tok in venue.lower() for tok in conf_tokens)


def parse_front_matter(text: str) -> dict:
    fm = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
    if not fm:
        raise ValueError("missing front matter")
    body = fm.group(1)

    def get(name: str) -> str:
        pat = re.compile(r"(?m)^" + re.escape(name) + r"\s*:\s*(.*?)\s*$")
        m = pat.search(body)
        return m.group(1).strip() if m else ""

    def get_quoted_yaml(name: str) -> str:
        m = re.search(
            r"(?m)^" + re.escape(name) + r"\s*:\s*('(?:[^']|'')*'|\"(?:[^\"\\]|\\.)*\")\s*$",
            body,
        )
        return m.group(1) if m else get(name)

    return {
        "title_raw": get_quoted_yaml("title"),
        "permalink": get("permalink"),
        "excerpt_raw": get_quoted_yaml("excerpt"),
        "date": get("date"),
        "venue": get_quoted_yaml("venue"),
        "category": get("category"),
        "paperurl": get("paperurl"),
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    if yaml is None:
        print("WARNING: 'yaml' is not installed; using regex fallback.",
              file=sys.stderr)

    md_files = sorted(PUBS_DIR.glob(MD_GLOB))
    if not md_files:
        print("No markdown files found under {0}".format(PUBS_DIR), file=sys.stderr)
        return 1

    BIB_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    added_bibtexurl = 0
    skipped_no_permalink = []
    skipped_no_venue = []
    no_paperurl_line = []
    fallback_author = []

    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8")
        try:
            meta = parse_front_matter(text)
        except ValueError as exc:
            print("SKIP {0}: {1}".format(md_path.name, exc))
            continue

        permalink = meta["permalink"].strip()
        if not permalink or not permalink.startswith("/publication/"):
            skipped_no_permalink.append(md_path.name)
            continue

        key = permalink.rstrip("/").rsplit("/", 1)[-1]
        title = _dequote_yaml(meta["title_raw"]).strip()
        venue = _dequote_yaml(meta["venue"]).strip()
        date = meta["date"].strip()
        category = meta["category"].strip()

        year = ""
        m = re.search(r"(19|20)\d{2}", date)
        if m:
            year = m.group(0)

        # --- authors ---
        authors = _extract_authors(meta["excerpt_raw"])
        if not authors:
            authors = "Zelin Zang and others"
            fallback_author.append(md_path.name)

        # --- venue / booktitle ---
        if not venue:
            skipped_no_venue.append(md_path.name)
            booktitle = "Available online"
        else:
            booktitle = venue

        # --- entry type ---
        if _is_conf(category, venue):
            entry_type, container_field = "inproceedings", "booktitle"
        else:
            entry_type, container_field = "article", "journal"

        fields = {
            "author": authors,
            "title": title,
            container_field: booktitle,
        }
        if year:
            fields["year"] = year

        # --- doi ---
        paperurl = meta["paperurl"].strip(" '\"")
        mo = re.search(r"(?:doi\.org/|/doi/)(10\.\S+)", paperurl, re.I)
        if mo:
            fields["doi"] = mo.group(1).rstrip(",.;")

        entry = BibEntry(entry_type=entry_type, key=key, fields=fields)
        bib_path = BIB_DIR / "{0}.bib".format(md_path.stem)
        bib_path.write_text(entry.render(), encoding="utf-8")
        generated += 1

        # --- bibtexurl insertion (idempotent) ---
        url = "/files/bibtex/{0}.bib".format(md_path.stem)
        existing_url = None
        murl = re.search(r"(?m)^bibtexurl\s*:\s*['\"]?([^'\"]*)['\"]?\s*$", text)
        if murl:
            existing_url = murl.group(1).strip()
        if existing_url == url:
            pass  # already correct
        elif "bibtexurl:" in text:
            def _replace_url(m: re.Match) -> str:
                return "bibtexurl: '{0}'".format(url)
            md_path.write_text(
                re.sub(r"(?m)^bibtexurl\s*:\s*.*$", _replace_url, text, count=1),
                encoding="utf-8",
            )
            added_bibtexurl += 1
        else:
            pat = re.compile(r"(?m)^paperurl\s*:\s*(.*)$")
            match = pat.search(text)
            if match is None:
                no_paperurl_line.append(md_path.name)
                # No paperurl line: insert bibtexurl INSIDE the front matter,
                # right after the citation: line (before the closing ---).
                text = re.sub(
                    r"(?m)^citation\s*:.*$",
                    lambda m: "{0}\nbibtexurl: '{1}'".format(m.group(0), url),
                    text,
                    count=1,
                )
                md_path.write_text(
                    text,
                    encoding="utf-8",
                )
                added_bibtexurl += 1
            else:
                def _insert(m: re.Match) -> str:
                    return "{0}\nbibtexurl: '/files/bibtex/{1}.bib'".format(m.group(0), md_path.stem)

                # Re-read after the (above) possible update and insert under paperurl.
                text2 = md_path.read_text(encoding="utf-8")
                md_path.write_text(pat.sub(_insert, text2, count=1), encoding="utf-8")
                added_bibtexurl += 1

    print("Generated BibTeX for {0}/{1} publications".format(generated, len(md_files)))
    print("Added bibtexurl to {0} markdown files".format(added_bibtexurl))
    if no_paperurl_line:
        print("bibtexurl inserted after citation (no paperurl line): "
              "{0}".format(", ".join(no_paperurl_line)))
    if skipped_no_permalink:
        print("Skipped (bad permalink): {0}".format(", ".join(skipped_no_permalink)))
    if skipped_no_venue:
        print("Skipped (no venue): {0}".format(", ".join(skipped_no_venue)))
    if fallback_author:
        print("Fallback authors used: {0}".format(", ".join(fallback_author)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

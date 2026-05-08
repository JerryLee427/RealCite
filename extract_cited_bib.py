r"""Build a cited-only BibTeX file from a LaTeX manuscript.

Usage:
    python ../extract_cited_bib.py main.tex ref.bib \
        --output ref_cited.bib \
        --missing-report missing_citations.txt

What the script does:
    1. Starts from the root TeX file such as ``main.tex``.
    2. Recursively follows ``\input{...}`` and ``\include{...}`` files.
    3. Strips LaTeX comments before scanning citation commands.
    4. Collects citation keys in first-appearance order.
    5. Writes only the cited BibTeX entries from the source ``.bib`` file.

Typical project workflow:
    - Source bibliography: ``ref.bib``
    - Generated cited-only bibliography: ``ref_cited.bib``
    - Optional missing-key report: ``missing_citations.txt``

Notes:
    - ``nocite{*}`` is rejected because it requires the full bibliography.
    - The generated cited-only file is meant to be reproducible, so manual
      edits to the output file should be avoided.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

INPUT_RE = re.compile(r"\\(?:input|include)\{([^{}]+)\}")
CITE_CMD_RE = re.compile(r"\\([A-Za-z]*cite[A-Za-z]*|nocite)\*?")
ENTRY_START_RE = re.compile(r"@([A-Za-z]+)\s*([({])")


def strip_comments(text: str) -> str:
    """Remove LaTeX comments while preserving escaped percent signs."""

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        out: list[str] = []
        index = 0
        while index < len(line):
            if line[index] == "%":
                backslashes = 0
                probe = index - 1
                while probe >= 0 and line[probe] == "\\":
                    backslashes += 1
                    probe -= 1
                if backslashes % 2 == 0:
                    break
            out.append(line[index])
            index += 1
        cleaned_lines.append("".join(out))
    return "\n".join(cleaned_lines)


def read_balanced(
    text: str, start: int, open_ch: str, close_ch: str
) -> tuple[str, int]:
    """Read a balanced delimited block and return its content and end index."""

    if start >= len(text) or text[start] != open_ch:
        raise ValueError(f"Expected {open_ch} at position {start}")

    depth = 0
    index = start
    buffer: list[str] = []

    while index < len(text):
        ch = text[index]
        if ch == open_ch:
            depth += 1
            if depth > 1:
                buffer.append(ch)
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return "".join(buffer), index + 1
            buffer.append(ch)
        else:
            buffer.append(ch)
        index += 1

    raise ValueError(f"Unbalanced delimiter starting at position {start}")


def skip_space_and_optionals(text: str, index: int) -> int:
    """Skip whitespace and LaTeX optional arguments like ``[see also]``."""

    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "[":
            _, index = read_balanced(text, index, "[", "]")
            continue
        return index


def collect_tex_sources(root_tex: Path) -> dict[Path, str]:
    """Read the root TeX file and every recursively included child file."""

    seen: dict[Path, str] = {}

    def visit(tex_path: Path) -> None:
        resolved = tex_path.resolve()
        if resolved in seen or not resolved.exists():
            return

        raw = resolved.read_text(encoding="utf-8")
        cleaned = strip_comments(raw)
        seen[resolved] = cleaned

        for rel in INPUT_RE.findall(cleaned):
            child = resolved.parent / rel
            if child.suffix == "":
                child = child.with_suffix(".tex")
            visit(child)

    visit(root_tex)
    return seen


def extract_keys_from_tex(text: str) -> list[str]:
    r"""Extract citation keys from one cleaned TeX source string.

    The parser supports commands such as ``\cite{}``, ``\textcite{}``,
    ``\parencite{}``, and ``\nocite{}``, including optional arguments.
    """

    keys: list[str] = []
    index = 0

    while True:
        match = CITE_CMD_RE.search(text, index)
        if not match:
            break

        index = skip_space_and_optionals(text, match.end())
        groups: list[str] = []

        while index < len(text) and text[index] == "{":
            content, index = read_balanced(text, index, "{", "}")
            groups.append(content)
            index = skip_space_and_optionals(text, index)

        for group in groups:
            for raw_key in group.split(","):
                key = raw_key.strip()
                if not key:
                    continue
                if key == "*":
                    raise SystemExit(
                        "Found nocite{*}. Wildcard citations cannot be reduced to a cited-only bibliography from source text alone."
                    )
                keys.append(key)

    ordered: list[str] = []
    seen = set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def parse_bib_entries(text: str) -> dict[str, str]:
    """Map BibTeX keys to their full raw entry text."""

    entries: dict[str, str] = {}
    index = 0

    while True:
        match = ENTRY_START_RE.search(text, index)
        if not match:
            break

        start = match.start()
        open_ch = match.group(2)
        close_ch = "}" if open_ch == "{" else ")"
        head_end = match.end()

        key_start = head_end
        while key_start < len(text) and text[key_start].isspace():
            key_start += 1

        comma = text.find(",", key_start)
        if comma == -1:
            break

        key = text[key_start:comma].strip()

        depth = 1
        probe = head_end
        while probe < len(text) and depth > 0:
            ch = text[probe]
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
            probe += 1

        if depth != 0:
            raise ValueError(f"Unbalanced BibTeX entry for key: {key}")

        entry_text = text[start:probe].strip()
        entries[key] = entry_text
        index = probe

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract only cited BibTeX entries from a LaTeX manuscript.",
        epilog=(
            "Example: python scripts/extract_cited_bib.py main.tex ref.bib "
            "--output ref_cited.bib --missing-report missing_citations.txt"
        ),
    )
    parser.add_argument(
        "tex",
        type=Path,
        help="Root TeX file to scan, for example main.tex",
    )
    parser.add_argument(
        "bib",
        type=Path,
        help="Source BibTeX database, for example ref.bib",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path for the cited-only BibTeX file",
    )
    parser.add_argument(
        "--missing-report",
        type=Path,
        help="Optional text file that lists citation keys missing from the BibTeX source",
    )
    args = parser.parse_args()

    tex_sources = collect_tex_sources(args.tex)

    ordered_keys: list[str] = []
    seen = set()
    for _, text in tex_sources.items():
        for key in extract_keys_from_tex(text):
            if key not in seen:
                seen.add(key)
                ordered_keys.append(key)

    bib_text = args.bib.read_text(encoding="utf-8")
    bib_entries = parse_bib_entries(bib_text)

    found_entries: list[str] = []
    missing_keys: list[str] = []

    for key in ordered_keys:
        if key in bib_entries:
            found_entries.append(bib_entries[key])
        else:
            missing_keys.append(key)

    output_path = args.output or args.bib.with_name(
        f"{args.bib.stem}_cited.bib"
    )
    output_path.write_text(
        "\n\n".join(found_entries) + ("\n" if found_entries else ""),
        encoding="utf-8",
    )

    if args.missing_report:
        args.missing_report.write_text(
            "\n".join(missing_keys) + ("\n" if missing_keys else ""),
            encoding="utf-8",
        )

    print(f"Scanned {len(tex_sources)} TeX file(s)")
    print(f"Found {len(ordered_keys)} unique citation key(s)")
    print(f"Wrote {len(found_entries)} entry(ies) to {output_path}")
    if missing_keys:
        print(f"Missing {len(missing_keys)} key(s)")
        if args.missing_report:
            print(f"Missing-key report written to {args.missing_report}")
        else:
            print("Missing keys:")
            for key in missing_keys:
                print(f"  - {key}")


if __name__ == "__main__":
    main()

# CiteReal

Extract only the cited BibTeX entries from a LaTeX manuscript into a separate `.bib` file.

## Requirements

Python 3.8+

## Usage

```bash
python extract_cited_bib.py <root.tex> <source.bib> [options]
```

| Argument           | Description                                              |
| ------------------ | -------------------------------------------------------- |
| `tex`              | Root TeX file (e.g. `main.tex`)                          |
| `bib`              | Source BibTeX database (e.g. `ref.bib`)                  |
| `-o, --output`     | Output path (default: `<bib stem>_cited.bib`)            |
| `--missing-report` | File to list citation keys absent from the BibTeX source |

**Example:**

```bash
python extract_cited_bib.py main.tex ref.bib -o ref_cited.bib --missing-report missing.txt
```

## How It Works

1. Starts from the root `.tex` file.
2. Recursively follows `\input{...}` and `\include{...}`.
3. Strips LaTeX comments before scanning.
4. Collects citation keys in first-appearance order.
5. Writes only the cited BibTeX entries to the output file.

## Known Limitations

- **Encoding**: All `.tex` and `.bib` files must be UTF-8 encoded. Files with other encodings (e.g. `cp1252` on Windows) will fail with a `UnicodeDecodeError`.
- **Include packages**: Only `\input` and `\include` are followed. `\subfile`, `\import`, and `\subimport` are not supported.
- **`verbatim` environments**: Citation commands inside `\verb` or `\begin{verbatim}` are not excluded and may produce spurious keys.
- **`nocite{*}`**: Wildcard citations are not supported and will abort the script.
- **Output directory**: The parent directory of `--output` must already exist.

# Litematic Text Schematic Generator

A fully interactive CLI that converts plain text into `.litematic` schematic files for the [Litematica](https://www.curseforge.com/minecraft/mc-mods/litematica) Minecraft mod.

Optimised for **2b2t** (Java 1.20.x) with the **Litematica Icebox Printer** workflow.

---

## Features

- **Complete 5×7 bitmap font** covering all 95 printable ASCII characters
- **Scalable text** — choose from Tiny (1×) up to Massive (6×) or enter a custom scale
- **Multi-line support** — type `\n` inline, split by word count, or one word per line
- **Outline / border** — dilate the text pixels with a chosen block and adjustable thickness
- **Background fill** — flood the bounding box with a backing block
- **Orientations** — VERTICAL (wall / sign) or HORIZONTAL (floor / ground text)
- **Depth control** — multi-layer thick walls or raised floor text
- **Curated 2b2t block palette** — Netherrack, Cobblestone, all 16 Concretes/Wools, emissive blocks, and more — plus a "custom ID" fallback
- **Live summary** before generating: dimensions in blocks and chunks, per-block counts
- **Terminal ASCII preview** before committing to disk
- Outputs native `.litematic` files read directly by Litematica (no conversion needed)

---

## Requirements

- Python ≥ 3.9
- pip packages: `litemapy`, `questionary`, `rich`

---

## Installation

```bash
# Clone the repo (or download the ZIP)
git clone https://github.com/your-username/litematic-text-schematic-generator.git
cd litematic-text-schematic-generator

# Install dependencies
# (--pre is required because litemapy uses pre-release version tags)
pip install --pre -r requirements.txt
```

---

## Usage

```bash
python main.py
```

Follow the interactive prompts:

| Step | What it asks |
|------|-------------|
| 1 | Text to render (supports `\n` for line breaks) |
| 2 | Letter case (preserve / UPPER / lower) |
| 3 | Line splitting strategy |
| 4 | Orientation — VERTICAL wall or HORIZONTAL floor |
| 5 | Font scale (1× – 6× or custom) |
| 6 | Character spacing (pixels, pre-scale) |
| 7 | Line spacing (blocks, post-scale) |
| 8 | Wall depth / layer height |
| 9 | Padding margin (air blocks around the text) |
| 10 | Main text block |
| 11 | Outline block + thickness (optional) |
| 12 | Background block (optional) |
| 13 | Output filename and directory |
| 14 | Author name for litematic metadata |
| 15 | Dimension + block-count summary |
| 16 | ASCII terminal preview |
| 17 | Final confirmation → generates file |

---

## Loading in Litematica

1. Copy the `.litematic` file into your Minecraft saves (or any folder Litematica can browse).
2. In-game press **M** → **Load Schematic** → navigate to the file.
3. Place the schematic anchor in the world and use **Place** mode.
4. With **Icebox Printer**: freeze yourself in ice at the build site, load the schematic, align it, and start printing layer by layer.

---

## Coordinate convention

| Orientation | X axis | Y axis | Z axis |
|-------------|--------|--------|--------|
| VERTICAL    | text width (east) | text height (up) | wall depth (south) |
| HORIZONTAL  | text width (east) | layer height (up) | text height (south) |

When you paste the schematic, the anchor corresponds to the **lower-left-front** corner (minimum X, minimum Y, minimum Z) of the structure.

---

## Block grid cell values

| Value | Meaning |
|-------|---------|
| `0`   | Air (not placed) |
| `1`   | Main text block |
| `2`   | Outline block |
| `3`   | Background block |

---

## Project structure

```
main.py              Entry point
src/
  __init__.py
  font.py            5×7 bitmap font data (all 95 printable ASCII chars)
  renderer.py        Text → 2-D block grid (scale, outline, background, padding)
  schematic.py       litemapy .litematic writer + dimension helpers
  cli.py             Interactive Rich/Questionary CLI
requirements.txt
README.md
```

---

## License

MIT — do whatever you want, attribution appreciated.

"""
Text-to-block-grid renderer.

Pipeline:
  1. Each character is rendered at 1×1 pixel scale using the 5×7 bitmap font.
  2. Characters are joined horizontally with `char_spacing` pixel gaps.
  3. Lines are stacked vertically with `line_spacing` block gaps.
  4. The combined pixel grid is scaled up by `scale` (each pixel → scale×scale blocks).
  5. Outline dilation is applied in the final block space (thickness in actual blocks).
  6. Uniform padding is added around the entire grid.

Grid cell values
----------------
  0  – air
  1  – main text block
  2  – outline block
  3  – background block (optional)
"""

from __future__ import annotations
from .font import get_char_bitmap, CHAR_WIDTH, CHAR_HEIGHT


# ── Type alias ───────────────────────────────────────────────────────────────
Grid = list[list[int]]


# ── Low-level helpers ────────────────────────────────────────────────────────

def _make_grid(rows: int, cols: int, fill: int = 0) -> Grid:
    return [[fill] * cols for _ in range(rows)]


def _char_to_pixels(char: str) -> Grid:
    """Return a CHAR_HEIGHT × CHAR_WIDTH (7×5) pixel grid for one character."""
    bitmap = get_char_bitmap(char)
    return [[1 if pixel == '#' else 0 for pixel in row] for row in bitmap]


def _render_line_pixels(line: str, char_spacing: int) -> Grid:
    """
    Render a single line of text as a pixel grid (before scale-up).
    Returns a CHAR_HEIGHT-row grid whose width equals:
        len(line) * CHAR_WIDTH + max(0, len(line)-1) * char_spacing
    """
    if not line:
        # Render an empty line as a full-width block of spaces
        return _make_grid(CHAR_HEIGHT, CHAR_WIDTH)

    char_grids = [_char_to_pixels(ch) for ch in line]
    gap = max(0, char_spacing)
    total_cols = len(line) * CHAR_WIDTH + max(0, len(line) - 1) * gap
    grid = _make_grid(CHAR_HEIGHT, total_cols)

    x_offset = 0
    for char_grid in char_grids:
        for r in range(CHAR_HEIGHT):
            for c in range(CHAR_WIDTH):
                if char_grid[r][c]:
                    grid[r][x_offset + c] = 1
        x_offset += CHAR_WIDTH + gap

    return grid


def _scale_grid(grid: Grid, scale: int) -> Grid:
    """Scale every pixel by `scale` in both dimensions."""
    if scale == 1:
        return [row[:] for row in grid]
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    scaled = _make_grid(rows * scale, cols * scale)
    for r in range(rows):
        for c in range(cols):
            val = grid[r][c]
            if val:
                for dr in range(scale):
                    for dc in range(scale):
                        scaled[r * scale + dr][c * scale + dc] = val
    return scaled


def _pad_grid(grid: Grid, cols: int, fill: int = 0) -> Grid:
    """Right-pad each row of `grid` to `cols` columns."""
    result = []
    for row in grid:
        if len(row) < cols:
            result.append(row + [fill] * (cols - len(row)))
        else:
            result.append(row[:cols])
    return result


# ── Outline ──────────────────────────────────────────────────────────────────

def _apply_outline(grid: Grid, thickness: int) -> Grid:
    """
    Morphological dilation: fill air cells adjacent (including diagonals) to
    text-block cells (value == 1) with outline cells (value == 2).
    Applied in block space after scaling.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    # Work on a copy to avoid iterating over already-placed outline blocks
    result = [row[:] for row in grid]

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                for dr in range(-thickness, thickness + 1):
                    for dc in range(-thickness, thickness + 1):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if result[nr][nc] == 0:
                                result[nr][nc] = 2
    return result


# ── Background fill ──────────────────────────────────────────────────────────

def _apply_background(grid: Grid) -> Grid:
    """Fill all remaining air cells (0) with background marker (3)."""
    return [[3 if cell == 0 else cell for cell in row] for row in grid]


# ── Padding ──────────────────────────────────────────────────────────────────

def _add_padding(grid: Grid, padding: int) -> Grid:
    """Add `padding` air-block border on all four sides."""
    if padding <= 0:
        return grid
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    new_cols = cols + 2 * padding
    empty_row = [0] * new_cols
    result: Grid = []
    for _ in range(padding):
        result.append(empty_row[:])
    for row in grid:
        result.append([0] * padding + row + [0] * padding)
    for _ in range(padding):
        result.append(empty_row[:])
    return result


# ── Public API ───────────────────────────────────────────────────────────────

def render_text(
    lines: list[str],
    scale: int = 1,
    char_spacing: int = 1,
    line_spacing: int = 2,
    outline: bool = False,
    outline_thickness: int = 1,
    background: bool = False,
    padding: int = 1,
) -> Grid:
    """
    Render a list of text lines to a 2-D block grid.

    Parameters
    ----------
    lines            : list of text strings, one per line.
    scale            : block-per-pixel multiplier (≥1).
    char_spacing     : horizontal gap between characters in pixels (pre-scale).
    line_spacing     : vertical gap between lines in final blocks (post-scale).
    outline          : whether to draw an outline around text.
    outline_thickness: outline width in final blocks (post-scale).
    background       : if True, fill air cells with background block (value 3).
    padding          : border of air blocks added on all four sides.

    Returns
    -------
    2-D list of ints: 0=air, 1=text, 2=outline, 3=background.
    """
    scale = max(1, scale)
    char_spacing = max(0, char_spacing)
    line_spacing = max(0, line_spacing)
    padding = max(0, padding)

    # ── Step 1: render each line at pixel scale, then scale up ───────────────
    scaled_line_grids: list[Grid] = []
    for line in lines:
        pixel_grid = _render_line_pixels(line, char_spacing)
        scaled = _scale_grid(pixel_grid, scale)
        scaled_line_grids.append(scaled)

    # ── Step 2: normalise widths so all lines share the same column count ─────
    max_cols = max((len(g[0]) for g in scaled_line_grids if g), default=CHAR_WIDTH * scale)
    scaled_line_grids = [_pad_grid(g, max_cols) for g in scaled_line_grids]

    # ── Step 3: stack lines with line_spacing gaps ────────────────────────────
    gap_row = [[0] * max_cols]
    combined: Grid = []
    for idx, lg in enumerate(scaled_line_grids):
        combined.extend(lg)
        if idx < len(scaled_line_grids) - 1:
            for _ in range(line_spacing):
                combined.append(gap_row[0][:])

    # ── Step 4: outline ───────────────────────────────────────────────────────
    if outline:
        combined = _apply_outline(combined, outline_thickness)

    # ── Step 5: background ────────────────────────────────────────────────────
    if background:
        combined = _apply_background(combined)

    # ── Step 6: padding ───────────────────────────────────────────────────────
    combined = _add_padding(combined, padding)

    return combined


def get_grid_dimensions(grid: Grid) -> tuple[int, int]:
    """Return (width, height) of the grid in blocks."""
    height = len(grid)
    width = len(grid[0]) if height else 0
    return width, height


def count_blocks(grid: Grid) -> dict[str, int]:
    """Return counts of text, outline, and background blocks."""
    counts = {1: 0, 2: 0, 3: 0}
    for row in grid:
        for cell in row:
            if cell in counts:
                counts[cell] += 1
    return {
        "text": counts[1],
        "outline": counts[2],
        "background": counts[3],
        "total": counts[1] + counts[2] + counts[3],
    }


def grid_to_ascii_preview(
    grid: Grid,
    max_width: int = 100,
    max_height: int = 40,
    text_char: str = "█",
    outline_char: str = "▓",
    background_char: str = "░",
    air_char: str = " ",
) -> str:
    """
    Convert the grid to a printable ASCII-art preview string.
    Downsamples if the grid exceeds max_width or max_height.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0:
        return "(empty grid)"

    # Determine sample step so the preview fits within the terminal bounds
    # Each cell takes ~1 character wide, but terminal chars are ~2× taller
    # than wide, so we sample rows more aggressively.
    col_step = max(1, (cols + max_width - 1) // max_width)
    row_step = max(1, (rows + max_height - 1) // max_height)

    char_map = {0: air_char, 1: text_char, 2: outline_char, 3: background_char}
    lines_out: list[str] = []
    for r in range(0, rows, row_step):
        row_chars = []
        for c in range(0, cols, col_step):
            row_chars.append(char_map.get(grid[r][c], air_char))
        lines_out.append("".join(row_chars))
    return "\n".join(lines_out)

"""
Litematic file writer.

Converts a 2-D block grid produced by renderer.py into a .litematic file
using the litemapy library.

Coordinate conventions
----------------------
Grid axes  →  Minecraft world axes:

  VERTICAL orientation  (text stands upright on a wall facing south)
    grid col  →  X  (east, +X)
    grid row  →  Y  (up, +Y)   — row 0 is the TOP of the text, so
                                  block_y = (height - 1) - row
    depth     →  Z  (south, +Z)  e.g. Z=0 is the front face

  HORIZONTAL orientation  (text lies flat on the floor, readable from above)
    grid col  →  X  (east, +X)
    grid row  →  Z  (south, +Z)  — row 0 is the northernmost row
    layer     →  Y  (up, +Y)     e.g. Y=0 is the bottom layer

The schematic origin is always (0, 0, 0) so Litematica will paste the
lower-left-front corner of the text at the anchor point you choose
in-game.
"""

from __future__ import annotations
import math
from pathlib import Path

from litemapy import Schematic, Region, BlockState

from .renderer import Grid, get_grid_dimensions, count_blocks

# Litematica stores air as "minecraft:air"; every unset position defaults to
# this, so we only need to call reg[x,y,z] = block for non-air cells.
_AIR = BlockState("minecraft:air")


def _bs(block_id: str) -> BlockState:
    """Wrap a block id string in a BlockState."""
    if not block_id.startswith("minecraft:"):
        block_id = f"minecraft:{block_id}"
    return BlockState(block_id)


def build_schematic(
    grid: Grid,
    orientation: str,         # "vertical" | "horizontal"
    text_block: str,
    outline_block: str | None,
    background_block: str | None,
    depth: int,               # wall depth (vertical) or layer height (horizontal)
    name: str = "Text Schematic",
    author: str = "litematic-text-generator",
    description: str = "",
) -> Schematic:
    """
    Build and return a litemapy Schematic from a rendered block grid.

    Parameters
    ----------
    grid             : 2-D grid (0=air, 1=text, 2=outline, 3=background).
    orientation      : "vertical" (wall) or "horizontal" (floor).
    text_block       : Minecraft block ID for value-1 cells.
    outline_block    : Minecraft block ID for value-2 cells (None = skip).
    background_block : Minecraft block ID for value-3 cells (None = skip).
    depth            : layers of depth for the extrusion axis.
    name             : schematic name embedded in metadata.
    author           : author string embedded in metadata.
    description      : description string embedded in metadata.
    """
    depth = max(1, depth)
    grid_width, grid_height = get_grid_dimensions(grid)

    # ── Build block lookup ────────────────────────────────────────────────────
    block_map: dict[int, BlockState | None] = {
        1: _bs(text_block),
        2: _bs(outline_block) if outline_block else None,
        3: _bs(background_block) if background_block else None,
    }

    # ── Determine region size ─────────────────────────────────────────────────
    if orientation == "vertical":
        # X = col direction, Y = row direction (inverted), Z = depth
        reg_x_size = grid_width
        reg_y_size = grid_height
        reg_z_size = depth
    else:  # horizontal
        # X = col direction, Z = row direction, Y = layer height
        reg_x_size = grid_width
        reg_y_size = depth
        reg_z_size = grid_height

    # litemapy Region(x, y, z, xsize, ysize, zsize)
    reg = Region(0, 0, 0, reg_x_size, reg_y_size, reg_z_size)

    # ── Place blocks ──────────────────────────────────────────────────────────
    for row_idx, row in enumerate(grid):
        for col_idx, cell_val in enumerate(row):
            block = block_map.get(cell_val)
            if block is None:
                continue  # air or ignored cell type

            if orientation == "vertical":
                bx = col_idx
                by = (grid_height - 1) - row_idx   # flip so row 0 = top
                for bz in range(depth):
                    reg[bx, by, bz] = block
            else:  # horizontal
                bx = col_idx
                bz = row_idx
                for by in range(depth):
                    reg[bx, by, bz] = block

    schem = reg.as_schematic(name=name, author=author, description=description)
    return schem


def save_schematic(
    grid: Grid,
    orientation: str,
    text_block: str,
    outline_block: str | None,
    background_block: str | None,
    depth: int,
    output_path: str | Path,
    name: str = "Text Schematic",
    author: str = "litematic-text-generator",
    description: str = "",
) -> Path:
    """
    Build and save a .litematic file.  Returns the resolved output path.
    Appends the .litematic extension if it is not already present.
    """
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".litematic":
        output_path = output_path.with_suffix(".litematic")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    schem = build_schematic(
        grid=grid,
        orientation=orientation,
        text_block=text_block,
        outline_block=outline_block,
        background_block=background_block,
        depth=depth,
        name=name,
        author=author,
        description=description,
    )
    schem.save(str(output_path))
    return output_path


# ── Dimension helpers (used by CLI for the summary table) ─────────────────────

def get_schematic_dimensions(
    grid: Grid,
    orientation: str,
    depth: int,
) -> dict[str, int]:
    """
    Return a dict with x, y, z, and volume in blocks, plus chunk footprint.
    """
    grid_width, grid_height = get_grid_dimensions(grid)
    depth = max(1, depth)

    if orientation == "vertical":
        sx, sy, sz = grid_width, grid_height, depth
    else:
        sx, sy, sz = grid_width, depth, grid_height

    return {
        "x": sx,
        "y": sy,
        "z": sz,
        "volume": sx * sy * sz,
        "chunks_x": math.ceil(sx / 16),
        "chunks_y": math.ceil(sy / 16),
        "chunks_z": math.ceil(sz / 16),
    }

#!/usr/bin/env python3
"""
convert_to_schematic.py
=======================
Converts a Litematica .litematic file to the classic Schematica .schematic
NBT format — the format Baritone reads with its #schematic / #build command.

Usage (interactive):
    python3 convert_to_schematic.py

Usage (command-line):
    python3 convert_to_schematic.py input.litematic [output.schematic]

File format notes
-----------------
The classic .schematic format stores blocks as two parallel byte arrays
("Blocks" and "Data") indexed in Y-Z-X order:
    index = Y * Width * Length  +  Z * Width  +  X

Block IDs are 1.12.2-era numeric IDs.  Blocks introduced in 1.13+
(deepslate, blackstone, shroomlight, basalt, etc.) have no 1.12 equivalent
and are substituted with Stone (ID 1).  A warning listing all substitutions
is printed after conversion.

The output file is gzip-compressed NBT, identical in structure to schematics
produced by the Schematica mod and recognised by Baritone's #build command.
"""

from __future__ import annotations
import argparse
import gzip
import io
import sys
from pathlib import Path

import numpy as np
import nbtlib
from litemapy import Schematic

# ── Minecraft 1.12.2 numeric block-ID mapping ─────────────────────────────────
# (block_string_id) -> (numeric_id, data_value)
# Only the subset relevant to this generator's block catalogue plus common extras.

BLOCK_ID_MAP: dict[str, tuple[int, int]] = {
    # ── Air ──────────────────────────────────────────────────────────────────
    "minecraft:air":                       (0,   0),
    "minecraft:cave_air":                  (0,   0),
    "minecraft:void_air":                  (0,   0),

    # ── Stone & variants ─────────────────────────────────────────────────────
    "minecraft:stone":                     (1,   0),
    "minecraft:granite":                   (1,   1),
    "minecraft:polished_granite":          (1,   2),
    "minecraft:diorite":                   (1,   3),
    "minecraft:polished_diorite":          (1,   4),
    "minecraft:andesite":                  (1,   5),
    "minecraft:polished_andesite":         (1,   6),
    "minecraft:smooth_stone":              (43,  8),   # double stone slab = smooth stone in 1.12

    # ── Dirt / ground ────────────────────────────────────────────────────────
    "minecraft:grass_block":               (2,   0),
    "minecraft:dirt":                      (3,   0),
    "minecraft:coarse_dirt":               (3,   1),
    "minecraft:podzol":                    (3,   2),
    "minecraft:cobblestone":               (4,   0),
    "minecraft:mossy_cobblestone":         (48,  0),
    "minecraft:gravel":                    (13,  0),
    "minecraft:sand":                      (12,  0),
    "minecraft:red_sand":                  (12,  1),

    # ── Wood planks ──────────────────────────────────────────────────────────
    "minecraft:oak_planks":                (5,   0),
    "minecraft:spruce_planks":             (5,   1),
    "minecraft:birch_planks":              (5,   2),
    "minecraft:jungle_planks":             (5,   3),
    "minecraft:acacia_planks":             (5,   4),
    "minecraft:dark_oak_planks":           (5,   5),

    # ── Sponge / glass ───────────────────────────────────────────────────────
    "minecraft:sponge":                    (19,  0),
    "minecraft:wet_sponge":                (19,  1),
    "minecraft:glass":                     (20,  0),

    # ── Ores / minerals ──────────────────────────────────────────────────────
    "minecraft:gold_block":                (41,  0),
    "minecraft:iron_block":                (42,  0),
    "minecraft:diamond_block":             (57,  0),
    "minecraft:lapis_block":               (22,  0),
    "minecraft:emerald_block":             (133, 0),
    "minecraft:redstone_block":            (152, 0),
    "minecraft:coal_block":                (173, 0),

    # ── Obsidian / nether ────────────────────────────────────────────────────
    "minecraft:obsidian":                  (49,  0),
    "minecraft:netherrack":                (87,  0),
    "minecraft:soul_sand":                 (88,  0),
    "minecraft:nether_bricks":             (112, 0),
    "minecraft:red_nether_bricks":         (215, 0),
    "minecraft:glowstone":                 (89,  0),
    "minecraft:magma_block":               (213, 0),
    "minecraft:bone_block":                (216, 0),

    # ── End ──────────────────────────────────────────────────────────────────
    "minecraft:end_stone":                 (121, 0),
    "minecraft:end_stone_bricks":          (206, 0),
    "minecraft:purpur_block":              (201, 0),
    "minecraft:purpur_pillar":             (202, 0),

    # ── Sea lantern / prismarine ──────────────────────────────────────────────
    "minecraft:sea_lantern":               (169, 0),
    "minecraft:prismarine":                (168, 0),
    "minecraft:prismarine_bricks":         (168, 1),
    "minecraft:dark_prismarine":           (168, 2),

    # ── Stone bricks ─────────────────────────────────────────────────────────
    "minecraft:stone_bricks":              (98,  0),
    "minecraft:mossy_stone_bricks":        (98,  1),
    "minecraft:cracked_stone_bricks":      (98,  2),
    "minecraft:chiseled_stone_bricks":     (98,  3),

    # ── Sandstone ────────────────────────────────────────────────────────────
    "minecraft:sandstone":                 (24,  0),
    "minecraft:chiseled_sandstone":        (24,  1),
    "minecraft:smooth_sandstone":          (24,  2),
    "minecraft:red_sandstone":             (179, 0),
    "minecraft:smooth_red_sandstone":      (179, 2),

    # ── Quartz ───────────────────────────────────────────────────────────────
    "minecraft:quartz_block":              (155, 0),
    "minecraft:chiseled_quartz_block":     (155, 1),
    "minecraft:quartz_pillar":             (155, 2),

    # ── Wool (all 16 colours) ────────────────────────────────────────────────
    "minecraft:white_wool":                (35,  0),
    "minecraft:orange_wool":               (35,  1),
    "minecraft:magenta_wool":              (35,  2),
    "minecraft:light_blue_wool":           (35,  3),
    "minecraft:yellow_wool":               (35,  4),
    "minecraft:lime_wool":                 (35,  5),
    "minecraft:pink_wool":                 (35,  6),
    "minecraft:gray_wool":                 (35,  7),
    "minecraft:light_gray_wool":           (35,  8),
    "minecraft:cyan_wool":                 (35,  9),
    "minecraft:purple_wool":               (35, 10),
    "minecraft:blue_wool":                 (35, 11),
    "minecraft:brown_wool":                (35, 12),
    "minecraft:green_wool":                (35, 13),
    "minecraft:red_wool":                  (35, 14),
    "minecraft:black_wool":                (35, 15),

    # ── Terracotta (uncoloured) ───────────────────────────────────────────────
    "minecraft:terracotta":                (172, 0),

    # ── Stained terracotta (all 16 colours) ──────────────────────────────────
    "minecraft:white_terracotta":          (159, 0),
    "minecraft:orange_terracotta":         (159, 1),
    "minecraft:magenta_terracotta":        (159, 2),
    "minecraft:light_blue_terracotta":     (159, 3),
    "minecraft:yellow_terracotta":         (159, 4),
    "minecraft:lime_terracotta":           (159, 5),
    "minecraft:pink_terracotta":           (159, 6),
    "minecraft:gray_terracotta":           (159, 7),
    "minecraft:light_gray_terracotta":     (159, 8),
    "minecraft:cyan_terracotta":           (159, 9),
    "minecraft:purple_terracotta":         (159, 10),
    "minecraft:blue_terracotta":           (159, 11),
    "minecraft:brown_terracotta":          (159, 12),
    "minecraft:green_terracotta":          (159, 13),
    "minecraft:red_terracotta":            (159, 14),
    "minecraft:black_terracotta":          (159, 15),

    # ── Concrete (all 16 colours) ────────────────────────────────────────────
    "minecraft:white_concrete":            (251, 0),
    "minecraft:orange_concrete":           (251, 1),
    "minecraft:magenta_concrete":          (251, 2),
    "minecraft:light_blue_concrete":       (251, 3),
    "minecraft:yellow_concrete":           (251, 4),
    "minecraft:lime_concrete":             (251, 5),
    "minecraft:pink_concrete":             (251, 6),
    "minecraft:gray_concrete":             (251, 7),
    "minecraft:light_gray_concrete":       (251, 8),
    "minecraft:cyan_concrete":             (251, 9),
    "minecraft:purple_concrete":           (251, 10),
    "minecraft:blue_concrete":             (251, 11),
    "minecraft:brown_concrete":            (251, 12),
    "minecraft:green_concrete":            (251, 13),
    "minecraft:red_concrete":              (251, 14),
    "minecraft:black_concrete":            (251, 15),

    # ── Concrete powder (all 16 colours) ─────────────────────────────────────
    "minecraft:white_concrete_powder":     (252, 0),
    "minecraft:orange_concrete_powder":    (252, 1),
    "minecraft:magenta_concrete_powder":   (252, 2),
    "minecraft:light_blue_concrete_powder":(252, 3),
    "minecraft:yellow_concrete_powder":    (252, 4),
    "minecraft:lime_concrete_powder":      (252, 5),
    "minecraft:pink_concrete_powder":      (252, 6),
    "minecraft:gray_concrete_powder":      (252, 7),
    "minecraft:light_gray_concrete_powder":(252, 8),
    "minecraft:cyan_concrete_powder":      (252, 9),
    "minecraft:purple_concrete_powder":    (252, 10),
    "minecraft:blue_concrete_powder":      (252, 11),
    "minecraft:brown_concrete_powder":     (252, 12),
    "minecraft:green_concrete_powder":     (252, 13),
    "minecraft:red_concrete_powder":       (252, 14),
    "minecraft:black_concrete_powder":     (252, 15),

    # ── Misc 1.12-era blocks ─────────────────────────────────────────────────
    "minecraft:hay_block":                 (170, 0),
    "minecraft:bricks":                    (45,  0),
    "minecraft:brick_slab":                (44,  4),
    "minecraft:jack_o_lantern":            (91,  0),
    "minecraft:pumpkin":                   (86,  0),
    "minecraft:ice":                       (79,  0),
    "minecraft:packed_ice":                (174, 0),

    # ── 1.13+ blocks with reasonable 1.12 approximations ──────────────────────
    # These exist in 1.20 worlds but have no direct 1.12 numeric ID.
    # We map them to their nearest visual/functional equivalent.
    "minecraft:smooth_basalt":             (1,   0),   # → stone
    "minecraft:tuff":                      (1,   5),   # → andesite (similar look)
    "minecraft:calcite":                   (1,   3),   # → diorite (similar look)
    "minecraft:amethyst_block":            (133, 0),   # → emerald block (closest purple)
    "minecraft:raw_iron_block":            (42,  0),   # → iron block
    "minecraft:raw_gold_block":            (41,  0),   # → gold block
    "minecraft:raw_copper_block":          (41,  0),   # → gold block (no copper in 1.12)
    "minecraft:copper_block":              (41,  0),   # → gold block
    "minecraft:cut_copper":                (41,  0),   # → gold block
    "minecraft:waxed_copper_block":        (41,  0),   # → gold block
    "minecraft:mud":                       (3,   0),   # → dirt
    "minecraft:packed_mud":                (45,  0),   # → bricks
    "minecraft:mud_bricks":                (45,  0),   # → bricks
    "minecraft:reinforced_deepslate":      (49,  0),   # → obsidian (closest hard block)
}

# Blocks NOT in BLOCK_ID_MAP get this fallback + a warning printed at the end.
FALLBACK_ID: tuple[int, int] = (1, 0)   # Stone

# ── No-1.12-equivalent blocks (printed as a note, not an error) ───────────────
_1_13_PLUS_KNOWN_UNSUPPORTED = {
    "minecraft:deepslate",
    "minecraft:cobbled_deepslate",
    "minecraft:polished_deepslate",
    "minecraft:deepslate_bricks",
    "minecraft:deepslate_tiles",
    "minecraft:chiseled_deepslate",
    "minecraft:cracked_deepslate_bricks",
    "minecraft:cracked_deepslate_tiles",
    "minecraft:blackstone",
    "minecraft:polished_blackstone",
    "minecraft:polished_blackstone_bricks",
    "minecraft:chiseled_polished_blackstone",
    "minecraft:gilded_blackstone",
    "minecraft:basalt",
    "minecraft:polished_basalt",
    "minecraft:shroomlight",
    "minecraft:crimson_nylium",
    "minecraft:warped_nylium",
    "minecraft:crimson_planks",
    "minecraft:warped_planks",
    "minecraft:soul_soil",
    "minecraft:netherite_block",
    "minecraft:crying_obsidian",
    "minecraft:respawn_anchor",
    "minecraft:lodestone",
    "minecraft:ancient_debris",
    "minecraft:nether_gold_ore",
}


def _resolve_block(block_id: str) -> tuple[int, int]:
    """
    Return (numeric_id, data) for the given block_id string.
    Returns FALLBACK_ID for unknown blocks.
    """
    return BLOCK_ID_MAP.get(block_id, FALLBACK_ID)


def _to_signed_byte(val: int) -> int:
    """
    Convert an unsigned block-ID byte (0–255) to its signed int8 equivalent
    so it can be stored in a numpy int8 array without overflow errors.
    NumPy ≥ 2.0 raises OverflowError on out-of-range int8 assignments.
    """
    val = val & 0xFF
    return val if val < 128 else val - 256


# ── Core conversion ───────────────────────────────────────────────────────────

def litematic_to_schematic(
    input_path: str | Path,
    output_path: str | Path,
    region_name: str | None = None,
) -> dict:
    """
    Convert a .litematic file to a classic .schematic file.

    Parameters
    ----------
    input_path   : path to the source .litematic file.
    output_path  : path to write the .schematic file (created/overwritten).
    region_name  : which region to convert.  If None, the first region is used.
                   If the litematic has multiple regions they are merged into one.

    Returns
    -------
    dict with conversion statistics:
        total_blocks, substitutions (dict of unknown_id → count), width, height, length
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".schematic":
        output_path = output_path.with_suffix(".schematic")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Load litematic ────────────────────────────────────────────────────────
    schem = Schematic.load(str(input_path))

    if region_name and region_name in schem.regions:
        regions_to_use = {region_name: schem.regions[region_name]}
    else:
        regions_to_use = schem.regions

    # ── Compute total bounding box across all regions ─────────────────────────
    all_positions: list[tuple[int, int, int, str]] = []   # (x, y, z, block_id)

    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')

    for reg in regions_to_use.values():
        for x, y, z in reg.block_positions():
            bid = reg[x, y, z].id
            if bid == "minecraft:air":
                continue
            all_positions.append((x, y, z, bid))
            if x < min_x: min_x = x
            if y < min_y: min_y = y
            if z < min_z: min_z = z
            if x > max_x: max_x = x
            if y > max_y: max_y = y
            if z > max_z: max_z = z

    if not all_positions:
        # Schematic has no non-air blocks — write a 1×1×1 air schematic
        min_x = min_y = min_z = 0
        max_x = max_y = max_z = 0

    min_x, min_y, min_z = int(min_x), int(min_y), int(min_z)
    max_x, max_y, max_z = int(max_x), int(max_y), int(max_z)

    width  = max_x - min_x + 1   # X
    height = max_y - min_y + 1   # Y
    length = max_z - min_z + 1   # Z

    total = width * height * length
    blocks_arr = np.zeros(total, dtype=np.int8)
    data_arr   = np.zeros(total, dtype=np.int8)

    substitutions: dict[str, int] = {}
    placed = 0

    for x, y, z, bid in all_positions:
        # Normalise to 0-based
        bx = x - min_x
        by = y - min_y
        bz = z - min_z
        idx = by * width * length + bz * width + bx

        numeric_id, data_val = _resolve_block(bid)

        if bid not in BLOCK_ID_MAP:
            substitutions[bid] = substitutions.get(bid, 0) + 1

        blocks_arr[idx] = _to_signed_byte(numeric_id)
        data_arr[idx]   = _to_signed_byte(data_val)
        placed += 1

    # ── Build NBT file ────────────────────────────────────────────────────────
    # .schematic: gzip-compressed, big-endian, root tag is an unnamed Compound.
    nbt_file = nbtlib.File(
        {
            "Width":        nbtlib.Short(width),
            "Height":       nbtlib.Short(height),
            "Length":       nbtlib.Short(length),
            "Materials":    nbtlib.String("Alpha"),
            "Blocks":       nbtlib.ByteArray(blocks_arr),
            "Data":         nbtlib.ByteArray(data_arr),
            "TileEntities": nbtlib.List[nbtlib.Compound](),
            "Entities":     nbtlib.List[nbtlib.Compound](),
        },
        gzipped=True,
        byteorder="big",
        root_name="",
    )
    nbt_file.save(str(output_path), gzipped=True)

    return {
        "total_blocks": placed,
        "substitutions": substitutions,
        "width": width,
        "height": height,
        "length": length,
        "output_path": output_path,
    }


# ── Pretty-print helper ───────────────────────────────────────────────────────

def _print_result(stats: dict) -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich import box

        console = Console()
        console.print()
        console.print(
            Panel(
                f"[bold green]✔  Conversion complete![/bold green]\n\n"
                f"[bold]Output:[/bold]     {stats['output_path']}\n"
                f"[bold]Size:[/bold]       {stats['output_path'].stat().st_size / 1024:.1f} KB\n"
                f"[bold]Dimensions:[/bold] {stats['width']} × {stats['height']} × {stats['length']} blocks  "
                f"(X × Y × Z)\n"
                f"[bold]Blocks placed:[/bold] {stats['total_blocks']:,}",
                title="[bold green].schematic Export[/bold green]",
                box=box.ROUNDED,
                border_style="green",
            )
        )

        if stats["substitutions"]:
            console.print()
            t = Table(
                title="⚠  Block Substitutions  (no 1.12 numeric ID → Stone used)",
                box=box.SIMPLE_HEAD,
                title_style="bold yellow",
                header_style="bold",
            )
            t.add_column("Block ID (1.13+)", style="dim")
            t.add_column("Count", justify="right")
            t.add_column("Substituted with")
            for bid, cnt in sorted(stats["substitutions"].items(), key=lambda x: -x[1]):
                t.add_row(bid, str(cnt), "minecraft:stone  (ID 1)")
            console.print(t)
            console.print(
                "[dim]Tip: for Baritone builds on 2b2t, use blocks with 1.12 IDs\n"
                "(netherrack, cobblestone, concrete, wool, obsidian, etc.).[/dim]"
            )

        console.print()
        console.print(
            "[dim]To use with Baritone:  [bold]#build[/bold] (or [bold]#schematic[/bold]) "
            f"[bold]{stats['output_path'].name}[/bold][/dim]"
        )
        console.print()

    except ImportError:
        # Fallback if rich is not available
        print(f"\n✔ Saved: {stats['output_path']}")
        print(f"  Dimensions: {stats['width']}x{stats['height']}x{stats['length']}")
        print(f"  Blocks: {stats['total_blocks']:,}")
        if stats["substitutions"]:
            print("  ⚠ Substitutions (→ stone):")
            for bid, cnt in sorted(stats["substitutions"].items(), key=lambda x: -x[1]):
                print(f"    {bid}: {cnt}")


# ── Interactive / CLI entry point ─────────────────────────────────────────────

def _interactive() -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich import box
        import questionary
        from questionary import Style

        Q_STYLE = Style([
            ("qmark",       "fg:#00e5ff bold"),
            ("question",    "fg:#ffffff bold"),
            ("answer",      "fg:#00e5ff bold"),
            ("pointer",     "fg:#00e5ff bold"),
            ("highlighted", "fg:#00e5ff bold"),
            ("selected",    "fg:#5fff87"),
        ])

        console = Console()
        console.print(
            Panel(
                "[bold cyan].litematic → .schematic Converter[/bold cyan]\n"
                "[dim]Produces a Baritone-compatible classic Schematica file.[/dim]",
                box=box.ROUNDED,
                border_style="cyan",
            )
        )

        src = questionary.path(
            "Source .litematic file:",
            style=Q_STYLE,
            validate=lambda p: (
                True if Path(p).is_file() and p.endswith(".litematic")
                else "Please select a valid .litematic file."
            ),
        ).ask()
        if src is None:
            sys.exit(0)

        default_out = str(Path(src).with_suffix(".schematic"))
        dst = questionary.text(
            "Output .schematic path:",
            default=default_out,
            style=Q_STYLE,
        ).ask()
        if dst is None:
            sys.exit(0)

        console.print("[bold cyan]Converting…[/bold cyan]")
        stats = litematic_to_schematic(src, dst)
        _print_result(stats)

    except ImportError:
        # Bare-bones fallback
        src = input("Source .litematic file: ").strip()
        dst = input(f"Output .schematic [{Path(src).with_suffix('.schematic')}]: ").strip()
        if not dst:
            dst = str(Path(src).with_suffix(".schematic"))
        print("Converting…")
        stats = litematic_to_schematic(src, dst)
        _print_result(stats)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="convert_to_schematic",
        description=(
            "Convert a Litematica .litematic file to a classic .schematic file "
            "(Baritone-compatible, Schematica NBT format)."
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        help=".litematic input file path (omit for interactive mode).",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help=".schematic output file path (defaults to same name as input).",
    )
    args = parser.parse_args()

    if args.input is None:
        _interactive()
        return

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_suffix(".schematic")

    print(f"Converting {input_path} → {output_path} …")
    stats = litematic_to_schematic(input_path, output_path)
    _print_result(stats)


if __name__ == "__main__":
    main()

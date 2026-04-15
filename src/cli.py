"""
Interactive CLI for the Litematic Text Schematic Generator.

Uses `questionary` for prompts and `rich` for formatted output.
Optimised for a 2b2t Java-Edition player on macOS (M4) using Litematica
with the Icebox Printer addon.
"""

from __future__ import annotations
import sys
import textwrap
from pathlib import Path

import questionary
from questionary import Choice, Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .font import get_unsupported_chars
from .renderer import render_text, get_grid_dimensions, count_blocks, grid_to_ascii_preview
from .schematic import save_schematic, get_schematic_dimensions

console = Console()

# ── Custom questionary style ──────────────────────────────────────────────────
Q_STYLE = Style([
    ("qmark",        "fg:#00e5ff bold"),
    ("question",     "fg:#ffffff bold"),
    ("answer",       "fg:#00e5ff bold"),
    ("pointer",      "fg:#00e5ff bold"),
    ("highlighted",  "fg:#00e5ff bold"),
    ("selected",     "fg:#5fff87"),
    ("separator",    "fg:#444444"),
    ("instruction",  "fg:#888888 italic"),
])


# ── Block catalogue ───────────────────────────────────────────────────────────
# Format: (display label, minecraft block id)
# Groups are separated by a "──" separator entry (None value).
BLOCK_CATALOGUE: list[tuple[str, str | None]] = [
    # 2b2t abundantly-available materials
    ("── 2b2t Common ─────────────────────────────", None),
    ("Netherrack",                                  "minecraft:netherrack"),
    ("Cobblestone",                                 "minecraft:cobblestone"),
    ("Sand",                                        "minecraft:sand"),
    ("Gravel",                                      "minecraft:gravel"),
    ("Stone",                                       "minecraft:stone"),
    ("Dirt",                                        "minecraft:dirt"),
    ("Obsidian",                                    "minecraft:obsidian"),
    ("End Stone",                                   "minecraft:end_stone"),
    ("Nether Bricks",                               "minecraft:nether_bricks"),

    # Stone variants
    ("── Stone Variants ──────────────────────────", None),
    ("Andesite",                                    "minecraft:andesite"),
    ("Diorite",                                     "minecraft:diorite"),
    ("Granite",                                     "minecraft:granite"),
    ("Smooth Stone",                                "minecraft:smooth_stone"),
    ("Blackstone",                                  "minecraft:blackstone"),
    ("Deepslate",                                   "minecraft:deepslate"),
    ("Cobbled Deepslate",                           "minecraft:cobbled_deepslate"),
    ("Polished Deepslate",                          "minecraft:polished_deepslate"),
    ("Basalt",                                      "minecraft:basalt"),

    # Concrete (all 16 colours)
    ("── Concrete ────────────────────────────────", None),
    ("White Concrete",                              "minecraft:white_concrete"),
    ("Light Gray Concrete",                         "minecraft:light_gray_concrete"),
    ("Gray Concrete",                               "minecraft:gray_concrete"),
    ("Black Concrete",                              "minecraft:black_concrete"),
    ("Red Concrete",                                "minecraft:red_concrete"),
    ("Orange Concrete",                             "minecraft:orange_concrete"),
    ("Yellow Concrete",                             "minecraft:yellow_concrete"),
    ("Lime Concrete",                               "minecraft:lime_concrete"),
    ("Green Concrete",                              "minecraft:green_concrete"),
    ("Cyan Concrete",                               "minecraft:cyan_concrete"),
    ("Light Blue Concrete",                         "minecraft:light_blue_concrete"),
    ("Blue Concrete",                               "minecraft:blue_concrete"),
    ("Purple Concrete",                             "minecraft:purple_concrete"),
    ("Magenta Concrete",                            "minecraft:magenta_concrete"),
    ("Pink Concrete",                               "minecraft:pink_concrete"),
    ("Brown Concrete",                              "minecraft:brown_concrete"),

    # Wool (all 16 colours)
    ("── Wool ────────────────────────────────────", None),
    ("White Wool",                                  "minecraft:white_wool"),
    ("Light Gray Wool",                             "minecraft:light_gray_wool"),
    ("Gray Wool",                                   "minecraft:gray_wool"),
    ("Black Wool",                                  "minecraft:black_wool"),
    ("Red Wool",                                    "minecraft:red_wool"),
    ("Orange Wool",                                 "minecraft:orange_wool"),
    ("Yellow Wool",                                 "minecraft:yellow_wool"),
    ("Lime Wool",                                   "minecraft:lime_wool"),
    ("Green Wool",                                  "minecraft:green_wool"),
    ("Cyan Wool",                                   "minecraft:cyan_wool"),
    ("Light Blue Wool",                             "minecraft:light_blue_wool"),
    ("Blue Wool",                                   "minecraft:blue_wool"),
    ("Purple Wool",                                 "minecraft:purple_wool"),
    ("Magenta Wool",                                "minecraft:magenta_wool"),
    ("Pink Wool",                                   "minecraft:pink_wool"),
    ("Brown Wool",                                  "minecraft:brown_wool"),

    # Terracotta
    ("── Terracotta ──────────────────────────────", None),
    ("Terracotta (uncoloured)",                     "minecraft:terracotta"),
    ("White Terracotta",                            "minecraft:white_terracotta"),
    ("Orange Terracotta",                           "minecraft:orange_terracotta"),
    ("Yellow Terracotta",                           "minecraft:yellow_terracotta"),
    ("Red Terracotta",                              "minecraft:red_terracotta"),
    ("Brown Terracotta",                            "minecraft:brown_terracotta"),

    # Light-emitting blocks
    ("── Emissive / Glowing ──────────────────────", None),
    ("Glowstone",                                   "minecraft:glowstone"),
    ("Sea Lantern",                                 "minecraft:sea_lantern"),
    ("Shroomlight",                                 "minecraft:shroomlight"),
    ("Magma Block",                                 "minecraft:magma_block"),
    ("Jack o'Lantern",                              "minecraft:jack_o_lantern"),
    ("Lantern",                                     "minecraft:lantern"),

    # Wood/natural
    ("── Wood / Natural ──────────────────────────", None),
    ("Oak Planks",                                  "minecraft:oak_planks"),
    ("Dark Oak Planks",                             "minecraft:dark_oak_planks"),
    ("Spruce Planks",                               "minecraft:spruce_planks"),
    ("Jungle Planks",                               "minecraft:jungle_planks"),
    ("Mossy Cobblestone",                           "minecraft:mossy_cobblestone"),
    ("Sponge",                                      "minecraft:sponge"),

    # Custom entry
    ("── Other ───────────────────────────────────", None),
    ("Enter a custom block ID…",                    "__custom__"),
]

_SEPARATOR_LABEL = "────────────────────────────────────────────"

def _build_choices(catalogue: list[tuple[str, str | None]]) -> list[Choice]:
    choices = []
    for label, block_id in catalogue:
        if block_id is None:
            choices.append(Choice(title=label, value=None, disabled=""))
        else:
            choices.append(Choice(title=label, value=block_id))
    return choices


def _ask_block(prompt: str) -> str:
    """Interactive block selector; handles custom entry."""
    choices = _build_choices(BLOCK_CATALOGUE)
    selected = questionary.select(
        prompt,
        choices=choices,
        style=Q_STYLE,
        use_shortcuts=False,
        use_indicator=True,
    ).ask()

    if selected is None:
        console.print("[red]Selection cancelled. Exiting.[/red]")
        sys.exit(0)

    if selected == "__custom__":
        custom = questionary.text(
            "Enter the full block ID (e.g. minecraft:cobblestone):",
            style=Q_STYLE,
            validate=lambda v: (
                True if v.strip() else "Block ID cannot be empty."
            ),
        ).ask()
        if custom is None:
            console.print("[red]Cancelled.[/red]")
            sys.exit(0)
        return custom.strip()

    return selected


def _ask_int(prompt: str, default: int, min_val: int, max_val: int) -> int:
    """Ask for an integer within a range."""
    raw = questionary.text(
        f"{prompt} [{min_val}–{max_val}, default {default}]:",
        default=str(default),
        style=Q_STYLE,
        validate=lambda v: (
            True
            if (v.strip().lstrip("-").isdigit() and min_val <= int(v) <= max_val)
            else f"Please enter a number between {min_val} and {max_val}."
        ),
    ).ask()
    if raw is None:
        console.print("[red]Cancelled.[/red]")
        sys.exit(0)
    return int(raw.strip())


def _ask_confirm(prompt: str, default: bool = True) -> bool:
    ans = questionary.confirm(prompt, default=default, style=Q_STYLE).ask()
    if ans is None:
        console.print("[red]Cancelled.[/red]")
        sys.exit(0)
    return ans


# ── Banner ────────────────────────────────────────────────────────────────────

_BANNER = r"""
 ██╗     ██╗████████╗███████╗███╗   ███╗ █████╗ ████████╗██╗ ██████╗
 ██║     ██║╚══██╔══╝██╔════╝████╗ ████║██╔══██╗╚══██╔══╝██║██╔════╝
 ██║     ██║   ██║   █████╗  ██╔████╔██║███████║   ██║   ██║██║
 ██║     ██║   ██║   ██╔══╝  ██║╚██╔╝██║██╔══██║   ██║   ██║██║
 ███████╗██║   ██║   ███████╗██║ ╚═╝ ██║██║  ██║   ██║   ██║╚██████╗
 ╚══════╝╚═╝   ╚═╝   ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝
          TEXT → SCHEMATIC GENERATOR  •  2b2t ready  •  .litematic
"""


def _print_banner() -> None:
    console.print(Text(_BANNER, style="bold cyan"))
    console.print(
        Panel(
            "[dim]Generates pixel-font text schematics for the Litematica mod.\n"
            "Optimised for [bold]2b2t[/bold] (Java 1.20.x) · Litematica Icebox Printer compatible.[/dim]",
            box=box.ROUNDED,
            border_style="bright_black",
            padding=(0, 2),
        )
    )
    console.print()


# ── Main CLI flow ─────────────────────────────────────────────────────────────

def run_cli() -> None:
    _print_banner()

    # ── 1. Text input ─────────────────────────────────────────────────────────
    console.rule("[bold cyan]Step 1 · Text Content[/bold cyan]")
    console.print(
        "[dim]Type your text. Use [bold]\\n[/bold] to manually insert a line break "
        "(e.g.  [bold]HELLO\\nWORLD[/bold]).[/dim]\n"
    )
    raw_text: str | None = questionary.text(
        "Text to render:",
        style=Q_STYLE,
        validate=lambda v: True if v.strip() else "Text cannot be empty.",
    ).ask()
    if raw_text is None:
        sys.exit(0)
    raw_text = raw_text.strip()

    # Replace literal "\n" typed by user
    raw_text = raw_text.replace("\\n", "\n")

    # ── 2. Case handling ──────────────────────────────────────────────────────
    console.print()
    case_choice = questionary.select(
        "Letter case handling:",
        choices=[
            Choice("Preserve as typed",  value="preserve"),
            Choice("ALL UPPERCASE",       value="upper"),
            Choice("all lowercase",       value="lower"),
        ],
        style=Q_STYLE,
    ).ask()
    if case_choice is None:
        sys.exit(0)
    if case_choice == "upper":
        raw_text = raw_text.upper()
    elif case_choice == "lower":
        raw_text = raw_text.lower()

    # ── 3. Unsupported character warning ──────────────────────────────────────
    unsupported = get_unsupported_chars(raw_text)
    if unsupported:
        console.print(
            f"\n[yellow]⚠ The following characters have no font definition and will "
            f"be rendered as '?': [bold]{' '.join(unsupported)}[/bold][/yellow]"
        )

    # ── 4. Line splitting ─────────────────────────────────────────────────────
    natural_lines = raw_text.split("\n")
    console.print(
        f"\n[dim]Your text currently has [bold]{len(natural_lines)}[/bold] line(s) "
        f"based on the line breaks you entered.[/dim]"
    )

    split_mode = questionary.select(
        "How should the text be split into lines?",
        choices=[
            Choice(
                f"Keep {len(natural_lines)} line(s) as entered",
                value="natural",
            ),
            Choice(
                "Auto-split into N even lines (by word boundary)",
                value="auto",
            ),
            Choice(
                "Each word on its own line",
                value="words",
            ),
        ],
        style=Q_STYLE,
    ).ask()
    if split_mode is None:
        sys.exit(0)

    if split_mode == "natural":
        lines = natural_lines
    elif split_mode == "words":
        # Flatten then re-split by whitespace
        all_words = raw_text.replace("\n", " ").split()
        lines = all_words if all_words else [""]
    else:  # auto
        all_text_flat = raw_text.replace("\n", " ")
        n_lines = _ask_int("How many lines?", default=2, min_val=1, max_val=20)
        # Even-ish word distribution
        words = all_text_flat.split()
        if not words:
            lines = [""] * n_lines
        else:
            per_line = max(1, len(words) // n_lines)
            lines = []
            for i in range(n_lines):
                chunk = words[i * per_line: (i + 1) * per_line]
                if i == n_lines - 1:
                    chunk = words[i * per_line:]
                lines.append(" ".join(chunk))

    # Trim empty lines and show confirmation
    lines = [ln.rstrip() for ln in lines if ln.strip()]
    if not lines:
        lines = [raw_text]

    console.print()
    console.print("[bold]Lines preview:[/bold]")
    for i, ln in enumerate(lines, 1):
        console.print(f"  [cyan]{i}.[/cyan] {ln!r}")

    if not _ask_confirm("Proceed with these lines?", default=True):
        console.print("[yellow]Re-run the script to start over.[/yellow]")
        sys.exit(0)

    # ── 5. Orientation ────────────────────────────────────────────────────────
    console.print()
    console.rule("[bold cyan]Step 2 · Layout & Orientation[/bold cyan]")
    orientation = questionary.select(
        "Schematic orientation:",
        choices=[
            Choice(
                "VERTICAL  — text stands upright on a wall (faces south, readable head-on)",
                value="vertical",
            ),
            Choice(
                "HORIZONTAL — text lies flat on the ground (readable from above / flying)",
                value="horizontal",
            ),
        ],
        style=Q_STYLE,
    ).ask()
    if orientation is None:
        sys.exit(0)

    # ── 6. Font scale ─────────────────────────────────────────────────────────
    console.print()
    scale_choice = questionary.select(
        "Font scale  (1 pixel of the 5×7 bitmap = N blocks):",
        choices=[
            Choice("1 — Tiny    (5×7 blocks per char)",    value=1),
            Choice("2 — Small   (10×14 blocks per char)",  value=2),
            Choice("3 — Medium  (15×21 blocks per char)",  value=3),
            Choice("4 — Large   (20×28 blocks per char)",  value=4),
            Choice("5 — Huge    (25×35 blocks per char)",  value=5),
            Choice("6 — Massive (30×42 blocks per char)",  value=6),
            Choice("Custom…",                              value=0),
        ],
        style=Q_STYLE,
    ).ask()
    if scale_choice is None:
        sys.exit(0)
    if scale_choice == 0:
        scale = _ask_int("Enter custom scale factor", default=3, min_val=1, max_val=32)
    else:
        scale = scale_choice

    # ── 7. Character spacing ─────────────────────────────────────────────────
    console.print()
    char_spacing = _ask_int(
        "Character spacing (pixels between letters, pre-scale)",
        default=1, min_val=0, max_val=10,
    )

    # ── 8. Line spacing ───────────────────────────────────────────────────────
    line_spacing = _ask_int(
        "Line spacing (blocks between lines, post-scale)",
        default=2, min_val=0, max_val=20,
    )

    # ── 9. Depth ──────────────────────────────────────────────────────────────
    if orientation == "vertical":
        depth_label = "Wall depth (Z thickness in blocks, 1 = single-block-thick wall)"
    else:
        depth_label = "Layer height (Y thickness in blocks, 1 = flat on ground)"
    depth = _ask_int(depth_label, default=1, min_val=1, max_val=10)

    # ── 10. Padding ───────────────────────────────────────────────────────────
    padding = _ask_int(
        "Padding/margin around text (air blocks on all sides)",
        default=1, min_val=0, max_val=10,
    )

    # ── 11. Text block ────────────────────────────────────────────────────────
    console.print()
    console.rule("[bold cyan]Step 3 · Blocks[/bold cyan]")
    console.print(
        "[dim]Tip for 2b2t: [bold]Netherrack[/bold] and [bold]Cobblestone[/bold] "
        "are the most abundant near spawn. [bold]Obsidian[/bold] is great for "
        "permanent builds. [bold]Concrete[/bold] looks clean but requires crafting.[/dim]\n"
    )
    text_block = _ask_block("Main text block:")

    # ── 12. Outline ───────────────────────────────────────────────────────────
    console.print()
    use_outline = _ask_confirm("Add an outline / border around the text?", default=False)
    outline_block: str | None = None
    outline_thickness = 1
    if use_outline:
        outline_block = _ask_block("Outline block:")
        outline_thickness = _ask_int(
            "Outline thickness (blocks)", default=1, min_val=1, max_val=5
        )

    # ── 13. Background ────────────────────────────────────────────────────────
    console.print()
    use_background = _ask_confirm(
        "Fill the background (air gaps inside the schematic bounding box) with a block?",
        default=False,
    )
    background_block: str | None = None
    if use_background:
        console.print(
            "[dim]Background blocks fill the rectangular bounding box behind the text. "
            "Useful for signs, banners, or chroma-key style builds.[/dim]"
        )
        background_block = _ask_block("Background block:")

    # ── 14. Output settings ───────────────────────────────────────────────────
    console.print()
    console.rule("[bold cyan]Step 4 · Output[/bold cyan]")

    safe_name = "_".join(lines[0].split())[:40].replace("/", "-").replace("\\", "-")
    default_filename = f"{safe_name or 'text_schematic'}.litematic"

    output_filename: str | None = questionary.text(
        "Output filename:",
        default=default_filename,
        style=Q_STYLE,
        validate=lambda v: True if v.strip() else "Filename cannot be empty.",
    ).ask()
    if output_filename is None:
        sys.exit(0)
    output_filename = output_filename.strip()

    output_dir: str | None = questionary.text(
        "Save directory (leave blank for current folder):",
        default="",
        style=Q_STYLE,
    ).ask()
    if output_dir is None:
        sys.exit(0)
    output_dir = output_dir.strip()
    if not output_dir:
        output_dir = "."

    author: str | None = questionary.text(
        "Author name (embedded in schematic metadata):",
        default="2b2t_player",
        style=Q_STYLE,
    ).ask()
    if author is None:
        sys.exit(0)

    # ── 15. Render grid ───────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Rendering…[/bold cyan]")
    grid = render_text(
        lines=lines,
        scale=scale,
        char_spacing=char_spacing,
        line_spacing=line_spacing,
        outline=use_outline,
        outline_thickness=outline_thickness,
        background=use_background,
        padding=padding,
    )

    # ── 16. Summary table ─────────────────────────────────────────────────────
    console.print()
    console.rule("[bold cyan]Summary[/bold cyan]")

    dims = get_schematic_dimensions(grid, orientation, depth)
    block_counts = count_blocks(grid)
    total_non_air = block_counts["total"]

    dim_table = Table(
        title="Schematic Dimensions",
        box=box.SIMPLE_HEAD,
        title_style="bold",
        show_header=True,
        header_style="bold cyan",
    )
    dim_table.add_column("Axis", style="bold")
    dim_table.add_column("Blocks", justify="right")
    dim_table.add_column("Chunks", justify="right")

    dim_table.add_row("X (east–west)",     str(dims["x"]), str(dims["chunks_x"]))
    dim_table.add_row("Y (vertical)",      str(dims["y"]), str(dims["chunks_y"]))
    dim_table.add_row("Z (north–south)",   str(dims["z"]), str(dims["chunks_z"]))
    dim_table.add_row(
        "[bold]Total volume[/bold]",
        f"[bold]{dims['volume']:,}[/bold]",
        "—",
    )
    console.print(dim_table)

    block_table = Table(
        title="Block Counts",
        box=box.SIMPLE_HEAD,
        title_style="bold",
        show_header=True,
        header_style="bold cyan",
    )
    block_table.add_column("Type",  style="bold")
    block_table.add_column("Block ID",  style="dim")
    block_table.add_column("Count", justify="right")

    # Multiply 2-D count by depth for the actual total (depth layers)
    def _total(count_2d: int) -> str:
        return f"{count_2d * depth:,}"

    block_table.add_row(
        "Text",
        text_block,
        _total(block_counts["text"]),
    )
    if use_outline and outline_block:
        block_table.add_row(
            "Outline",
            outline_block,
            _total(block_counts["outline"]),
        )
    if use_background and background_block:
        block_table.add_row(
            "Background",
            background_block,
            _total(block_counts["background"]),
        )
    block_table.add_row(
        "[bold]TOTAL non-air[/bold]",
        "",
        f"[bold]{total_non_air * depth:,}[/bold]",
    )
    console.print(block_table)

    # ── 17. ASCII preview ─────────────────────────────────────────────────────
    console.print()
    show_preview = _ask_confirm("Show an ASCII preview in the terminal?", default=True)
    if show_preview:
        preview = grid_to_ascii_preview(grid)
        console.print(
            Panel(
                preview,
                title="Preview  (█ text  ▓ outline  ░ background)",
                border_style="bright_black",
                padding=(0, 1),
            )
        )

    # ── 18. Confirmation ──────────────────────────────────────────────────────
    console.print()
    output_path = Path(output_dir) / output_filename

    console.print(
        Panel(
            f"[bold]Text:[/bold]          {repr(chr(10).join(lines))}\n"
            f"[bold]Orientation:[/bold]   {orientation.upper()}\n"
            f"[bold]Scale:[/bold]         {scale}× (each bitmap pixel = {scale} block(s))\n"
            f"[bold]Char spacing:[/bold]  {char_spacing} px\n"
            f"[bold]Line spacing:[/bold]  {line_spacing} blocks\n"
            f"[bold]Depth:[/bold]         {depth} block(s)\n"
            f"[bold]Padding:[/bold]       {padding} block(s)\n"
            f"[bold]Text block:[/bold]    {text_block}\n"
            + (f"[bold]Outline:[/bold]       {outline_block} (thickness {outline_thickness})\n" if use_outline else "")
            + (f"[bold]Background:[/bold]   {background_block}\n" if use_background else "")
            + f"[bold]Output:[/bold]        {output_path}",
            title="[bold cyan]Final Configuration[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
        )
    )
    console.print()

    if not _ask_confirm("Generate and save the schematic?", default=True):
        console.print("[yellow]Cancelled. No file was written.[/yellow]")
        sys.exit(0)

    # ── 19. Generate ──────────────────────────────────────────────────────────
    console.print()
    with console.status("[bold cyan]Generating schematic…[/bold cyan]", spinner="dots"):
        saved_path = save_schematic(
            grid=grid,
            orientation=orientation,
            text_block=text_block,
            outline_block=outline_block if use_outline else None,
            background_block=background_block if use_background else None,
            depth=depth,
            output_path=output_path,
            name=" / ".join(lines),
            author=author.strip() or "litematic-text-generator",
            description=(
                f"Generated by litematic-text-schematic-generator. "
                f"Scale={scale}, orientation={orientation}."
            ),
        )

    console.print()
    console.print(
        Panel(
            f"[bold green]✔  Schematic saved successfully![/bold green]\n\n"
            f"[bold]File:[/bold]  {saved_path}\n"
            f"[bold]Size:[/bold]  {saved_path.stat().st_size / 1024:.1f} KB\n\n"
            "[dim]In Litematica:  press [bold]M[/bold] → [bold]Load Schematic[/bold] "
            "and navigate to this file to import it.\n"
            "With Icebox Printer, freeze in place, load the schematic, "
            "align it, and start printing![/dim]",
            title="[bold green]Done[/bold green]",
            box=box.ROUNDED,
            border_style="green",
        )
    )
    console.print()

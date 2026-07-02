# -*- coding: utf-8 -*-

"""
Reads a RAVEN puzzle JSON file and emits a standalone .tex file with TikZ.

Usage:
    python tikz_render.py /path/to/puzzle.json -o /path/to/output.tex
"""

import argparse
import json
import string
import sys


# Pattern mapping: color_level (0-9) -> TikZ fill specification
# Level 0 = lightest (outline only), Level 9 = darkest (solid black)
PATTERN_MAP = {
    0: None,                    # outline only
    1: "dots",
    2: "north east lines",
    3: "north west lines",
    4: "horizontal lines",
    5: "vertical lines",
    6: "crosshatch",
    7: "grid",
    8: "crosshatch dots",
    9: "black",                 # solid fill
}

# Cell size in cm
CELL_SIZE = 2.5


def _shape_tikz_node(entity, cx, cy):
    """Generate TikZ code to draw a single entity.

    Args:
        entity: dict with keys type, size, color_level, angle, position
        cx, cy: center coordinates in TikZ space (cm)

    Returns:
        string of TikZ draw commands
    """
    shape_type = entity["type"]
    if shape_type == "none":
        return ""

    size = entity["size"]
    color_level = entity["color_level"]
    angle = entity["angle"]

    # Compute minimum size from the bounding box and size factor
    pos = entity["position"]
    # pos is [row, col, width, height] in [0,1] normalized
    bbox_unit = min(pos[2], pos[3]) if len(pos) >= 4 else 0.5
    min_size_cm = bbox_unit * size * CELL_SIZE

    # Fill specification
    fill_spec = _get_fill_spec(color_level)

    # Shape node options
    if shape_type == "circle":
        shape_opt = "circle, minimum size={:.3f}cm".format(min_size_cm)
    elif shape_type == "triangle":
        shape_opt = "regular polygon, regular polygon sides=3, minimum size={:.3f}cm".format(min_size_cm)
    elif shape_type == "square":
        shape_opt = "regular polygon, regular polygon sides=4, minimum size={:.3f}cm".format(min_size_cm)
    elif shape_type == "pentagon":
        shape_opt = "regular polygon, regular polygon sides=5, minimum size={:.3f}cm".format(min_size_cm)
    elif shape_type == "hexagon":
        shape_opt = "regular polygon, regular polygon sides=6, minimum size={:.3f}cm".format(min_size_cm)
    else:
        return ""

    # Rotation
    rotate_opt = "rotate={}".format(angle) if angle != 0 else ""

    # Assemble options
    opts = [shape_opt, "draw=black", "inner sep=0pt"]
    if fill_spec:
        opts.append(fill_spec)
    if rotate_opt:
        opts.append(rotate_opt)

    opts_str = ", ".join(opts)
    return "    \\node[{}] at ({:.3f},{:.3f}) {{}};\n".format(opts_str, cx, cy)


def _get_fill_spec(color_level):
    """Return TikZ fill option string for a given color level."""
    pattern = PATTERN_MAP.get(color_level)
    if pattern is None:
        return ""  # outline only
    if pattern == "black":
        return "fill=black"
    return "pattern={}".format(pattern)


def render_cell(panel, x_offset, y_offset):
    """Render a single panel cell as TikZ code.

    Args:
        panel: dict with "structure" and "entities", or None for missing cell
        x_offset, y_offset: top-left corner of the cell in TikZ coordinates

    Returns:
        string of TikZ commands
    """
    lines = []

    # Draw cell border
    lines.append("    \\draw ({:.3f},{:.3f}) rectangle ({:.3f},{:.3f});\n".format(
        x_offset, y_offset, x_offset + CELL_SIZE, y_offset - CELL_SIZE
    ))

    if panel is None:
        # Missing cell: draw "?"
        cx = x_offset + CELL_SIZE / 2
        cy = y_offset - CELL_SIZE / 2
        lines.append("    \\node[font=\\Large\\bfseries] at ({:.3f},{:.3f}) {{?}};\n".format(cx, cy))
        return "".join(lines)

    structure = panel["structure"]

    # Draw structure dividers
    if structure == "Left_Right":
        mid_x = x_offset + CELL_SIZE / 2
        lines.append("    \\draw[thin, gray] ({:.3f},{:.3f}) -- ({:.3f},{:.3f});\n".format(
            mid_x, y_offset, mid_x, y_offset - CELL_SIZE
        ))
    elif structure == "Up_Down":
        mid_y = y_offset - CELL_SIZE / 2
        lines.append("    \\draw[thin, gray] ({:.3f},{:.3f}) -- ({:.3f},{:.3f});\n".format(
            x_offset, mid_y, x_offset + CELL_SIZE, mid_y
        ))

    # Draw entities
    for entity in panel["entities"]:
        if entity["type"] == "none":
            continue
        pos = entity["position"]
        # pos = [row, col, width, height] in normalized [0,1] coords
        # Map to TikZ: col -> x, row -> y (inverted)
        cx = x_offset + pos[1] * CELL_SIZE
        cy = y_offset - pos[0] * CELL_SIZE
        lines.append(_shape_tikz_node(entity, cx, cy))

    return "".join(lines)


def render_puzzle(puzzle_data):
    """Generate complete TikZ code for a puzzle.

    Args:
        puzzle_data: dict loaded from JSON

    Returns:
        string of complete .tex file content
    """
    grid = puzzle_data["grid"]
    candidates = puzzle_data["answer"]["candidates"]
    correct_index = puzzle_data["answer"]["correct_index"]
    num_choices = len(candidates)

    lines = []

    # LaTeX preamble
    lines.append("\\documentclass[border=5mm]{standalone}\n")
    lines.append("\\usepackage{amssymb}\n")
    lines.append("\\usepackage{tikz}\n")
    lines.append("\\usetikzlibrary{patterns, shapes.geometric}\n")
    lines.append("\\begin{document}\n")
    lines.append("\\begin{tikzpicture}\n")

    # Draw the 3x3 grid
    for row in range(3):
        for col in range(3):
            x_off = col * CELL_SIZE
            y_off = -row * CELL_SIZE
            panel = grid[row][col]
            lines.append(render_cell(panel, x_off, y_off))

    # Gap between grid and answer choices
    answer_y_top = -3 * CELL_SIZE - 0.8

    # Draw answer choices in a single row
    total_width = num_choices * CELL_SIZE
    grid_width = 3 * CELL_SIZE
    x_start = (grid_width - total_width) / 2  # center answers under grid

    for i, candidate in enumerate(candidates):
        x_off = x_start + i * CELL_SIZE
        y_off = answer_y_top
        lines.append(render_cell(candidate, x_off, y_off))

        # Label below: A, B, C, D, E, F...
        label = string.ascii_uppercase[i]
        label_x = x_off + CELL_SIZE / 2
        label_y = y_off - CELL_SIZE - 0.3
        lines.append("    \\node[font=\\small] at ({:.3f},{:.3f}) {{({})}};\n".format(
            label_x, label_y, label
        ))

    # Mark correct answer with a small indicator
    correct_label = string.ascii_uppercase[correct_index]
    correct_x = x_start + correct_index * CELL_SIZE + CELL_SIZE / 2
    correct_y = answer_y_top - CELL_SIZE - 0.6
    lines.append("    \\node[font=\\tiny, green!50!black] at ({:.3f},{:.3f}) "
                 "{{$\\checkmark$}};\n".format(correct_x, correct_y))

    lines.append("\\end{tikzpicture}\n")
    lines.append("\\end{document}\n")

    return "".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Render RAVEN puzzle JSON to TikZ/LaTeX")
    parser.add_argument("input", help="Path to puzzle .json file")
    parser.add_argument("-o", "--output", default=None,
                        help="Output .tex path (default: stdout)")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        puzzle_data = json.load(f)

    tex_content = render_puzzle(puzzle_data)

    if args.output:
        with open(args.output, "w") as f:
            f.write(tex_content)
    else:
        sys.stdout.write(tex_content)


if __name__ == "__main__":
    main()

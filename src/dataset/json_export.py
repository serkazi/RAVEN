# -*- coding: utf-8 -*-

"""
Serializes RAVEN AoT trees + rules into a clean JSON file for TikZ rendering.
"""

import json
import random

import numpy as np

from AoT import Root
from const import TYPE_VALUES, SIZE_VALUES, COLOR_VALUES, ANGLE_VALUES


def serialize_panel(root):
    """Convert an AoT panel (Root node) into a JSON-serializable dict.

    Args:
        root: A Root AoT node (must be a parse graph, i.e. is_pg=True)

    Returns:
        dict with keys: "structure", "entities"
    """
    assert isinstance(root, Root)
    structure_name, entities = root.prepare()
    entity_list = []
    for entity in entities:
        entity_dict = {
            "type": entity.type.get_value(),
            "size": entity.size.get_value(),
            "color_level": int(entity.color.get_value_level()),
            "angle": int(entity.angle.get_value()),
            "position": [float(x) for x in entity.bbox],
        }
        entity_list.append(entity_dict)
    return {
        "structure": structure_name,
        "entities": entity_list,
    }


def serialize_rules(rule_groups):
    """Convert rule_groups into a JSON-serializable list.

    Args:
        rule_groups: list of list of Rule objects

    Returns:
        list of dicts with keys: "name", "attr", "value", "component"
    """
    rules_out = []
    for component_idx, rule_group in enumerate(rule_groups):
        for rule in rule_group:
            rules_out.append({
                "name": rule.name,
                "attr": rule.attr,
                "value": int(rule.value) if rule.value is not None else None,
                "component": component_idx,
            })
    return rules_out


def select_distractors(correct_aot, all_candidates, num_choices):
    """Select a subset of distractors that maximizes diversity from the correct answer.

    Args:
        correct_aot: the correct answer AoT
        all_candidates: list of 8 AoT candidates (1 correct + 7 wrong)
        num_choices: total number of choices (including correct)

    Returns:
        (selected_candidates, correct_index) where selected_candidates is a list
        of num_choices AoT nodes, and correct_index is the position of the correct answer.
    """
    num_distractors = num_choices - 1

    # Separate correct from wrong
    wrong = [c for c in all_candidates if c is not correct_aot]

    if num_distractors >= len(wrong):
        # Use all available distractors
        selected = wrong[:num_distractors]
    else:
        # Score each distractor by attribute distance from correct answer
        correct_panel = serialize_panel(correct_aot)
        scores = []
        for i, candidate in enumerate(wrong):
            panel = serialize_panel(candidate)
            dist = _panel_distance(correct_panel, panel)
            scores.append((dist, i))
        # Sort by distance (descending) to pick most diverse
        scores.sort(key=lambda x: -x[0])
        selected = [wrong[scores[j][1]] for j in range(num_distractors)]

    # Combine and shuffle
    final = [correct_aot] + selected
    random.shuffle(final)
    correct_index = final.index(correct_aot)
    return final, correct_index


def _panel_distance(panel_a, panel_b):
    """Compute a simple attribute distance between two serialized panels."""
    dist = 0
    ents_a = panel_a["entities"]
    ents_b = panel_b["entities"]
    # Compare entity-by-entity (up to the shorter list)
    for ea, eb in zip(ents_a, ents_b):
        if ea["type"] != eb["type"]:
            dist += 3
        if ea["color_level"] != eb["color_level"]:
            dist += abs(ea["color_level"] - eb["color_level"])
        if ea["size"] != eb["size"]:
            dist += 2
        if ea["angle"] != eb["angle"]:
            dist += 1
    # Penalize different number of entities
    dist += abs(len(ents_a) - len(ents_b)) * 3
    return dist


def export_puzzle_json(config_name, rule_groups, context_aots, candidates,
                       correct_aot, num_choices=6):
    """Export a complete puzzle as a JSON-serializable dict.

    Args:
        config_name: string like "center_single", "distribute_four", etc.
        rule_groups: list of list of Rule objects
        context_aots: list of 8 AoT nodes (row-major: r1c1, r1c2, r1c3, r2c1, ...)
        candidates: list of 8 AoT candidates (already shuffled)
        correct_aot: the correct answer AoT node
        num_choices: number of answer choices to include (default 6)

    Returns:
        dict suitable for json.dumps()
    """
    # Build grid (3x3, last cell is the answer)
    grid = []
    for row in range(3):
        row_panels = []
        for col in range(3):
            idx = row * 3 + col
            if idx < 8:
                row_panels.append(serialize_panel(context_aots[idx]))
            else:
                # The missing cell (row 2, col 2)
                row_panels.append(None)
        grid.append(row_panels)

    # Select answer subset
    selected_candidates, correct_index = select_distractors(
        correct_aot, candidates, num_choices
    )

    # Serialize answer candidates
    answer_panels = [serialize_panel(c) for c in selected_candidates]

    # Serialize rules
    rules = serialize_rules(rule_groups)

    return {
        "config": config_name,
        "rules": rules,
        "grid": grid,
        "answer": {
            "correct_index": correct_index,
            "candidates": answer_panels,
        },
    }


def save_puzzle_json(puzzle_dict, filepath):
    """Write puzzle dict to a JSON file.

    Args:
        puzzle_dict: dict from export_puzzle_json()
        filepath: output .json path
    """
    with open(filepath, "w") as f:
        json.dump(puzzle_dict, f, indent=2)

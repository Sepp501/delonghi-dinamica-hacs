"""Explicit recipe-save packet builder for the ECAM370.95.T.

This function is used only by a manually triggered button and must never be
called from the status poller. The 0x83 START action also appears in beverage
commands; only the SAVE operation has been verified on the tested hardware.
Never substitute PREPARE or PREPARE_AND_SAVE without separate verification.
"""
import binascii

from .recipe_edit_draft import (
    TEST_PROFILE_ID, TEST_RECIPE_ID,
    plan_test_recipe,
)

BREW_TAG_WIDTHS = {0x01: 2, 0x09: 2, 0x02: 1, 0x0C: 1}
MODE_SAVE = 0x01
# Confirmed from the Coffee Link APK-derived builder: final byte packs
# profile_id in bits 2..7 and operation in bits 0..1.
# Confirmed for the coffee amount on ECAM370.95.T.
ACTION_START = 0x01


def profile_operation(profile_id: int, operation: int) -> int:
    if not 1 <= profile_id <= 4 or not 0 <= operation <= 3:
        raise ValueError("Unsupported profile or operation")
    return ((profile_id & 0x3F) << 2) | (operation & 0x03)



def make_save_probe(original, draft: dict, *, allow_all: bool = False) -> bytes:
    """Build a save-only 0x83 command; readback MUST verify applied values."""
    proposed = plan_test_recipe(
        original, int(draft["coffee"]), float(draft["milk"]),
        int(draft["strength"]), str(draft["name"]), allow_all=allow_all,
    )
    if not allow_all and (original.profile_id != TEST_PROFILE_ID or original.recipe_id != TEST_RECIPE_ID):
        raise ValueError("Test limited to Sepp / Frei 1")
    if (
        proposed.coffee_ml_after == original.coffee_ml
        and proposed.milk_seconds_after == (original.milk_seconds or 0.0)
        and proposed.strength_after == original.strength
    ):
        raise ValueError("Keine geänderten Rezeptwerte zum Speichern")

    # Keep all brewing tags as received, including milk. Strip only metadata
    # tags (0x19, 0x1B, 0x1C), which the reference Barista implementation also
    # excludes from 0x83 beverage commands.
    ingredients = bytearray()
    for tag, value in proposed.proposed_parameters:
        width = BREW_TAG_WIDTHS.get(tag)
        if width is None:
            if tag not in (0x19, 0x1B, 0x1C):
                raise ValueError(f"Unknown tag {tag:#x}; no write attempted")
            continue
        if not (0 <= value < 256 ** width):
            raise ValueError("Ingredient out of range")
        ingredients.append(tag)
        ingredients.extend(int(value).to_bytes(width, "big"))

    # [0x83,0xF0,recipe,action=START,ingredient...,profile+SAVE]
    # START also occurs in brewing commands. Keep the observed SAVE mode
    # unchanged; readback can detect success, not rule out side effects.
    body = (
        bytes((0x83, 0xF0, original.recipe_id, ACTION_START))
        + bytes(ingredients)
        + bytes((profile_operation(original.profile_id, MODE_SAVE),))
    )
    prefix = bytes((0x0D, len(body) + 3)) + body
    return prefix + binascii.crc_hqx(prefix, 0x1D0F).to_bytes(2, "big")


def make_profile_select(profile_id: int = TEST_PROFILE_ID) -> bytes:
    """Known 0xA9 profile selector for the requested machine profile."""
    if profile_id not in (1, 2, 3):
        raise ValueError("Nicht unterstütztes Profil")
    payload = bytes((0x0D, 0x06, 0xA9, 0xF0, profile_id))
    return payload + binascii.crc_hqx(payload, 0x1D0F).to_bytes(2, "big")

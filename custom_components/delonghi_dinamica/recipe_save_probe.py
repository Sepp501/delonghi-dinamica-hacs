"""Experimental single-slot save probe, never used by the regular poller.

Only for Sepp / Frei 1. A save-mode enum exists in independent ECAM protocol
projects, but is not yet verified for ECAM370.95.T. Never use PREPARE or
PREPARE_AND_SAVE here.
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
# This is a *candidate* for ECAM370.95.T, not a verified successful save.
ACTION_START = 0x01


def profile_operation(profile_id: int, operation: int) -> int:
    if not 1 <= profile_id <= 4 or not 0 <= operation <= 3:
        raise ValueError("Unsupported profile or operation")
    return ((profile_id & 0x3F) << 2) | (operation & 0x03)



def make_save_probe(original, draft: dict) -> bytes:
    """Make one candidate saving ONLY coffee quantity, requiring no other changes."""
    proposed = plan_test_recipe(
        original, int(draft["coffee"]), float(draft["milk"]),
        int(draft["strength"]), str(draft["name"]),
    )
    if original.profile_id != TEST_PROFILE_ID or original.recipe_id != TEST_RECIPE_ID:
        raise ValueError("Test limited to Sepp / Frei 1")
    if proposed.milk_seconds_after != original.milk_seconds:
        raise ValueError("Milk must remain unchanged for the first save test")
    if proposed.strength_after != original.strength:
        raise ValueError("Strength must remain unchanged for the first save test")
    if proposed.name_after != "Frei 1":
        raise ValueError("Name must remain Frei 1 for the first save test")
    if proposed.coffee_ml_after == original.coffee_ml:
        raise ValueError("Choose a different coffee quantity for the test")

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
    # START is also used by brewing; the SAVE operation is unconfirmed for
    # this model and could still trigger brewing. Manual test only.
    body = (
        bytes((0x83, 0xF0, TEST_RECIPE_ID, ACTION_START))
        + bytes(ingredients)
        + bytes((profile_operation(TEST_PROFILE_ID, MODE_SAVE),))
    )
    prefix = bytes((0x0D, len(body) + 3)) + body
    return prefix + binascii.crc_hqx(prefix, 0x1D0F).to_bytes(2, "big")


def make_profile_select() -> bytes:
    """Known 0xA9 profile selector: explicitly select target profile 1."""
    payload = bytes((0x0D, 0x06, 0xA9, 0xF0, TEST_PROFILE_ID))
    return payload + binascii.crc_hqx(payload, 0x1D0F).to_bytes(2, "big")

"""Offline-only coffee recipe draft for ECAM370.95.T.

This module must not send any BLE commands. Its output is a proposed change
that has to be reviewed before we implement a verified save operation.
"""
from dataclasses import dataclass

# DeLonghi ECAM370.95 manual: normal COFFEE programming range (mL).
COFFEE_MIN_ML = 100
COFFEE_MAX_ML = 240
TEST_PROFILE_ID = 1
TEST_RECIPE_ID = 233

COFFEE_TAG = 0x01
MILK_TAG = 0x09
INVERSION_TAG = 0x0C
# Tags that the verified recipe reader already understands.
KNOWN_TAGS = frozenset((0x01, 0x09, 0x02, 0x0C, 0x1B, 0x19, 0x1C))


@dataclass(frozen=True)
class CoffeeRecipeDraft:
    """Explicit data-only preview; NOT a BLE write payload."""

    profile_id: int
    recipe_id: int
    original_parameters: tuple[tuple[int, int], ...]
    proposed_parameters: tuple[tuple[int, int], ...]
    coffee_ml_before: int
    coffee_ml_after: int
    removed_milk_parameters: tuple[tuple[int, int], ...]
    requires_protocol_confirmation: bool = True


def plan_test_coffee(original, coffee_ml: int) -> CoffeeRecipeDraft:
    """Plan one dry-run edit without mutating the source recipe.

    The selected 'Frei 1' slot currently has nonzero milk settings. This
    intentionally removes milk-related tags from the proposal, but whether
    the machine accepts this as *black coffee* is not yet confirmed.
    """
    if not isinstance(coffee_ml, int) or isinstance(coffee_ml, bool):
        raise ValueError("Coffee quantity must be an integer number of milliliters")
    if not COFFEE_MIN_ML <= coffee_ml <= COFFEE_MAX_ML:
        raise ValueError(f"Coffee quantity must be {COFFEE_MIN_ML}–{COFFEE_MAX_ML} mL")
    if (original.profile_id, original.recipe_id) != (TEST_PROFILE_ID, TEST_RECIPE_ID):
        raise ValueError("Only Sepp / Frei 1 can be prepared as a test draft")

    original_params = tuple(original.parameters)
    if any(tag not in KNOWN_TAGS for tag, _ in original_params):
        raise ValueError("Unknown ingredient tag: refusing to prepare an edit")
    if sum(tag == COFFEE_TAG for tag, _ in original_params) != 1:
        raise ValueError("Expected exactly one coffee quantity in the source recipe")

    milk_tags = frozenset((MILK_TAG, INVERSION_TAG))
    removed = tuple((tag, value) for tag, value in original_params if tag in milk_tags)
    updated = tuple(
        (tag, coffee_ml if tag == COFFEE_TAG else value)
        for tag, value in original_params
        if tag not in milk_tags
    )

    return CoffeeRecipeDraft(
        profile_id=original.profile_id,
        recipe_id=original.recipe_id,
        original_parameters=original_params,
        proposed_parameters=updated,
        coffee_ml_before=original.coffee_ml,
        coffee_ml_after=coffee_ml,
        removed_milk_parameters=removed,
    )

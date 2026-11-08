"""Validated, strictly offline recipe draft for Sepp's Frei 1.

Never transmit candidate packets to BLE without separately verified write protocol.
"""
from dataclasses import dataclass

COFFEE_MIN_ML = 100
COFFEE_MAX_ML = 240
MILK_MIN_SECONDS = 0
MILK_MAX_SECONDS = 90
TEST_PROFILE_ID = 1
TEST_RECIPE_ID = 233
COFFEE_TAG = 0x01
MILK_TAG = 0x09
STRENGTH_TAG = 0x02
INVERSION_TAG = 0x0C
KNOWN_TAGS = frozenset((0x01, 0x09, 0x02, 0x0C, 0x1B, 0x19, 0x1C))


@dataclass(frozen=True)
class CoffeeRecipeDraft:
    profile_id: int
    recipe_id: int
    original_parameters: tuple[tuple[int, int], ...]
    proposed_parameters: tuple[tuple[int, int], ...]
    coffee_ml_before: int
    coffee_ml_after: int
    removed_milk_parameters: tuple[tuple[int, int], ...]
    milk_seconds_after: float = 0.0
    strength_after: int = 3
    name_after: str = ""
    requires_protocol_confirmation: bool = True


def _valid_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Recipe name must be text")
    if any(ord(ch) < 32 for ch in name):
        raise ValueError("Recipe name contains control characters")
    name = name.strip()
    if not name or len(name) > 10:
        raise ValueError("Recipe name must be 1 to 10 printable characters")
    # 0xAA name responses are UTF-16BE in 20 bytes.
    if len(name.encode("utf-16-be")) > 20:
        raise ValueError("Recipe name exceeds 20 UTF-16 bytes")
    return name


def plan_test_recipe(original, coffee_ml: int, milk_seconds: float,
                     strength: int, name: str, *, allow_all: bool = False) -> CoffeeRecipeDraft:
    """Compute a candidate from the 0xA6 readback; does not produce a BLE command."""
    if allow_all:
        if original.profile_id not in (1, 2, 3) or original.recipe_id not in range(230, 236):
            raise ValueError("Nur Profile 1–3 und Rezepte 230–235 erlaubt")
    elif (original.profile_id, original.recipe_id) != (TEST_PROFILE_ID, TEST_RECIPE_ID):
        raise ValueError("Only profile Sepp / Frei 1 may be edited")
    if type(coffee_ml) is not int or not COFFEE_MIN_ML <= coffee_ml <= COFFEE_MAX_ML:
        raise ValueError("Coffee quantity is outside the supported 100–240 mL range")
    if isinstance(milk_seconds, bool) or not isinstance(milk_seconds, (int, float)):
        raise ValueError("Milk duration must be a number")
    ticks = round(milk_seconds * 10)
    if abs(ticks - milk_seconds * 10) > 1e-6 or not 0 <= ticks <= MILK_MAX_SECONDS * 10:
        raise ValueError("Milk duration must be between 0 and 90 seconds in 0.1s steps")
    if type(strength) is not int or not 1 <= strength <= 5:
        raise ValueError("Strength must be 1–5")
    name = _valid_name(name)
    params = tuple(original.parameters)
    if any(tag not in KNOWN_TAGS for tag, _ in params):
        raise ValueError("Unknown recipe tag; cannot prepare an edit")
    for tag in (COFFEE_TAG, STRENGTH_TAG):
        if sum(k == tag for k, _ in params) != 1:
            raise ValueError(f"Expected exactly one recipe field 0x{tag:02X}")
    if sum(k == MILK_TAG for k, _ in params) > 1:
        raise ValueError("Duplicate milk fields")
    proposed = []
    removed = []
    inserted_milk = False
    for tag, value in params:
        if tag == COFFEE_TAG:
            proposed.append((tag, coffee_ml))
        elif tag == STRENGTH_TAG:
            proposed.append((tag, strength))
        elif tag == MILK_TAG:
            if ticks:
                proposed.append((tag, ticks))
                inserted_milk = True
            else:
                removed.append((tag, value))
        elif tag == INVERSION_TAG and not ticks:
            removed.append((tag, value))
        else:
            proposed.append((tag, value))
    if ticks and not inserted_milk:
        # A new milk ingredient would change the drink type. Fail closed.
        raise ValueError("Original recipe has no milk field")
    return CoffeeRecipeDraft(
        profile_id=original.profile_id, recipe_id=original.recipe_id,
        original_parameters=params, proposed_parameters=tuple(proposed),
        coffee_ml_before=original.coffee_ml, coffee_ml_after=coffee_ml,
        removed_milk_parameters=tuple(removed),
        milk_seconds_after=ticks / 10, strength_after=strength,
        name_after=name,
    )


def plan_test_coffee(original, coffee_ml: int) -> CoffeeRecipeDraft:
    """Compatibility with the v0.2.2 offline-only test draft."""
    return plan_test_recipe(original, coffee_ml, 0, 3, "Frei 1")

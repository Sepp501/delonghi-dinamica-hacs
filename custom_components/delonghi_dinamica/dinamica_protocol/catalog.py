"""Combine decoded DeLonghi recipe names and parameters."""

from dataclasses import dataclass

from .recipes import Recipe


@dataclass(frozen=True)
class NamedRecipe:
    name: str
    icon: int
    recipe: Recipe


def combine_recipes(
    recipes: list[Recipe],
    names: list[dict],
    first_recipe_id: int = 230,
) -> list[NamedRecipe]:
    """Combine recipe parameters with names by recipe ID."""

    names_by_id = {
        first_recipe_id + index: entry
        for index, entry in enumerate(names)
    }

    result = []

    for recipe in recipes:
        entry = names_by_id.get(recipe.recipe_id)

        if entry is None:
            continue

        result.append(
            NamedRecipe(
                name=entry["name"],
                icon=entry["icon"],
                recipe=recipe,
            )
        )

    return result
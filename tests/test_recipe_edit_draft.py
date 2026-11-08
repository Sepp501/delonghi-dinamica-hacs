"""Offline test for Sepp's Frei-1 coffee recipe draft."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

PATH = Path(__file__).resolve().parents[1] / "custom_components" / "delonghi_dinamica" / "recipe_edit_draft.py"
spec = importlib.util.spec_from_file_location("draft_recipe", PATH)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def sample(**overrides):
    values = dict(
        profile_id=1, recipe_id=233, coffee_ml=80,
        parameters=((0x01, 80), (0x09, 160), (0x02, 3), (0x0C, 0), (0x19, 1)),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class CoffeeDraftTests(unittest.TestCase):
    def test_only_coffee_quantity_changes_and_milk_is_removed(self):
        original = sample()
        planned = module.plan_test_coffee(original, 150)
        self.assertEqual(planned.original_parameters, original.parameters)
        self.assertEqual(planned.proposed_parameters, ((0x01, 150), (0x02, 3), (0x19, 1)))
        self.assertTrue(planned.requires_protocol_confirmation)

    def test_rejects_other_slots(self):
        with self.assertRaises(ValueError):
            module.plan_test_coffee(sample(recipe_id=231), 150)

    def test_rejects_invalid_quantity(self):
        for value in (-1, 99, 241, 400, 150.2, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.plan_test_coffee(sample(), value)

    def test_rejects_unrecognized_fields(self):
        with self.assertRaises(ValueError):
            module.plan_test_coffee(sample(parameters=((0x01, 80), (0xFF, 2))), 150)

    def test_requires_existing_coffee_field(self):
        with self.assertRaises(ValueError):
            module.plan_test_coffee(sample(parameters=((0x09, 160),)), 150)


if __name__ == "__main__":
    unittest.main()

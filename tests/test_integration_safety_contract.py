"""Offline regression checks for public integration behavior and BLE write guards.

These deliberately inspect source structure without loading Home Assistant or
connecting to a coffee machine. They supplement, not replace, hardware tests.
"""
import ast
from pathlib import Path
import unittest


COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "delonghi_dinamica"


def parse(name: str) -> ast.Module:
    return ast.parse((COMPONENT / name).read_text(encoding="utf-8"), filename=name)


def cls(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)


def method(node: ast.ClassDef, name: str) -> ast.AsyncFunctionDef:
    return next(n for n in node.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)


def calls(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == name
    ]


class IntegrationSafetyContract(unittest.TestCase):
    def test_status_polling_is_separate_from_manual_writes(self):
        coordinator = cls(parse("coordinator.py"), "DinamicaCoordinator")
        poll = method(coordinator, "_async_update_data")
        # Neither direct write nor manual save logic is reached by periodic polls.
        self.assertEqual(calls(poll, "write_gatt_char"), [])
        self.assertEqual(calls(poll, "async_save_selected_recipe"), [])
        self.assertEqual(calls(poll, "async_experimental_save_test_coffee"), [])
        self.assertEqual(calls(poll, "async_experimental_save_test_name"), [])
        source = ast.unparse(poll)
        self.assertIn("self._async_poll_status()", source)
        self.assertIn("self._async_poll_data()", source)

    def test_only_one_recipe_save_button_is_instantiated(self):
        tree = parse("button.py")
        save = cls(tree, "DinamicaRecipeSave")
        press = method(save, "async_press")
        self.assertIn("self.coordinator.async_save_selected_recipe()", ast.unparse(press))
        setup = next(
            n for n in tree.body
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_setup_entry"
        )
        self.assertEqual(ast.unparse(setup).count("DinamicaRecipeSave("), 1)
        self.assertNotIn("DinamicaNameSaveProbe", ast.unparse(tree))
        self.assertIn("_test_recipe_save", ast.unparse(save))
        self.assertIn("_power_on", ast.unparse(cls(tree, "DinamicaPowerOn")))

    def test_public_entity_identifiers_are_stable(self):
        number = ast.unparse(parse("number.py"))
        text = ast.unparse(parse("text.py"))
        select = ast.unparse(parse("select.py"))
        for literal in ("test_coffee_draft_amount", "test_coffee_draft_"):
            self.assertIn(literal, number)
        self.assertIn("test_coffee_draft_name", text)
        self.assertIn("selected_", select)

    def test_six_shared_recipes_only(self):
        coordinator = cls(parse("coordinator.py"), "DinamicaCoordinator")
        full = method(coordinator, "_async_poll_data")
        source = ast.unparse(full)
        self.assertIn("range(230, 236)", source)
        self.assertIn("result['recipes'][1]", source)
        self.assertIn("recipe_request(1, recipe_id)", source)
        self.assertNotIn("for profile in (1, 2, 3)", source)

    def test_save_requires_manual_button_and_fresh_status(self):
        coordinator = cls(parse("coordinator.py"), "DinamicaCoordinator")
        trigger = method(coordinator, "async_save_selected_recipe")
        value = method(coordinator, "async_experimental_save_test_coffee")
        name = method(coordinator, "async_experimental_save_test_name")
        trigger_code = ast.unparse(trigger)
        value_code = ast.unparse(value)
        name_code = ast.unparse(name)
        self.assertIn("self.async_experimental_save_test_coffee()", trigger_code)
        self.assertIn("self.async_experimental_save_test_name()", trigger_code)
        self.assertIn("status['state_code'] != 7", value_code)
        self.assertIn("status['state_code'] != 7", name_code)
        self.assertIn("make_save_probe(before, draft, allow_all=True)", value_code)
        self.assertIn("recipe_request(profile_id, recipe_id)", value_code)
        self.assertIn("read_names()", name_code)
        self.assertIn("split_name_write_chunks(payload)", name_code)
        # Every chunk must be individually acknowledged before the next.
        self.assertIn("write_gatt_char(CHAR_UUID, chunk, response=True)", value_code)
        self.assertIn("write_gatt_char(CHAR_UUID, chunk, response=True)", name_code)

    def test_recipe_save_packet_retains_save_not_prepare(self):
        tree = parse("recipe_save_probe.py")
        assignments = {
            t.id: n.value.value
            for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
            for t in n.targets if isinstance(t, ast.Name)
        }
        self.assertEqual(assignments.get("MODE_SAVE"), 0x01)
        self.assertEqual(assignments.get("ACTION_START"), 0x01)
        self.assertNotIn("MODE_PREPARE", assignments)
        self.assertNotIn("MODE_PREPARE_AND_SAVE", assignments)


if __name__ == "__main__":
    unittest.main()

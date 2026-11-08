"""Offline-only checks of a single-slot experimental 0x83 Save probe."""
import binascii
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "delonghi_dinamica"
pkg = types.ModuleType("probe_test_dinamica")
pkg.__path__ = [str(ROOT)]
sys.modules[pkg.__name__] = pkg

for name in ("recipe_edit_draft", "recipe_save_probe"):
    spec = importlib.util.spec_from_file_location(
        f"{pkg.__name__}.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

save = sys.modules["probe_test_dinamica.recipe_save_probe"]


def recipe():
    return SimpleNamespace(
        profile_id=1, recipe_id=233, coffee_ml=80,
        milk_seconds=16.0, strength=3,
        parameters=((1, 80), (9, 160), (2, 3), (12, 0),
                    (28, 0), (27, 4), (25, 0)),
    )


def draft(**kwargs):
    return dict(coffee=100, milk=16.0, strength=3, name="Frei 1", **kwargs)


class SaveProbeTests(unittest.TestCase):
    def test_packet_is_save_only_with_correct_crc(self):
        p = save.make_save_probe(recipe(), draft())
        self.assertEqual(p[0], 0x0D)
        self.assertEqual(len(p), p[1] + 1)
        self.assertEqual(p[2:6], bytes((0x83, 0xF0, 233, 0x01)))
        self.assertEqual(p[-3], 0x05)
        self.assertEqual(int.from_bytes(p[-2:], "big"), binascii.crc_hqx(p[:-2], 0x1D0F))
        # Never include profile metadata tags.
        self.assertEqual(p[6:-3], bytes.fromhex("01 00 64 09 00 A0 02 03 0C 00"))

    def test_profile_operation_encoding(self):
        self.assertEqual(save.profile_operation(1, save.MODE_SAVE), 0x05)
        self.assertEqual(save.profile_operation(1, 2), 0x06)
        self.assertEqual(save.profile_operation(2, save.MODE_SAVE), 0x09)
        with self.assertRaises(ValueError):
            save.profile_operation(0, save.MODE_SAVE)

    def test_changes_outside_coffee_are_rejected(self):
        changes = [
            {"milk": 0}, {"strength": 5}, {"name": "Testkaffee"},
            {"coffee": 80},
        ]
        for changed in changes:
            options = dict(coffee=100, milk=16.0, strength=3, name="Frei 1")
            options.update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                save.make_save_probe(recipe(), options)

    def test_other_slot_rejected(self):
        r = recipe()
        r.recipe_id = 232
        with self.assertRaises(ValueError):
            save.make_save_probe(r, draft())

    def test_profile_select_packet_crc(self):
        p = save.make_profile_select()
        self.assertEqual(p[:5], bytes.fromhex("0D 06 A9 F0 01"))
        self.assertEqual(int.from_bytes(p[-2:], "big"), binascii.crc_hqx(p[:-2], 0x1D0F))


if __name__ == "__main__":
    unittest.main()

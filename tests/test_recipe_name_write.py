"""Offline tests of APK-recovered name-write command. No BLE access."""
import binascii
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "delonghi_dinamica"
pkg = types.ModuleType("name_write_test")
pkg.__path__ = [str(ROOT)]
sys.modules[pkg.__name__] = pkg
for name in ("recipe_edit_draft", "recipe_name_write"):
    spec = importlib.util.spec_from_file_location(
        f"{pkg.__name__}.{name}", ROOT / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
names = sys.modules[f"{pkg.__name__}.recipe_name_write"]


class NameWriteTests(unittest.TestCase):
    def test_exact_packet_layout_and_crc(self):
        p = names.build_name_write("Testkaffee", icon=7)
        self.assertEqual(len(p), 29)
        self.assertEqual(p[:6], bytes.fromhex("0D 1C AB F0 04 04"))
        self.assertEqual(p[6:26], "Testkaffee".encode("utf-16-be"))
        self.assertEqual(p[26], 7)
        self.assertEqual(p[27:], binascii.crc_hqx(p[:-2], 0x1D0F).to_bytes(2,"big"))

    def test_short_name_null_padding(self):
        p = names.build_name_write("NEU", icon=2)
        self.assertEqual(p[6:12], "NEU".encode("utf-16-be"))
        self.assertEqual(p[12:26], b"\\x00" * 14)

    def test_non_ascii_name(self):
        p = names.build_name_write("München", icon=3)
        self.assertEqual(p[6:20], "München".encode("utf-16-be"))

    def test_restrictions(self):
        bad = (
            dict(name="Hallo", icon=0, profile_id=2),
            dict(name="Hallo", icon=0, recipe_id=232),
            dict(name="Hallo", icon=-1),
            dict(name="ÜberlangerName", icon=0),
            dict(name="", icon=0),
        )
        for kw in bad:
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                names.build_name_write(**kw)

    def test_name_slot_mapping_preserves_icon(self):
        source = [{"name":f"Frei {n}", "icon":n} for n in range(1,7)]
        self.assertEqual(names.get_test_name(source), {"name":"Frei 4","icon":4})
        with self.assertRaises(ValueError):
            names.get_test_name(source[:3])


if __name__ == "__main__":
    unittest.main()

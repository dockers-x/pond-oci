import importlib.util
from pathlib import Path
import tempfile
import unittest


class HardlinkTopologyTests(unittest.TestCase):
    def checker(self):
        specification = importlib.util.spec_from_file_location("hardlinks", Path(__file__).resolve().parents[1] / "scripts/check-hardlinks.py")
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

    def test_preserves_link_groups_without_comparing_inode_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            staged, final = Path(directory) / "staged", Path(directory) / "final"
            for root in (staged, final):
                root.mkdir()
                (root / "first").write_bytes(b"payload")
                (root / "second").hardlink_to(root / "first")
                (root / "independent").write_bytes(b"payload")
                (root / "symlink").symlink_to("first")
            self.checker().compare(staged, final)

    def test_rejects_extra_links_and_lost_links(self):
        with tempfile.TemporaryDirectory() as directory:
            independent, linked = Path(directory) / "independent", Path(directory) / "linked"
            for root in (independent, linked):
                root.mkdir()
                (root / "first").write_bytes(b"same")
            (independent / "second").write_bytes(b"same")
            (linked / "second").hardlink_to(linked / "first")
            checker = self.checker()
            for staged, final in ((independent, linked), (linked, independent)):
                with self.subTest(staged=staged), self.assertRaisesRegex(ValueError, "hardlink"):
                    checker.compare(staged, final)

"""Verify module and class structure integrity."""

import ast
import pytest


class TestScraperStructure:
    REQUIRED_METHODS = [
        "login", "_do_login", "_ensure_browser", "_try_cookie_login",
        "_is_logged_in", "search_range", "_search_single_date", "close",
        "_capture_bearer_token", "_save_cookies", "_save_full_session",
    ]

    def test_class_instantiable(self):
        from scraper import UnitedScraper
        s = UnitedScraper()
        assert type(s).__name__ == "UnitedScraper"

    def test_all_required_methods_present(self):
        from scraper import UnitedScraper
        s = UnitedScraper()
        for method in self.REQUIRED_METHODS:
            assert hasattr(s, method), f"Missing method: {method}"

    def test_no_duplicate_functions(self):
        with open("scraper.py") as f:
            tree = ast.parse(f.read())
        names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        dupes = {n for n in names if names.count(n) > 1}
        assert not dupes, f"Duplicate functions: {dupes}"

    def test_find_chrome_is_module_level(self):
        with open("scraper.py") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == "_find_chrome":
                        pytest.fail("_find_chrome must not be inside a class")


class TestMainStructure:
    def test_main_imports_cleanly(self):
        from united_monitor import main, setup_logging
        assert callable(main)
        assert callable(setup_logging)

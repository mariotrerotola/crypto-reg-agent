"""Tests for prompt loading and version tagging."""

import pytest

from mas.prompts.loader import load_prompt, prompt_hash, prompt_version_tag


class TestPromptLoader:
    def test_load_asset_flags(self) -> None:
        content = load_prompt("asset_flags", "v1")
        assert "MiCAR classification expert" in content
        assert len(content) > 100

    def test_load_compliance(self) -> None:
        content = load_prompt("compliance", "v1")
        assert "{micar_class}" in content

    def test_load_nonexistent_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent", "v1")

    def test_load_nonexistent_version_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_prompt("asset_flags", "v99")


class TestPromptHash:
    def test_hash_is_deterministic(self) -> None:
        h1 = prompt_hash("asset_flags", "v1")
        h2 = prompt_hash("asset_flags", "v1")
        assert h1 == h2

    def test_hash_is_16_chars(self) -> None:
        h = prompt_hash("asset_flags", "v1")
        assert len(h) == 16

    def test_different_prompts_different_hashes(self) -> None:
        h1 = prompt_hash("asset_flags", "v1")
        h2 = prompt_hash("compliance", "v1")
        assert h1 != h2


class TestVersionTag:
    def test_tag_format(self) -> None:
        tag = prompt_version_tag("v1")
        assert tag.startswith("v1|")
        assert "asset_flags:" in tag
        assert "compliance:" in tag

    def test_tag_is_deterministic(self) -> None:
        t1 = prompt_version_tag("v1")
        t2 = prompt_version_tag("v1")
        assert t1 == t2

    def test_nonexistent_version_returns_version_string(self) -> None:
        tag = prompt_version_tag("v99")
        assert tag == "v99"

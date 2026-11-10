"""Tests for OpenAPI document inspection (Slice 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contractguard.adapters.spec_loader import SpecLoader
from contractguard.domain.errors import SpecValidationError, UnsupportedSpecError
from contractguard.tools.inspect import inspect as inspect_handler


def _fixture(name: str) -> Path:
    return Path("tests/fixtures/openapi") / name


@pytest.mark.parametrize(
    "fixture",
    ["giftshop.yaml", "giftshop-31.yaml", "giftshop-32.yaml"],
)
def test_valid_fixtures_inspect_as_valid(fixture: str) -> None:
    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    report = loader.inspect(_fixture(fixture))

    assert report.status == "VALID"
    assert report.operation_count >= 3
    assert report.sha256
    assert len(report.sha256) == 64
    methods = {(op.method, op.path) for op in report.operations}
    assert ("GET", "/products/{product_id}") in methods
    assert ("POST", "/products") in methods


def test_invalid_spec_returns_invalid_status(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("openapi: 3.0.3\ninfo:\n  title: x\npaths: {}\n", encoding="utf-8")

    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    report = loader.inspect(path)

    assert report.status == "INVALID_SPEC"
    assert report.errors
    assert "version" in " ".join(report.errors).lower()


def test_unsupported_version_returns_unsupported_status(tmp_path: Path) -> None:
    path = tmp_path / "old.yaml"
    path.write_text(
        "openapi: 2.0.0\ninfo:\n  title: x\n  version: '1'\npaths: {}\n",
        encoding="utf-8",
    )

    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    report = loader.inspect(path)

    assert report.status == "UNSUPPORTED"
    assert report.errors


def test_external_ref_is_blocked(tmp_path: Path) -> None:
    path = tmp_path / "external.yaml"
    path.write_text(
        "openapi: 3.0.3\n"
        "info:\n  title: x\n  version: '1'\n"
        "paths:\n"
        "  /x:\n"
        "    get:\n"
        "      responses:\n"
        "        '200':\n"
        "          description: ok\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                $ref: 'https://example.com/schema.json'\n",
        encoding="utf-8",
    )

    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    report = loader.inspect(path)

    assert report.status == "INVALID_SPEC"
    assert any("External $ref" in error for error in report.errors)


def test_oversized_file_returns_invalid_status(tmp_path: Path) -> None:
    path = tmp_path / "big.yaml"
    path.write_text("x" * 100, encoding="utf-8")

    loader = SpecLoader(max_spec_bytes=10)
    report = loader.inspect(path)

    assert report.status == "INVALID_SPEC"
    assert any("size limit" in error for error in report.errors)


def test_malformed_yaml_returns_invalid_status(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("openapi: 3.0.3\ninfo: [\n", encoding="utf-8")

    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    report = loader.inspect(path)

    assert report.status == "INVALID_SPEC"
    assert report.errors


def test_load_file_raises_for_invalid_spec(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("openapi: 3.0.3\ninfo:\n  title: x\npaths: {}\n", encoding="utf-8")

    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    with pytest.raises(SpecValidationError):
        loader.load_file(path)


def test_load_file_raises_for_unsupported_version(tmp_path: Path) -> None:
    path = tmp_path / "old.yaml"
    path.write_text(
        "openapi: 2.0.0\ninfo:\n  title: x\n  version: '1'\npaths: {}\n",
        encoding="utf-8",
    )

    loader = SpecLoader(max_spec_bytes=1024 * 1024)
    with pytest.raises(UnsupportedSpecError):
        loader.load_file(path)


def test_inspect_handler_returns_json_for_valid_fixture() -> None:
    result = json.loads(inspect_handler({"spec_path": "tests/fixtures/openapi/giftshop.yaml"}))

    assert result["status"] == "VALID"
    assert result["operation_count"] >= 3
    assert len(result["sha256"]) == 64


def test_inspect_handler_requires_spec_path() -> None:
    result = json.loads(inspect_handler({}))

    assert result["code"] == "INCOMPLETE"

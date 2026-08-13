from __future__ import annotations

import os
from typing import Literal, cast, get_args

import pytest

from pytester_utils.errors import FixtureRequestNotAvailableError

type PytesterRunMethod = Literal["inprocess", "subprocess"]
"""Method for running pytester sessions, either in the same process as the test or in a separate subprocess."""

PYTESTER_RUN_METHODS: set[PytesterRunMethod] = set(get_args(PytesterRunMethod.__value__))
_DEFAULT_PYTESTER_RUN_METHOD: PytesterRunMethod = "subprocess"

PYTESTER_RUN_METHOD_CLI_FLAG = "--pytester-run-method"
_PYTESTER_RUN_METHOD_PYTESTER_VAR = "pytester_run_method"
PYTESTER_RUN_METHOD_ENV_VAR = "PYTESTER_RUN_METHOD"

_CLI_PARSER_GROUP = "pytester-utils"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(_CLI_PARSER_GROUP)

    pytester_run_methods = [
        f"{_DEFAULT_PYTESTER_RUN_METHOD} (default)",
        *[method for method in PYTESTER_RUN_METHODS if method != _DEFAULT_PYTESTER_RUN_METHOD],
    ]
    group.addoption(
        PYTESTER_RUN_METHOD_CLI_FLAG,
        dest=_PYTESTER_RUN_METHOD_PYTESTER_VAR,
        help=f"Run method for pytester via {PYTESTER_RUN_METHOD_CLI_FLAG}, choices: {', '.join(pytester_run_methods)}",
        type=str,
        default=None,
        action="store",
        choices=list(PYTESTER_RUN_METHODS),
        required=False,
    )


def pytest_configure(config: pytest.Config) -> None:
    _parse_pytester_run_method_from_cli(config)


def _parse_pytester_run_method(value: str | None, source: str) -> PytesterRunMethod | None:
    if value is None or not isinstance(value, str):
        return None

    pytester_run_method = value.strip().lower()
    if pytester_run_method in PYTESTER_RUN_METHODS:
        return cast("PytesterRunMethod", pytester_run_method)

    msg = f"Invalid value for {source}: {value!r}. Valid choices are: {list(PYTESTER_RUN_METHODS)!r}"
    raise pytest.UsageError(msg)


def _parse_pytester_run_method_from_cli(config: pytest.Config) -> PytesterRunMethod | None:
    pytester_run_method_arg = cast("str | None", config.getoption(PYTESTER_RUN_METHOD_CLI_FLAG, None))
    return _parse_pytester_run_method(pytester_run_method_arg, f"command-line option {PYTESTER_RUN_METHOD_CLI_FLAG!r}")


def _parse_pytester_run_method_from_env() -> PytesterRunMethod | None:
    pytester_run_method_env = os.environ.get(PYTESTER_RUN_METHOD_ENV_VAR, None)
    return _parse_pytester_run_method(pytester_run_method_env, f"environment variable {PYTESTER_RUN_METHOD_ENV_VAR!r}")


def get_default_pytester_run_method(config: pytest.Config) -> PytesterRunMethod:
    pytester_run_method_from_cli = _parse_pytester_run_method_from_cli(config)
    if pytester_run_method_from_cli is not None:
        return pytester_run_method_from_cli

    pytester_run_method_from_env = _parse_pytester_run_method_from_env()
    if pytester_run_method_from_env is not None:
        return pytester_run_method_from_env

    return _DEFAULT_PYTESTER_RUN_METHOD


_request: pytest.FixtureRequest | None = None


def get_request() -> pytest.FixtureRequest:
    if _request is None:
        raise FixtureRequestNotAvailableError
    return _request


def pytest_runtest_setup(item: pytest.Item) -> None:
    if not isinstance(item, pytest.Function):
        return
    global _request  # noqa: PLW0603 - global-statement
    _request = item._request  # noqa: SLF001 - private-member-access


def pytest_runtest_teardown() -> None:
    global _request  # noqa: PLW0603 - global-statement
    _request = None

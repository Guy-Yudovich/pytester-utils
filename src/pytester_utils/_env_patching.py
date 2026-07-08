from __future__ import annotations

import os
import subprocess
import unittest.mock
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, cast

_ENV_VARS_TO_REMOVE_ON_SANITIZE = {
    "LC_CTYPE",
    "LINES",
    "COLUMNS",
}
_ENV_VAR_PREFIXES_TO_REMOVE_ON_SANITIZE = {
    "PYTEST_",
    "PYTESTER_",
}


def _get_current_env() -> dict[str, str]:
    # It is important to copy the environment dict, since we don't
    # want it to be modified when the env itself is modified
    return dict(os.environ)


def _set_current_env(env: Mapping[str, str]) -> None:
    os.environ.clear()
    os.environ.update(env)


def _sanitize_env(env: Mapping[str, str]) -> dict[str, str]:
    env = dict(env)
    keys_to_pop = {
        key
        for key in env
        if key in _ENV_VARS_TO_REMOVE_ON_SANITIZE
        or any(key.startswith(prefix) for prefix in _ENV_VAR_PREFIXES_TO_REMOVE_ON_SANITIZE)
    }
    for key in keys_to_pop:
        env.pop(key, None)
    return env


def _resolve_env_to_patch(
    env: Mapping[str, str],
    inherit: bool,
    to_inherit: Mapping[str, str],
) -> dict[str, str]:
    new_env = {**(to_inherit if inherit else {}), **env}
    sanitized_new_env = _sanitize_env(new_env)
    return sanitized_new_env


@contextmanager
def _patch_current_env(env: Mapping[str, str], inherit: bool) -> Generator[None]:
    snapshot = _get_current_env()
    new_env = _resolve_env_to_patch(env, inherit, snapshot)
    try:
        _set_current_env(new_env)
        yield
    finally:
        _set_current_env(snapshot)


@contextmanager
def _patch_popen_env(env: Mapping[str, str], inherit: bool) -> Generator[None]:
    snapshot = _get_current_env()
    new_env = _resolve_env_to_patch(env, inherit, snapshot)

    original_popen = subprocess.Popen

    def _patched_popen(*args: Any, **kwargs: Any) -> subprocess.Popen:
        if "env" not in kwargs:
            kwargs["env"] = new_env
        proc = original_popen(*args, **kwargs)
        return proc

    if original_popen.__name__ == _patched_popen.__name__:
        yield  # TODO: Properly support nested patching of Popen
    else:
        with unittest.mock.patch(
            original_popen.__module__ + "." + original_popen.__name__,
            _patched_popen,
        ):
            yield


type _EnvPatcher = Callable[[Mapping[str, str], bool], Generator[None]]
_ENV_PATCHERS = cast("list[_EnvPatcher]", [_patch_current_env, _patch_popen_env])


@contextmanager
def _run_env_patchers(
    env: Mapping[str, str],
    inherit: bool,
    patchers: Sequence[_EnvPatcher] | None = None,
) -> Generator[None]:
    if patchers is None:
        patchers = _ENV_PATCHERS

    if len(patchers) == 0:
        yield
    else:
        patchers = list(patchers)
        patcher = patchers.pop(0)
        with patcher(env, inherit), _run_env_patchers(env, inherit, patchers):  # ty: ignore[invalid-context-manager]
            yield


@contextmanager
def patch_env(env: Mapping[str, str], inherit: bool) -> Generator[None]:
    """
    Patch the current environment with the given environment.

    Args:
        env (Mapping[str, str]): Environment mapping, describing the new environment.
        inherit (bool): Whether to inherit the current environment and apply the new env on top of it.
    """
    with _run_env_patchers(env, inherit):
        yield

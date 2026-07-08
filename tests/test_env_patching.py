import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import IO, Literal, cast

import pytest
from pydantic import BaseModel, ConfigDict

from pytester_utils._env_patching import _patch_current_env, _patch_popen_env, _sanitize_env, patch_env


def _get_current_env() -> dict[str, str]:
    return dict(os.environ)


def _get_popen_env() -> dict[str, str]:
    proc = subprocess.Popen(
        args=[sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        stdout=subprocess.PIPE,
        text=True,
    )
    raw_env = cast("IO[str]", proc.stdout).read()
    env = json.loads(raw_env)
    return env


class EnvPatchMethod(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    patch_env: Callable[[Mapping[str, str], bool], AbstractContextManager[None]]
    get_envs: tuple[Callable[[], dict[str, str]], ...]


def _assert_env(
    stage: Literal["before patch", "during patch", "after patch"],
    method: str,
    original_env: Mapping[str, str],
    expected_env: Mapping[str, str],
    got_env: Mapping[str, str],
) -> None:
    original_env = _sanitize_env(original_env)
    expected_env = _sanitize_env(expected_env)
    got_env = _sanitize_env(got_env)

    assert original_env == expected_env, f"Original {method} environment was modified {stage}, this is unintended"
    assert got_env == expected_env, f"Got unexpected {method} environment variable values {stage}"


@pytest.mark.parametrize(
    "method",
    [
        pytest.param(
            EnvPatchMethod(name="current", patch_env=_patch_current_env, get_envs=(_get_current_env,)), id="current",
        ),
        pytest.param(EnvPatchMethod(name="popen", patch_env=_patch_popen_env, get_envs=(_get_popen_env,)), id="popen"),
        pytest.param(
            EnvPatchMethod(name="full", patch_env=patch_env, get_envs=(_get_current_env, _get_popen_env)), id="full",
        ),
    ],
)
@pytest.mark.parametrize("inherit", [False, True], ids=lambda inherit: f"{inherit=}")
def test_patch_env(method: EnvPatchMethod, inherit: bool) -> None:
    initial_env = dict(os.environ)
    patched_env = {**(os.environ if inherit else {}), "SOME_ENV_VAR": "SOME_ENV_VALUE"}

    # Keep pristine copies so that _assert_env can detect the patch mutating its input in place.
    expected_initial_env = dict(initial_env)
    expected_patched_env = dict(patched_env)

    for get_env in method.get_envs:
        _assert_env("before patch", method.name, initial_env, expected_initial_env, get_env())

    with method.patch_env(patched_env, inherit):
        for get_env in method.get_envs:
            _assert_env("during patch", method.name, patched_env, expected_patched_env, get_env())

    for get_env in method.get_envs:
        _assert_env("after patch", method.name, initial_env, expected_initial_env, get_env())

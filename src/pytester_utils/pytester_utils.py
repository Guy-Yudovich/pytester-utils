from __future__ import annotations

import re
from abc import abstractmethod
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol, Self, overload

import pytest
from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, computed_field, model_validator, validate_call

from pytester_utils._ast_utils import get_function_body_source_lines
from pytester_utils._env_patching import patch_env
from pytester_utils._plugin import (
    PYTESTER_RUN_METHOD_CLI_FLAG,
    PytesterRunMethod,
    get_default_pytester_run_method,
    get_request,
)
from pytester_utils.errors import DuplicateSpecialFilesError

type RawFileFunction = Callable[..., Any]
"""Raw Python function that can be converted into a Python file."""

type AnyFileFunction = FileFunction | RawFileFunction
"""Any function that can be converted into a Python file."""


class _DefaultParams(BaseModel):
    pytest_args: list[str] = Field(default_factory=lambda: ["-l", *(["-v"] * 3), "-rA", "--log-cli-level=INFO"])
    env_vars: dict[str, str] = Field(default_factory=dict)


_default_params = _DefaultParams()


def get_default_pytest_args() -> list[str]:
    """Get a copy of the default pytest arguments used for running nested pytest sessions."""
    return list(_default_params.pytest_args)


def get_default_env() -> dict[str, str]:
    """Get a copy of the default environment variables used for running nested pytest sessions."""
    return dict(_default_params.env_vars)


def set_default_pytest_args(pytest_args: Sequence[str]) -> None:
    """Set the default pytest arguments used for running nested pytest sessions."""
    _default_params.pytest_args = list(pytest_args)


def set_default_env(env_vars: Mapping[str, str]) -> None:
    """Set the default environment variables used for running nested pytest sessions."""
    _default_params.env_vars = dict(env_vars)


def _assert_pytester_exit_code(
    result: pytest.RunResult,
    assert_exit_code: pytest.ExitCode | None,
) -> None:
    if assert_exit_code is None:
        return

    assert result.ret == assert_exit_code, (
        f"Expected pytest exit code to be {assert_exit_code}, but got {result.ret}. "
        "See result.stdout and result.stderr for more details."
    )


def _assert_pytester_outcomes(
    result: pytest.RunResult,
    assert_outcomes: PytesterOutcomes | None,
) -> None:
    if assert_outcomes is None:
        return

    assert_kwargs = assert_outcomes.model_dump(
        exclude_defaults=True,
        exclude_none=True,
        exclude={"custom_outcomes"},
    )
    if len(assert_kwargs) > 0:
        result.assert_outcomes(**assert_kwargs)

    if len(assert_outcomes.custom_outcomes) > 0:
        other_result_outcomes = {
            outcome: amount
            for outcome, amount in result.parseoutcomes().items()
            if outcome not in PytesterOutcomes.model_fields
        }
        assert assert_outcomes.custom_outcomes == other_result_outcomes, (
            "Unexpected pytest outcomes. See result.stdout and result.stderr for more details."
        )


def _assert_pytester_output(
    line_matcher: pytest.LineMatcher,
    match_patterns: OutputMatchPatterns | None,
) -> None:
    if match_patterns is None:
        return

    if match_patterns.line_match_method == "regex":
        match_lines = line_matcher.re_match_lines
    elif match_patterns.line_match_method == "glob":
        match_lines = line_matcher.fnmatch_lines

    for pattern_sequence in match_patterns.match_patterns:
        if isinstance(pattern_sequence, Sequence) and not isinstance(pattern_sequence, str):
            consecutive = True
            actual_pattern_sequence = pattern_sequence
        else:
            consecutive = False
            actual_pattern_sequence = [pattern_sequence]

        match_lines(actual_pattern_sequence, consecutive=consecutive)


def _assert_pytester_result(
    result: pytest.RunResult,
    assert_exit_code: pytest.ExitCode | None,
    assert_outcomes: PytesterOutcomes | None,
    match_stdout_patterns: OutputMatchPatterns | None,
    match_stderr_patterns: OutputMatchPatterns | None,
) -> None:
    try:
        _assert_pytester_exit_code(result, assert_exit_code)
        _assert_pytester_outcomes(result, assert_outcomes)
        _assert_pytester_output(result.stdout, match_stdout_patterns)
        _assert_pytester_output(result.stderr, match_stderr_patterns)
    except ValueError as e:
        for arg in e.args:
            if not isinstance(arg, str):
                continue
            message = arg.lower()
            if all((segment in message) for segment in ["terminal summary", "not found"]):
                msg = (
                    "Pytest failed to capture terminal summary. This might be caused when running "
                    "pytester without the `-s` flag with pytester run method set to `inprocess`."
                )
                raise RuntimeError(msg) from e
        raise


def _resolve_file_function(file_function: AnyFileFunction) -> FileFunction:
    if isinstance(file_function, FileFunction):
        return file_function

    return FileFunction(func=file_function)


def _resolve_pytester_method(
    pytester: pytest.Pytester,
    pytester_run_method: PytesterRunMethod,
) -> _PytesterRunProtocol:
    run_pytest_methods = {
        "inprocess": pytester.runpytest_inprocess,
        "subprocess": pytester.runpytest_subprocess,
    }
    run_pytest_method = run_pytest_methods[pytester_run_method]
    return run_pytest_method


class _PytesterRunProtocol(Protocol):
    @abstractmethod
    def __call__(self, *args: str) -> pytest.RunResult: ...


class PytesterOutcomes(BaseModel):
    """Represents the expected outcomes of a pytest run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: NonNegativeInt | None = None
    skipped: NonNegativeInt | None = None
    failed: NonNegativeInt | None = None
    errors: NonNegativeInt | None = None
    xpassed: NonNegativeInt | None = None
    xfailed: NonNegativeInt | None = None
    warnings: NonNegativeInt | None = None
    deselected: NonNegativeInt | None = None
    custom_outcomes: dict[str, NonNegativeInt] = Field(default_factory=dict)


class OutputMatchPatterns(BaseModel):
    """Represents a list of patterns to match against the output of a pytest run, along with the matching method."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    match_patterns: list[Sequence[str | re.Pattern[str]] | str | re.Pattern[str]]
    line_match_method: Literal["regex", "glob"]

    @overload
    def __init__(
        self,
        *match_patterns: Sequence[str | re.Pattern[str]] | str | re.Pattern[str],
        line_match_method: Literal["regex"] = "regex",
    ) -> None: ...

    @overload
    def __init__(
        self,
        *match_patterns: Sequence[str] | str,
        line_match_method: Literal["glob"],
    ) -> None: ...

    def __init__(
        self,
        *match_patterns: Sequence[str | re.Pattern[str]] | str | re.Pattern[str],
        line_match_method: Literal["regex", "glob"] = "regex",
    ) -> None:
        """
        Patterns used for matching against stdout or stderr of the nested pytest session.

        Patterns can be either all regex or all glob patterns.

        Instead of a single pattern, it is possible to pass a sequence
        of patterns to be matched for consecutive matching.
        """
        super().__init__(
            match_patterns=match_patterns,
            line_match_method=line_match_method,
        )


class _FileFunctionMetadata(BaseModel):
    """
    Builder class for the class `FileFunction`.

    Finalize building by decorating a file function with an instance of this class.
    """

    model_config = ConfigDict(extra="forbid")

    injected_variables: dict[str, Any] = Field(default_factory=dict)
    auto_inject_imports: bool = True

    def __call__(self, func: RawFileFunction) -> FileFunction:
        return FileFunction(
            func=func,
            injected_variables=self.injected_variables,
            auto_inject_imports=self.auto_inject_imports,
        )

    @overload
    def inject(self, /, **variables_kwargs: Any) -> Self: ...

    @overload
    def inject(self, variables_dict: dict[str, Any], /) -> Self: ...

    def inject(self, variables_dict: dict[str, Any] | None = None, /, **variables_kwargs: Any) -> Self:
        """
        Inject variables into the file function.

        When generating a file based on a file function, a variable is injected only
        if there is an argument in the file function's signature with the same name.
        """
        self.injected_variables.update(variables_dict or {})
        self.injected_variables.update(variables_kwargs)
        return self


class FileFunction(_FileFunctionMetadata):
    """
    Container for attaching metadata to a function that can be converted into a Python file.

    Can be initialized either via the `__init__`, or via the `FileFunction.build()` method.
    For simplicity, it is advised to use the builder, as it can be used as a decorator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    func: RawFileFunction

    __call__ = None

    @classmethod
    def build(cls) -> _FileFunctionMetadata:
        """
        Initialize a builder for the class `FileFunction`.

        Finalize building by decorating a file function with an instance of the returned builder.
        """
        return _FileFunctionMetadata()


class TestFiles(BaseModel):
    """Represents a collection of test files, extra files, and special files to be used in a pytester session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conftest: AnyFileFunction | None = None
    """Optional `conftest.py` file to add alongside the test files."""

    test_files: Sequence[AnyFileFunction]
    """Files containing test cases, to be run inside pytest session(s)."""

    extra_files: Mapping[str, AnyFileFunction] = Field(default_factory=dict)
    """Files without any test cases, useful for utilities."""

    # Pytest tried to collect the class as a test class when imported
    # by a test module. This variable tells pytest it doesn't contain
    # tests even though it has the "Test" prefix in the name.
    __test__ = False

    @model_validator(mode="after")
    def _validate_special_files(self) -> Self:
        duplicate_file_names: list[str] = [
            name
            for name, field in {
                "conftest": self.conftest,
            }.items()
            if field is not None and name in self.extra_files
        ]

        if len(duplicate_file_names) > 0:
            raise DuplicateSpecialFilesError(duplicate_file_names)

        return self

    @computed_field
    @property
    def special_files(self) -> dict[str, AnyFileFunction]:
        return {
            name: file
            for name, file in {
                "__init__": self.extra_files.get("__init__"),
                "conftest": self.conftest or self.extra_files.get("conftest"),
            }.items()
            if file is not None
        }

    @computed_field
    @property
    def all_non_test_files(self) -> dict[str, AnyFileFunction]:
        return {
            **self.extra_files,
            **self.special_files,
        }

    @overload
    def make_pytester_tmp_files(self, pytester: pytest.Pytester) -> list[str]: ...

    @overload
    def make_pytester_tmp_files(self, pytester: pytest.Pytester, tests_dir_name: str) -> Path: ...

    def make_pytester_tmp_files(
        self,
        pytester: pytest.Pytester,
        tests_dir_name: str | None = None,
    ) -> list[str] | Path:
        """
        Register the files into the pytester session using `pytester.makepyfile(...)`.

        Return the list of paths of the test files, which should be passed to pytester's run method.
        When `tests_dir_name` is provided, return its created path instead.

        Optionally specify a directory name to create for containing
        the test files (excluding special files and extra files).
        """
        tests_dir_name = tests_dir_name.strip() if tests_dir_name is not None else ""
        test_file_name_prefix = ""
        tests_dir_path: Path | None = None
        if len(tests_dir_name) > 0:
            test_file_name_prefix = f"{tests_dir_name}/"
            tests_dir_path = pytester.mkpydir(tests_dir_name)

        for extra_file_name, extra_file_function in self.all_non_test_files.items():
            file_function = _resolve_file_function(extra_file_function)
            pytester.makepyfile(
                **{
                    extra_file_name: get_function_body_source_lines(
                        file_function.func,
                        file_function.injected_variables,
                        file_function.auto_inject_imports,
                    ),
                },
            )

        test_file_paths: list[str] = []
        for test_file_function in self.test_files:
            file_function = _resolve_file_function(test_file_function)
            test_file_name = f"{test_file_name_prefix}{file_function.func.__name__}"  # ty: ignore[unresolved-attribute]
            test_file_path = pytester.makepyfile(
                **{
                    test_file_name: get_function_body_source_lines(
                        file_function.func,
                        file_function.injected_variables,
                        file_function.auto_inject_imports,
                    ),
                },
            )
            test_path_str = str(test_file_path.absolute())
            test_file_paths.append(test_path_str)

        if tests_dir_path is not None:
            return tests_dir_path
        return test_file_paths


class PytesterTestCase(BaseModel):
    """Represents a test case to be run in a pytester session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_files: TestFiles
    """Files to be created in the pytester sessions."""

    pytest_args: list[str] = Field(default_factory=list)
    """Command line arguments to pass to the nested pytest session."""

    include_default_pytest_args: bool = True
    """
    Whether to pass the default command line arguments to the nested pytest session.

    Can be combined with `pytest_args` to pass additional arguments.

    The default pytest arguments can be modified via `set_default_pytest_args(...)` and `get_default_pytest_args(...)`.
    """

    env: dict[str, str] = Field(default_factory=dict)
    """
    Environment variables to pass to the nested pytest session, optionally overriding the default environment variables.

    Explicitly set environment variables take priority over default
    environment variables. Both default and explicit environment
    variables take priority over inherited environment variables.
    """

    include_default_env: bool = True
    """
    Whether to pass the default environment variables to the nested pytest session.

    Can be combined with `env` to pass additional environment variables.

    The default environment variables can be modified via `set_default_env(...)` and `get_default_env(...)`.

    Explicitly set environment variables take priority over default
    environment variables. Both default and explicit environment
    variables take priority over inherited environment variables.
    """

    inherit_env: bool = True
    """
    Whether to pass the environment variables of the invoking process to the nested pytest session.

    Can be combined with `env` to pass additional arguments

    Explicitly set environment variables take priority over default
    environment variables. Both default and explicit environment
    variables take priority over inherited environment variables.
    """

    pytester_run_method: PytesterRunMethod | None = None
    """
    Desired method for running pytester.

    Default value for the argument `pytester_run_method` can be set via the
    cli flag `--pytester-run-method`. When not defined, an environment variable
    `PYTESTER_RUN_METHOD` can be used to set the default value. When neither is
    defined, the default value is `subprocess`.
    """

    assert_exit_code: pytest.ExitCode | None = pytest.ExitCode.OK
    """Expected exit code used for asserting against the exit code of the nested pytest session's exit code."""

    assert_outcomes: PytesterOutcomes | None = None
    """Expected outcomes used for asserting against the nested pytest session's outcomes."""

    match_stdout_patterns: OutputMatchPatterns | None = None
    """Expected patterns used for matching against the nested pytest session's stdout."""

    match_stderr_patterns: OutputMatchPatterns | None = None
    """Expected patterns used for matching against the nested pytest session's stderr."""

    def run(self) -> PytesterTestCaseResult:
        request = get_request()
        result = _run_test_function(self, request)
        return result


class PytesterTestCaseResult(BaseModel):
    """Represents the result of running a `PytesterTestCase`."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    test_case: PytesterTestCase
    """The test case that was run."""

    run_result: pytest.RunResult
    """The result of running the test case."""


def _run_test_function(test_case: PytesterTestCase, request: pytest.FixtureRequest) -> PytesterTestCaseResult:
    pytester = request.getfixturevalue("pytester")

    pytest_args = [
        *(_default_params.pytest_args if test_case.include_default_pytest_args else []),
        *test_case.pytest_args,
    ]
    env = {
        **(_default_params.env_vars if test_case.include_default_env else {}),
        **test_case.env,
    }

    run_result = run_pytester(
        config=request.config,
        pytester=pytester,
        pytester_run_method=test_case.pytester_run_method,
        test_files=test_case.test_files,
        pytest_args=pytest_args,
        env=env,
        inherit_env=test_case.inherit_env,
    )

    _assert_pytester_result(
        result=run_result,
        assert_exit_code=test_case.assert_exit_code,
        assert_outcomes=test_case.assert_outcomes,
        match_stdout_patterns=test_case.match_stdout_patterns,
        match_stderr_patterns=test_case.match_stderr_patterns,
    )

    return PytesterTestCaseResult(
        test_case=test_case,
        run_result=run_result,
    )


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def run_pytester(  # noqa: PLR0913 - too-many-arguments
    *,
    config: pytest.Config,
    pytester: pytest.Pytester,
    pytester_run_method: PytesterRunMethod | None = None,
    test_files: TestFiles,
    pytest_args: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    inherit_env: bool = True,
) -> pytest.RunResult:
    """
    Run pytester with the given files and args.

    Default value for the argument `pytester_run_method` can be set via the
    cli flag `--pytester-run-method`. When not defined, an environment variable
    `PYTESTER_RUN_METHOD` can be used to set the default value. When neither is
    defined, the default value is `subprocess`.

    Args:
        config (pytest.Config): Config object from the pytest session.
        pytester (pytest.Pytester): Fixture for running pytester, obtained from the pytest session.
        test_files (TestFiles): Files to be created in the pytester sessions.
        pytester_run_method (PytesterRunMethod | None, optional): Desired method for running pytester.
        pytest_args (Sequence[str] | None, optional): Command line arguments to pass to the nested pytest session.
        env (Mapping[str, str] | None, optional): Environment variables to pass to the nested pytest
            session, optionally overriding the default environment variables.
        inherit_env (bool, optional): Whether to pass the environment variables of the invoking
            process to the nested pytest session.

    Returns:
        pytest.RunResult: The result of running the nested pytest session.
    """
    pytest_args = list(pytest_args or [])
    env = dict(env or {})

    pytester_run_method = pytester_run_method or get_default_pytester_run_method(config)
    pytester_run_method_flag = (PYTESTER_RUN_METHOD_CLI_FLAG, pytester_run_method)
    run_pytest = _resolve_pytester_method(pytester, pytester_run_method)

    test_file_paths = test_files.make_pytester_tmp_files(pytester)
    with patch_env(env, inherit_env):
        run_result = run_pytest(*test_file_paths, *pytest_args, *pytester_run_method_flag)
    return run_result

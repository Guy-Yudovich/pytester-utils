import ast
import inspect
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from pytester_utils._ast_utils import (
    _build_assign_statements,
    _create_variable_injection_lines,
    _get_function_def,
    _verify_valid_function,
    get_function_body_source_lines,
)
from pytester_utils.errors import (
    ArgumentWithDefaultValueError,
    MissingInjectionVariablesError,
    UnusedInjectedVariablesWarning,
)


def dummy_function() -> None:
    pass


def unparse_ast_nodes(nodes: Sequence[ast.AST]) -> list[str]:
    return [ast.unparse(node) for node in nodes]


class AssignmentTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, arbitrary_types_allowed=True)

    variables: dict[str, Any]
    expected_statements: list[ast.Assign]
    expected_unparsed_code: list[str]


@pytest.fixture(
    params=[
        pytest.param(
            AssignmentTestCase(
                variables={},
                expected_statements=[],
                expected_unparsed_code=[],
            ),
            id="no variables",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"a": 42},
                expected_statements=[ast.Assign(targets=[ast.Name("a")], value=ast.Constant(42), lineno=1)],
                expected_unparsed_code=["a = 42"],
            ),
            id="single integer variable",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"name": "hello"},
                expected_statements=[ast.Assign(targets=[ast.Name("name")], value=ast.Constant("hello"), lineno=1)],
                expected_unparsed_code=["name = 'hello'"],
            ),
            id="single string variable",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"flag": True},
                expected_statements=[ast.Assign(targets=[ast.Name("flag")], value=ast.Constant(True), lineno=1)],
                expected_unparsed_code=["flag = True"],
            ),
            id="single boolean variable",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"value": None},
                expected_statements=[ast.Assign(targets=[ast.Name("value")], value=ast.Constant(None), lineno=1)],
                expected_unparsed_code=["value = None"],
            ),
            id="single none variable",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"pi": 3.14},
                expected_statements=[ast.Assign(targets=[ast.Name("pi")], value=ast.Constant(3.14), lineno=1)],
                expected_unparsed_code=["pi = 3.14"],
            ),
            id="single float variable",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"a": 1, "b": 2},
                expected_statements=[
                    ast.Assign(targets=[ast.Name("a")], value=ast.Constant(1), lineno=1),
                    ast.Assign(targets=[ast.Name("b")], value=ast.Constant(2), lineno=1),
                ],
                expected_unparsed_code=["a = 1", "b = 2"],
            ),
            id="multiple variables",
        ),
        pytest.param(
            AssignmentTestCase(
                variables={"func": dummy_function},
                expected_statements=[
                    ast.Assign(targets=[ast.Name("func")], value=ast.Name(dummy_function.__name__), lineno=1),
                ],
                expected_unparsed_code=[f"func = {dummy_function.__name__}"],
            ),
            id="function as variable",
        ),
    ],
)
def assignment_test_case(request: pytest.FixtureRequest) -> AssignmentTestCase:
    return request.param


def test_build_assign_statements(assignment_test_case: AssignmentTestCase) -> None:
    result = _build_assign_statements(assignment_test_case.variables)
    assert unparse_ast_nodes(result) == unparse_ast_nodes(assignment_test_case.expected_statements), (
        "Got unexpected assignment statements"
    )


def test_create_variable_injection_lines(assignment_test_case: AssignmentTestCase) -> None:
    result = _create_variable_injection_lines(assignment_test_case.variables)
    assert result == assignment_test_case.expected_unparsed_code, "Got unexpected assignment code"


def function_for_get_function_def(a: int, b: str) -> str:
    return f"{a}:{b}"


def function_for_get_function_def_no_args() -> None:
    pass


@pytest.mark.parametrize(
    ("func", "expected_name", "expected_args"),
    [
        pytest.param(
            function_for_get_function_def,
            "function_for_get_function_def",
            ["a", "b"],
            id="two_args",
        ),
        pytest.param(
            function_for_get_function_def_no_args,
            "function_for_get_function_def_no_args",
            [],
            id="no_args",
        ),
    ],
)
def test_get_function_def(func: Callable[..., Any], expected_name: str, expected_args: list[str]) -> None:
    result = _get_function_def(func)

    assert isinstance(result, ast.FunctionDef)
    assert result.name == expected_name
    assert [arg.arg for arg in result.args.args] == expected_args


def function_with_no_default(a: int, b: int) -> int:
    c = a + b
    return c


def function_with_default(a: int, b: int = 1) -> int:
    c = a + b
    return c


@pytest.mark.parametrize(
    ("func", "variables", "expected_warning", "expected_exception"),
    [
        pytest.param(function_with_no_default, {"a": 1, "b": 2}, None, None, id="valid_no_default_args"),
        pytest.param(
            function_with_no_default,
            {"a": 1},
            None,
            MissingInjectionVariablesError,
            id="missing_injected_variables",
        ),
        pytest.param(
            function_with_no_default,
            {"a": 1, "b": 2, "ignored": 3},
            UnusedInjectedVariablesWarning,
            None,
            id="unused_injected_variables",
        ),
        pytest.param(
            function_with_default,
            {"a": 1, "b": 2},
            None,
            ArgumentWithDefaultValueError,
            id="invalid_default_arg",
        ),
    ],
)
def test_verify_valid_function(
    func: Callable[..., Any],
    variables: dict[str, Any],
    expected_warning: type[Warning] | None,
    expected_exception: type[Exception] | None,
) -> None:
    function_signature = inspect.signature(func)

    if expected_warning is not None:
        with pytest.warns(expected_warning):
            _verify_valid_function(function_signature, variables)
        return

    if expected_exception is None:
        _verify_valid_function(function_signature, variables)
        return

    with pytest.raises(expected_exception):
        _verify_valid_function(function_signature, variables)


def function_for_get_function_body_source_lines(a: int, b: int) -> int:
    c = a + b
    return c


def function_for_get_function_body_source_lines_with_default(a: int = 1) -> int:
    return a


@pytest.mark.parametrize(
    (
        "func",
        "variables",
        "auto_inject_imports",
        "expected_contains",
        "expected_not_contains",
        "expected_warning",
        "expected_exception",
    ),
    [
        pytest.param(
            function_for_get_function_body_source_lines,
            {"a": 2, "b": 3, "ignored": 999},
            False,
            ["a = 2", "b = 3", "c = a + b", "return c"],
            ["ignored = 999", "import ast"],
            UnusedInjectedVariablesWarning,
            None,
            id="without_auto_imports",
        ),
        pytest.param(
            function_for_get_function_body_source_lines,
            {"a": 2, "b": 3, "ignored": 999},
            True,
            ["import ast", "a = 2", "b = 3", "c = a + b", "return c"],
            ["ignored = 999"],
            UnusedInjectedVariablesWarning,
            None,
            id="with_auto_imports",
        ),
        pytest.param(
            function_for_get_function_body_source_lines,
            {"a": 2},
            False,
            [],
            [],
            None,
            MissingInjectionVariablesError,
            id="raises_for_unassigned_arg",
        ),
        pytest.param(
            function_for_get_function_body_source_lines_with_default,
            {"a": 2},
            False,
            [],
            [],
            None,
            ArgumentWithDefaultValueError,
            id="raises_for_default_arg",
        ),
    ],
)
def test_get_function_body_source_lines(  # noqa: PLR0913
    func: Callable[..., Any],
    variables: dict[str, Any],
    auto_inject_imports: bool,
    expected_contains: list[str],
    expected_not_contains: list[str],
    expected_warning: type[Warning] | None,
    expected_exception: type[Exception] | None,
) -> None:
    if expected_warning is not None:
        with pytest.warns(expected_warning):
            result = get_function_body_source_lines(
                func=func,
                variables=variables,
                auto_inject_imports=auto_inject_imports,
            )

        for line in expected_contains:
            assert line in result

        for line in expected_not_contains:
            assert line not in result
        return

    if expected_exception is not None:
        with pytest.raises(expected_exception):
            get_function_body_source_lines(
                func=func,
                variables=variables,
                auto_inject_imports=auto_inject_imports,
            )
        return

    result = get_function_body_source_lines(
        func=func,
        variables=variables,
        auto_inject_imports=auto_inject_imports,
    )

    for line in expected_contains:
        assert line in result

    for line in expected_not_contains:
        assert line not in result

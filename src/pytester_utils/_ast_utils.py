from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable, Mapping
from typing import Any, cast

from pytester_utils.errors import ArgumentWithDefaultValueError


def _build_assign_statements(variables: Mapping[str, Any]) -> list[ast.Assign]:
    variable_statements: list[ast.Assign] = []

    for variable, value in variables.items():
        if inspect.isfunction(value) or inspect.ismethod(value):
            assignment_value = ast.Name(value.__name__)
        else:
            assignment_value = ast.Constant(value)

        assign_statement = ast.Assign(
            targets=[ast.Name(variable)],
            value=assignment_value,
            lineno=1,
        )
        variable_statements.append(assign_statement)

    return variable_statements


def _create_variable_injection_lines(variables: Mapping[str, Any]) -> list[str]:
    if len(variables) == 0:
        return []

    variable_statements = _build_assign_statements(variables)
    lines = [ast.unparse(statement) for statement in variable_statements]
    return lines


def _get_function_def[**P, R](func: Callable[P, R]) -> ast.FunctionDef:
    source_lines = inspect.getsourcelines(func)[0]
    source = "\n".join(source_lines)
    source = textwrap.dedent(source)

    module = ast.parse(source)
    statements = module.body
    function_def: ast.FunctionDef | None = None
    for statement in statements:
        if isinstance(statement, ast.FunctionDef):
            function_def = statement
            break
    if function_def is None:
        # This is a runtime error because it should not be possible as we always take a func as an argument
        msg = "Failed to get ast function definition from function."
        raise RuntimeError(msg)
    return function_def


def _verify_valid_function[**P, R](func: Callable[P, R]) -> None:
    function_signature = inspect.signature(func)
    for param in function_signature.parameters.values():
        if param.default is not inspect.Parameter.empty:
            raise ArgumentWithDefaultValueError(str(param))


def _get_module_imports_from_function_def[**P, R](func: Callable[P, R]) -> list[str]:
    module = inspect.getmodule(func)
    if module is None:
        # This is a runtime error because it should not be possible as we always take a func as an argument
        msg = "Failed to get module from function."
        raise RuntimeError(msg)
    tree = ast.parse(inspect.getsource(module))

    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.unparse(node))

    return imports


def get_function_body_source_lines[**P, R](
    func: Callable[P, R],
    variables: Mapping[str, Any] | None = None,
    auto_inject_imports: bool = True,
) -> str:
    _verify_valid_function(func)
    function_signature = inspect.signature(func)
    variables = {
        variable: value for variable, value in (variables or {}).items() if variable in function_signature.parameters
    }

    function_def = _get_function_def(func)

    function_contents = ast.unparse(cast("ast.AST", function_def.body))
    function_contents = textwrap.dedent(function_contents)

    variable_injection_lines = _create_variable_injection_lines(variables)
    if len(variable_injection_lines) > 0:
        variable_injection_lines.append("")

    imports: list[str] = []
    if auto_inject_imports:
        imports = _get_module_imports_from_function_def(func)
        if len(imports) > 0:
            imports.append("")

    function_contents = "\n".join(
        [
            *imports,
            *variable_injection_lines,
            function_contents,
        ],
    )
    return function_contents

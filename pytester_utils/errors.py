from __future__ import annotations

from typing import Any


class InvalidFileFunctionError(SyntaxError):
    """Raised when a file function is invalid."""

    def __init__(self, reason: str, *args: Any) -> None:
        self.reason = reason
        super().__init__(f"Invalid file function: {reason}", *args)


class ArgumentWithDefaultValueError(InvalidFileFunctionError):
    """Raised when a file function has an argument with a default value, which is invalid for file functions."""

    def __init__(self, argument: str) -> None:
        self.argument = argument
        super().__init__(
            f"The function has an argument '{argument}' with a default value, which is invalid "
            "for file functions. Try using the `FileFunction.build(...)` decorator instead.",
        )


class FixtureRequestNotAvailableError(ValueError):
    """Raised when the fixture request is not available at a desired stage."""

    def __init__(self) -> None:
        super().__init__("Fixture request is not available at this stage.")


class DuplicateSpecialFilesError(ValueError):
    """Raised when special files are defined multiple times."""

    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__(
            f"The files {names!r} must be defined up to once each but were "
            "defined twice, once via their fields and once via extra_files.",
        )


class UnusedInjectedVariablesWarning(UserWarning):
    """Raised when extra variables are provided for function body injection."""

    def __init__(self, unused_variables: list[str]) -> None:
        self.unused_variables = unused_variables
        super().__init__(f"Unused variables were injected: {unused_variables!r}")


class MissingInjectionVariablesError(ValueError):
    """Raised when required function parameters were not provided in injected variables."""

    def __init__(self, missing_variables: list[str]) -> None:
        self.missing_variables = missing_variables
        super().__init__(f"Missing injection variables: {missing_variables!r}.")

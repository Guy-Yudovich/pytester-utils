from __future__ import annotations

from typing import Any


class InvalidFileFunctionError(SyntaxError):
    def __init__(self, reason: str, *args: Any) -> None:
        self.reason = reason
        super().__init__(f"Invalid file function: {reason}", *args)


class ArgumentWithDefaultValueError(InvalidFileFunctionError):
    def __init__(self, argument: str) -> None:
        self.argument = argument
        super().__init__(
            f"The function has an argument '{argument}' with a default value, which is invalid "
            "for file functions. Try using the `FileFunction.build(...)` decorator instead.",
        )


class FixtureRequestNotAvailableError(ValueError):
    def __init__(self) -> None:
        super().__init__("Fixture request is not available at this stage.")


class DuplicateSpecialFilesError(ValueError):
    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__(
            f"The files {names!r} must be defined up to once each but were "
            "defined twice, once via their fields and once via extra_files.",
        )

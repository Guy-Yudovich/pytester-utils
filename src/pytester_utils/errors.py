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

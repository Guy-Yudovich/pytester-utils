from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import FunctionType
from typing import Any, Self, overload, override

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from pytester_utils._ast_utils import get_function_body_source_lines
from pytester_utils.errors import NotConvertibleToTestFileError

type RawFileFunction = Callable[..., Any]
"""Raw Python function that can be converted into a Python file."""

type AnyTestFile = TestFile | RawFileFunction
"""Any object that can be converted into a Python file."""


class TestFile(ABC):
    __test__ = False

    @property
    @abstractmethod
    def metadata(self) -> TestFileMetadata: ...

    @property
    @abstractmethod
    def source_lines(self) -> str:
        """
        Get the source lines (or variants thereof) of the test file.

        Multi-line strings are returned as a single string with newline characters.
        """

    @classmethod
    def build(cls) -> TestFileBuilder:
        """Initialize a builder for the implementations of this class."""
        return TestFileBuilder()

    @staticmethod
    def from_any(obj: AnyTestFile) -> TestFile:
        """
        Convert any object that can be converted into a Python file into a `TestFile`.

        If the object is already a `TestFile`, it is returned as-is.
        If the object is a raw Python function, it is wrapped in a `FileFunction` with default metadata.
        """
        if isinstance(obj, TestFile):
            return obj
        if isinstance(obj, FunctionType):
            return FunctionTestFile(obj, TestFileMetadata(name=obj.__name__) if hasattr(obj, "__name__") else None)
        raise NotConvertibleToTestFileError(obj)

    @overload
    def inject(self, /, **variables_kwargs: Any) -> Self: ...

    @overload
    def inject(self, variables_dict: dict[str, Any], /) -> Self: ...

    def inject(self, variables_dict: dict[str, Any] | None = None, /, **variables_kwargs: Any) -> Self:
        """
        Inject variables into the test file.

        When generating a file based on a test file function, a variable is injected only
        if there is an argument in the test file function's signature with the same name.
        """
        self.metadata.injected_variables.update(variables_dict or {})
        self.metadata.injected_variables.update(variables_kwargs)
        return self


class TestFileMetadata(BaseModel):
    __test__ = False

    model_config = ConfigDict(extra="forbid")

    name: str = "test_unnamed"
    injected_variables: dict[str, Any] = Field(default_factory=dict)
    auto_inject_imports: bool = True


class FunctionTestFile(TestFile):
    """
    Container for attaching metadata to a function that can be converted into a Python file.

    For simplicity, it is advised to use the builder, as it can be used as a decorator.
    """

    def __init__(self, func: RawFileFunction, metadata: TestFileMetadata | None = None) -> None:
        self._func = func
        self._metadata = metadata or (
            TestFileMetadata(name=str(func.__name__)) if hasattr(func, "__name__") else TestFileMetadata()
        )

    @property
    def func(self) -> RawFileFunction:
        return self._func

    @property
    @override
    def metadata(self) -> TestFileMetadata:
        return self._metadata

    @property
    @override
    def source_lines(self) -> str:
        return get_function_body_source_lines(
            self._func,
            self._metadata.injected_variables,
            self._metadata.auto_inject_imports,
        )


class TestFileBuilder:
    """
    Builder class for the class `TestFile`.

    Finalize building by using one of the methods with the prefix "finalize".
    """

    __test__ = False

    def __init__(self) -> None:
        self._raw_metadata: dict[str, Any] = {}

    def finalize_from_raw(self) -> Callable[[RawFileFunction], TestFile]:
        """Finalize building by decorating a file function with the returned decorator."""

        def wrapper(func: RawFileFunction) -> TestFile:
            raw_metadata = self._raw_metadata.copy()
            if "name" not in raw_metadata and hasattr(func, "__name__"):
                raw_metadata["name"] = func.__name__
            metadata = TestFileMetadata.model_validate(raw_metadata)
            test_file = FunctionTestFile(func, metadata)
            return test_file

        return wrapper

    def set_name(self, name: str) -> Self:
        """Set the name of the test file."""
        self._raw_metadata["name"] = name
        return self

    @overload
    def inject(self, /, **variables_kwargs: Any) -> Self: ...

    @overload
    def inject(self, variables_dict: dict[str, Any], /) -> Self: ...

    def inject(self, variables_dict: dict[str, Any] | None = None, /, **variables_kwargs: Any) -> Self:
        """
        Inject variables into the test file.

        When generating a file based on a test file function, a variable is injected only
        if there is an argument in the test file function's signature with the same name.
        """
        injected_variables: dict[str, Any] = self._raw_metadata.setdefault("injected_variables", {})
        injected_variables.update(variables_dict or {})
        injected_variables.update(variables_kwargs)
        return self

    def set_auto_inject_imports(self, auto_inject_imports: bool) -> Self:
        """Set whether to automatically inject imports from the defining module."""
        self._raw_metadata["auto_inject_imports"] = auto_inject_imports
        return self

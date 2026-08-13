from unittest import mock  # IMPORTANT!

from pytester_utils import (
    FunctionTestFile,
    PytesterOutcomes,
    PytesterTestCase,
    TestFileMetadata,
    TestFiles,
    run_pytester,
)
from tests.system.utils import file_outer_conftest


def file_test_auto_imports() -> None:
    from pytester_utils import (  # noqa: PLC0415
        FunctionTestFile,
        PytesterOutcomes,
        PytesterTestCase,
        TestFileMetadata,
        TestFiles,
        run_pytester,
    )

    try:
        _ = mock.Mock()  # ty:ignore[unresolved-reference] # noqa: F823 - undefined-local
    except NameError:
        pass
    else:
        msg = "Expected NameError to be raised!"
        raise RuntimeError(msg)

    from unittest import mock  # noqa: PLC0415

    def file_test_1() -> None:
        def test_1() -> None:
            _ = mock.Mock()

    def file_test_2() -> None:
        def test_2() -> None:
            import pytest  # noqa: PLC0415

            with pytest.raises(NameError):
                _ = mock.Mock()

    def test_auto_imports_true() -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(test_files=[file_test_1]),
                assert_outcomes=PytesterOutcomes(passed=1),
            ),
        )

    def test_auto_imports_false() -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(
                    test_files=[
                        FunctionTestFile(func=file_test_2, metadata=TestFileMetadata(auto_inject_imports=False)),
                    ],
                ),
                assert_outcomes=PytesterOutcomes(passed=1),
            ),
        )


def test_auto_imports() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(
                conftest=file_outer_conftest,
                test_files=[
                    FunctionTestFile(func=file_test_auto_imports, metadata=TestFileMetadata(auto_inject_imports=False)),
                ],
            ),
            assert_outcomes=PytesterOutcomes(passed=2),
        ),
    )

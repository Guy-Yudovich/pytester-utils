from pytester_utils import PytesterTestCase, TestFiles, run_pytester
from tests.system.utils import file_outer_conftest


def file_test_pytester_utils_sanity() -> None:
    def file_test_inside_pytester_utils() -> None:
        def test_sanity() -> None:
            pass

    def test_sanity() -> None:
        run_pytester(PytesterTestCase(test_files=file_test_inside_pytester_utils))


def test_sanity() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(
                conftest=file_outer_conftest,
                test_files=[file_test_pytester_utils_sanity],
            ),
        ),
    )

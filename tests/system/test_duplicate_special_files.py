import pytest
from pydantic import ValidationError

from pytester_utils import OutputMatchPatterns, PytesterOutcomes, PytesterTestCase, TestFiles, run_pytester
from tests.system.utils import file_outer_conftest


def file_test_duplicate_special_files() -> None:
    def file_inner_conftest() -> None:
        pass

    def file_test_inside() -> None:
        def test() -> None:
            pass

    def test_inside() -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(
                    test_files=[file_test_inside],
                    conftest=file_inner_conftest,
                    extra_files={"conftest": file_inner_conftest},
                ),
            ),
        )


def test_duplicate_special_files() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(conftest=file_outer_conftest, test_files=[file_test_duplicate_special_files]),
            assert_exit_code=pytest.ExitCode.TESTS_FAILED,
            assert_outcomes=PytesterOutcomes(failed=1),
            match_stdout_patterns=OutputMatchPatterns(f"*{ValidationError.__qualname__}*", line_match_method="glob"),
        ),
    )

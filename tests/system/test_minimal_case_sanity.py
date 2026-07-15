import pytest

from pytester_utils import PytesterOutcomes, PytesterTestCase, TestFiles, run_pytester
from tests.system.utils import file_outer_conftest


def file_pytester() -> None:
    def file_test_1() -> None:
        def test_1() -> None:
            pass

    def test_sanity() -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(test_files=[file_test_1]),
                assert_outcomes=PytesterOutcomes(passed=1),
            ),
        )

    @pytest.mark.parametrize(
        "case",
        [
            PytesterTestCase(
                test_files=TestFiles(test_files=[file_test_1]), assert_outcomes=PytesterOutcomes(passed=1)
            ),
        ],
    )
    def test_sanity_parametrized(case: PytesterTestCase) -> None:
        run_pytester(case)


def test_sanity() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(conftest=file_outer_conftest, test_files=[file_pytester]),
            assert_outcomes=PytesterOutcomes(passed=2),
        )
    )

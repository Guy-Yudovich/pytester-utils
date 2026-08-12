import os
from typing import cast

import pytest

from pytester_utils import PytesterTestCase, TestFile, TestFiles, run_pytester
from tests.system.utils import file_outer_conftest


def file_test_parametrized_variable_injection() -> None:
    test_value_key = "test_value"

    @pytest.fixture(params=["a", "b"])
    def test_value(request: pytest.FixtureRequest) -> str:
        test_value = cast("str", request.param)
        os.environ[test_value_key] = test_value
        return test_value

    @(
        TestFile.build()
        .inject(
            test_value_key=test_value_key,
        )
        .finalize_from_raw()
    )
    def _file_test_1(
        test_value_key: str,
        test_value: str,
    ) -> None:
        def test_sanity() -> None:
            assert test_value == os.environ.get(test_value_key)

    @pytest.fixture
    def file_test_1(test_value: str) -> TestFile:
        _file_test_1.inject({test_value_key: test_value})
        return _file_test_1

    def test_sanity(file_test_1: TestFile) -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(
                    test_files=[file_test_1],
                ),
            ),
        )


def test_parametrized_variable_injection() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(
                conftest=file_outer_conftest,
                test_files=[file_test_parametrized_variable_injection],
            ),
        ),
    )

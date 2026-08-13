from pytester_utils import PytesterTestCase, TestFile, TestFiles, run_pytester
from tests.system.utils import file_outer_conftest


def file_test_simple_variable_injection() -> None:
    my_const = "my_value"
    my_array_const = [1, b"2", "hello"]
    my_complex_array_const = [*my_array_const, my_array_const]

    @(
        TestFile.build()
        .inject(
            my_const=my_const,
            my_array_const=my_array_const,
            my_complex_array_const=my_complex_array_const,
        )
        .finalize_from_raw()
    )
    def file_test_1(
        my_const: str,
        my_array_const: list[int | bytes | str],
        my_complex_array_const: list[int | bytes | str | list[int | bytes | str]],
    ) -> None:
        def test_sanity() -> None:
            assert my_const == "my_value"
            assert my_array_const == [1, b"2", "hello"]
            assert my_complex_array_const == [1, b"2", "hello", [1, b"2", "hello"]]

    def test_sanity() -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(
                    test_files=[file_test_1],
                ),
            ),
        )


def test_simple_variable_injection() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(
                conftest=file_outer_conftest,
                test_files=[file_test_simple_variable_injection],
            ),
        ),
    )

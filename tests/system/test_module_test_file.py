from pathlib import Path

from pytester_utils import FunctionTestFile, PytesterTestCase, TestFiles, run_pytester
from pytester_utils.test_file import ModuleTestFile
from tests.system.utils import file_outer_conftest


def file_test_pytester_utils_sanity() -> None:
    def file_test_inside_pytester_utils_1() -> None:
        def test_sanity() -> None:
            pass

    def file_test_inside_pytester_utils_2() -> None:
        def test_sanity() -> None:
            assert a == 2, "Failed to inject variable 'a' into the test file."  # noqa: F821, PLR2004 # ty: ignore[unresolved-reference]

    def test_sanity(tmp_path: Path) -> None:
        tmp_path.mkdir(parents=True, exist_ok=True)

        tmp_file_1 = tmp_path / "file_test_pytester_utils_sanity_1.py"
        tmp_file_1.write_text(FunctionTestFile(file_test_inside_pytester_utils_1).source_lines)

        tmp_file_2 = tmp_path / "file_test_pytester_utils_sanity_2.py"
        tmp_file_2.write_text(FunctionTestFile(file_test_inside_pytester_utils_2).source_lines)

        test_file_2 = ModuleTestFile.build().inject(a=2).finalize_from_module(tmp_file_2)
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(
                    conftest=file_outer_conftest,
                    test_files=[tmp_file_1, test_file_2],
                ),
            ),
        )


def test_sanity() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(
                conftest=file_outer_conftest,
                test_files=[file_test_pytester_utils_sanity],
            ),
        ),
    )

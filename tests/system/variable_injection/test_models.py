from pytester_utils import FileFunction, PytesterTestCase, TestFiles, run_pytester
from tests.system.mocks import ComplexMockModel, SimpleMockModel
from tests.system.utils import file_outer_conftest


def file_test_model_variable_injection() -> None:
    my_complex_model = ComplexMockModel(
        simples_list=[
            SimpleMockModel(name="model-1", value=1, extras={"hi": 1, "bye": 2}),
            SimpleMockModel(name="model-2", value=2, extras={"hi": 2, "bye": 3}),
            SimpleMockModel(name="model-3", value=3, extras={"hi": 3, "bye": 4}),
        ],
        simples_mapping={
            "model-4": SimpleMockModel(name="model-4", value=4, extras={"hi": 4, "bye": 5}),
            "model-5": SimpleMockModel(name="model-5", value=5, extras={"hi": 5, "bye": 6}),
            "model-6": SimpleMockModel(name="model-6", value=6, extras={"hi": 6, "bye": 7}),
        },
    )

    @FileFunction.build().inject(
        my_complex_model=my_complex_model,
    )
    def file_test_1(my_complex_model: ComplexMockModel) -> None:
        def test_sanity() -> None:
            assert my_complex_model == ComplexMockModel(
                simples_list=[
                    SimpleMockModel(name="model-1", value=1, extras={"hi": 1, "bye": 2}),
                    SimpleMockModel(name="model-2", value=2, extras={"hi": 2, "bye": 3}),
                    SimpleMockModel(name="model-3", value=3, extras={"hi": 3, "bye": 4}),
                ],
                simples_mapping={
                    "model-4": SimpleMockModel(name="model-4", value=4, extras={"hi": 4, "bye": 5}),
                    "model-5": SimpleMockModel(name="model-5", value=5, extras={"hi": 5, "bye": 6}),
                    "model-6": SimpleMockModel(name="model-6", value=6, extras={"hi": 6, "bye": 7}),
                },
            )

    def test_sanity() -> None:
        run_pytester(
            PytesterTestCase(
                test_files=TestFiles(
                    test_files=[file_test_1],
                ),
            ),
        )


def test_model_variable_injection() -> None:
    run_pytester(
        PytesterTestCase(
            test_files=TestFiles(
                conftest=file_outer_conftest,
                test_files=[file_test_model_variable_injection],
            ),
        ),
    )

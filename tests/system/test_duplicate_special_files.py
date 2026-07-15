def file_test_duplicate_special_files() -> None:
    def file_test_inside() -> None:
        def test() -> None:
            pass

    def test_inside() -> None:
        run_pytester()
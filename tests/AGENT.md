# Unit Testing Guidelines

## Test Structure
- Use `pytest.parametrize` decorator for testing multiple test cases with the same logic
- Apply parametrization only when testing a single logical branch with different inputs
- Avoid multiple asserts or separate test functions for the same behavior
- Test only public interfaces
- Use pytest `monkeypatch` fixture instead of `unittest.mock.patch`


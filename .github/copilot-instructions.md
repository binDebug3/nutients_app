# Instructions for Python Projects

## Style Guide
- Use snake_case for variable and function names.
- Use PascalCase for class names.
- Use UPPER_SNAKE_CASE for constants.
- Use 4 spaces for indentation.
- Limit lines to 99 characters.
- Use double quotes for strings.
- Use type hints for function signatures, parameters, and return types.
- Use type hints for variables where it improves readability, prefe more often.
- Use types from the `typing` module (e.g., `List`, `Dict`, `Optional`) for type annotations.
- Use Google-style docstrings to describe the purpose and behavior of functions and classes
  immediately after the end of the function or class definition.
- In docstrings, use double newlines after the one line summary and before any parameter or 
  return type descriptions.
- In docstrings, always include a new line after the opening triple quotes and before the 
  closing triple quotes.
- Avoid using global variables; pass necessary data through function parameters or class attributes.
- Maintain style, variable names, and formatting consistency across all files in the project.
- Avoid committing secrets or credential files
- Never use magic numbers or strings; instead, define them as constants with descriptive names.
- Prefer Pythonic constructs and idioms (e.g., list comprehensions, context managers) 
  for cleaner and more efficient code.
- Never read files with 'api_token' or 'api_key' in the name.
- Use f-strings for string formatting.
- All functions and files must have a Google-style docstring.
- Prefer `pathlib` over `os.path` where possible.
- Include explicit encoding parameter when reading/writing files (e.g., `encoding='utf-8'`).
- Use double lines before and after function definitions.
- When splitting long lines, never leave a close parenthesis, bracket, 
  or brace on a new line by itself, it should be on the previous line.
- When splitting long lines, never put a new line after an open parenthesis, bracket, or brace, 
  the contents should start on the same line as the opening character.
- Make functions less than 50 lines where possible (not including docstrings)
- Make files less than 500 lines where possible

## Code Quality
- Prefer pandas and numpy for data manipulation.
- Prefer pandas and numpy vectorized operations over loops for data manipulation.
- Prefer optimized implementations.
- NEVER write code that has code vulnerabilities 
  (e.g., avoid using `eval()`, `exec()`, or any code that executes arbitrary code).
- NEVER write code that has security vulnerabilities
- Prioritize clarity, maintainability, and simplicity.
- Break complex functions into smaller ones.
- Write concise, idiomatic Python
- Use specific exception handling instead of catching all exceptions with a bare `except`.
- Avoid using `print()` for logging; use the `logging` module instead.
- When logging, every function should log at least once

## Documentation
- Maintain a `README.md` file with project overview and setup instructions with every major change; ignore minor changes.
- Avoid changing structure of the `README.md` file without explicit permission from the user.
- Document all functions and classes with Google-style docstrings.

## Testing
- Place tests in the `tests` directory, mirroring the `src` structure.
- NEVER skip tests - broken tests should be fixed immediately or removed.
- Use `pytest` for testing and ensure all tests pass before merging code.
- Write tests for all new features and bug fixes.
- Run tests using conda environment named 'lila'
- Always mock read from *.txt and *.json files in tests, never read from them directly because they are not available in the test environment.

## Your Permission
- Never delete files without explicit permission from the user.
- Never delete more than 5 files without explicit permission from the user.
- Never read, edit, or delete *.txt or *.json files without explicit permission from the user.
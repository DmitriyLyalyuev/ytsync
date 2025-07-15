1. Run tests and linters:
  ```
    black --check -v *.py
    isort --check-only *.py
    pylint *.py --fail-under=9.5
  ```
2. If everything gone right commit changes.

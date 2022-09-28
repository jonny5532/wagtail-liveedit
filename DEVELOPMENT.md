## Running tests

./tools/test_wagtail_versions.py

## Updating PyPI

- Update version number in setup.py

- Run:

./setup.py sdist bdist_wheel
twine upload --skip-existing dist/*

## Running tests

`./tools/test_wagtail_versions.py`

## Testing locally

```export DATABASE_FILE=/tmp/test.db
export SELENIUM_HOST=172.17.0.7
export TEST_LIVE_SERVER_HOST=192.168.1.10
./manage.py migrate
./manage.py createsuperuser
./manage.py runserver```

## Updating PyPI

- Update version number in setup.py

- Run:

```./setup.py sdist bdist_wheel
twine upload --skip-existing dist/*```

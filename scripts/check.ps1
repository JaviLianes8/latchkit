# Local quality gate. Run before every commit. No CI runs in the cloud.
# Every tool runs through this environment's python, so the dev extra is what runs.
$ErrorActionPreference = "Stop"

python -c "import pytest_timeout" 2>$null
if ($LASTEXITCODE) { throw "pytest-timeout is missing: pip install -r requirements-dev.txt" }
python -m ruff format --check .
if ($LASTEXITCODE) { exit $LASTEXITCODE }
python -m ruff check .
if ($LASTEXITCODE) { exit $LASTEXITCODE }
python -m mypy --strict src tests
if ($LASTEXITCODE) { exit $LASTEXITCODE }
python -m pytest
if ($LASTEXITCODE) { exit $LASTEXITCODE }

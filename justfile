# tokledger justfile recipes

set shell := ["bash", "-euo", "pipefail", "-c"]

py := "uv run python"
pytest := "uv run pytest"
src_dir := "src"
test_dir := "tests"

install-dev:
    @echo "Installing development dependencies..."
    @uv sync --all-groups

install-motherduck:
    @echo "Installing motherduck 🦆..."
    @curl -s https://install.motherduck.com | sh


# ---- build & publish ----

# Remember to set the UV_PUBLISH_TOKEN environment variable.

build:
    @echo "Building the project..."
    rm -rf dist/
    uv build --no-sources

# Validate artifacts before any upload.
check-dist: build
    uv run twine check dist/*

publish-test: check-dist
    uv publish \
        --publish-url https://test.pypi.org/legacy/

publish: check-dist
    uv publish


# ---- hygiene ----

spell:
    typos

spell-diff:
    typos --diff

spell-fix:
    typos --write-changes

test *args:
    {{pytest}} -v -s {{args}}

# Run tests with coverage reporting
coverage:
    {{pytest}} --cov=src --cov-report=term-missing

lint:
    uv run ruff check {{src_dir}} {{test_dir}}
    uv run ruff format --check {{src_dir}} {{test_dir}}

typecheck:
    uv run pyrefly check {{src_dir}} {{test_dir}}

clean:
    rm -rf dist/ build/ .pytest_cache/ .mypy_cache/ .ruff_cache/
    find . -type d -name __pycache__ -prune -exec rm -rf {} +

check-justfile:
    just --fmt --check


# ---- full CI gate ----

ci: test lint typecheck

# --- CD / release ---

release-build:
    uv build --no-sources

release-check:
    uv run twine check dist/*

release-test:
    uv publish --publish-url https://test.pypi.org/legacy/

release:
    uv publish


# --- tokscale canonical commands ---

# Canonical tokscale commands for raw JSON data input.
# These commands are the raw interface for tokledger.
# Use the versioned golden JSON fixtures in tests/fixtures/ for testing.
# Updating the golden fixtures requires a dedicated PR.

tokscale-report:
    tokscale report --json --no-summarize

tokscale-models:
    tokscale models --json --group-by client,session,model --merge-worktrees

tokscale-graph:
    tokscale graph

tokscale-pricing:
    tokscale pricing <model-id> --json

# tokledger justfile recipes

py := "uv run python"
pytest := "uv run pytest"

install-dev:
    @echo "Installing development dependencies..."
    @uv run pip install -e .[dev]
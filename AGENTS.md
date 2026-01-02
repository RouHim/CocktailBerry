# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CocktailBerry is a Raspberry Pi-based cocktail machine system with two main versions:
- **v1**: PyQt5-based desktop application (stable)
- **v2**: FastAPI backend + React frontend (newer, more flexible)

Both versions share the same core functionality for cocktail preparation, recipe management, and hardware control.

## Development Commands

### Python Environment Setup
```bash
# Install all dependencies (required for development)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install --install-hooks
```

### Running the Application

#### v1 (Qt Application)
```bash
# Start the Qt-based application
uv run runme.py

# With options
uv run runme.py --calibration  # Run calibration program
uv run runme.py --debug        # Enable debug mode for microservice
uv run runme.py --quiet        # Hide startup messages
```

#### v2 (API + Web Client)
```bash
# Start FastAPI backend (development mode with auto-reload)
uv run fastapi dev ./src/api/api.py

# Or via CLI command
uv run runme.py api --port 8000

# Start React frontend (requires Node.js v20 and yarn)
cd web_client
yarn install  # First time only
yarn dev      # Development server
yarn build    # Production build
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov

# Run specific test file
uv run pytest tests/test_database_commander.py
```

### Code Quality
```bash
# Linting and formatting (handled by pre-commit hooks)
uv run ruff check --fix      # Lint and auto-fix
uv run ruff format           # Format code

# Type checking
uv run mypy src/

# Run all pre-commit hooks manually
uv run pre-commit run --all-files
```

### Documentation
```bash
# Serve documentation locally
uv run mkdocs serve

# Build documentation
uv run mkdocs build
```

### Microservice (Optional Component)
```bash
# Run microservice locally
cd microservice
uv run app.py
```

## Architecture

### Core Components

**Database Layer** (`src/database_commander.py`, `src/db_models.py`)
- SQLAlchemy ORM with SQLite database
- Main tables: `Recipes`, `Ingredients`, `Bottles`, `Available` (ingredient-bottle mappings), `Teamdata` (usage statistics)
- `DatabaseCommander` class provides high-level database operations
- Database migrations handled by `src/migration/migrator.py` (runs on startup)

**Machine Control** (`src/machine/`)
- `MachineController`: Singleton coordinating all hardware interactions
- `PinController` interface with platform-specific implementations:
  - `raspberry.py`: Raspberry Pi GPIO via gpiozero
  - `generic_board.py`: Generic boards via python-periphery
- `LedController`: WS281x LED strip control (Linux only)
- `Reverter`: Pump reversion logic for cleaning
- Hardware abstraction allows running on different platforms

**Configuration** (`src/config/`)
- YAML-based configuration in `config.yaml`
- `ConfigManager` singleton loads and validates settings
- User configs stored separately from defaults
- Settings include: pump pins, flow rates, LED options, language, theme

**API Layer** (`src/api/`)
- FastAPI application for v2 and external integrations
- Routers: `cocktails.py`, `ingredients.py`, `bottles.py`, `options.py`
- SSE (Server-Sent Events) for real-time updates
- Middleware for CORS and request logging
- Can run standalone or alongside Qt app

**UI Components**

*v1 (Qt):*
- `src/ui/`: PyQt5 UI files and styles (SCSS compiled to QSS)
- `src/tabs/`: Tab controllers (maker, recipes, ingredients, bottles)
- `src/display_controller.py`: Main window coordinator
- `src/dialog_handler.py`: Centralized dialog/message management

*v2 (React):*
- `web_client/src/`: React TypeScript application
- Vite build system, TailwindCSS for styling
- i18next for internationalization
- Axios for API communication

### Data Flow

1. **Cocktail Preparation**:
   - User selects recipe → `Cocktail` model created with ingredients
   - `MachineController.make_cocktail()` calculates timing based on flow rates
   - Pumps activated via `PinController` → physical cocktail dispensed
   - Consumption tracked in database (`DbBottle.consumption`, `DbTeamdata`)

2. **Recipe Management**:
   - Recipes link to ingredients through `DbCocktailIngredient` (many-to-many)
   - Auto-calculation of available recipes based on connected bottles
   - Virgin (non-alcoholic) variants generated automatically

3. **Addon System**:
   - `src/programs/addons.py`: Plugin architecture for extensions
   - Addons can hook into preparation lifecycle, UI events
   - See `addon_skeleton.py` for template

### Key Design Patterns

- **Singleton**: `MachineController`, `ConfigManager`, `DatabaseCommander` ensure single instances
- **Factory**: `gpio_factory.py` selects appropriate hardware controller
- **Repository**: `DatabaseCommander` abstracts database operations
- **Observer**: LED effects and UI updates respond to cocktail preparation events

## Important Notes

### Python Version
- Requires Python 3.11+ (see `pyproject.toml` and `.python-version`)
- Uses modern type hints (e.g., `list[str]` instead of `List[str]`)

### Platform-Specific Code
- GPIO/hardware modules are Linux-only (see `pyproject.toml` conditional dependencies)
- `mfrc522`, `rpi-ws281x`, `gpiozero` only installed on Linux
- Qt on ARM64: PyQt5 should be installed via apt, use `--system-site-packages` with venv

### Database
- SQLite with no direct SQL queries—all via SQLAlchemy ORM
- Migrations auto-run on startup via `runme.py`
- Default database copied on first run if missing
- Backup created in `saves/` directory before migrations

### Configuration
- Never hardcode hardware pins or settings—always use `CONFIG` from `config_manager`
- Theme/language settings in `src/__init__.py` define supported values
- Custom styles: SCSS files in `src/ui/styles/`, compile with `qtsass`

### Code Style
- Line length: 120 characters
- Ruff handles formatting/linting (replaces autopep8, pylint, isort)
- Pre-commit hooks enforce style automatically
- Docstrings not required (many ignored rules in `pyproject.toml`)
- Use `from __future__ import annotations` for forward references

### Translation
- Language files: `src/language.yaml` (backend/Qt), `web_client/src/locales/` (React)
- Use ISO 639-1 two-letter language codes
- All UI strings must be translatable—use `DialogHandler.get_translation()`

### Testing
- Tests in `tests/` directory
- Fixtures in `conftest.py`
- Use in-memory SQLite for database tests: `DatabaseCommander(db_url="sqlite:///:memory:")`

### Microservice
- Optional component for external webhooks, data posting
- Decouples non-core tasks from main application
- Docker-based deployment via `docker-compose.yml`
- Environment variables in `.env` file (not committed)

### Web Client (v2)
- React 19, TypeScript, Vite
- Development: `yarn dev` starts on localhost:5173
- Production: `yarn build` creates static files in `dist/`
- API base URL configured via environment variables (`.env.development`, `.env.production`)

## File Locations

- Main entry: `runme.py`
- Database: `Cocktail_database_default.db` (default), user DB copied on first run
- Logs: `logs/` directory
- Config: User config created on first run
- Default cocktail images: `default_cocktail_images/`
- User images: `display_images_user/`

## Common Patterns

### Adding a New Configuration Option
1. Add default value to config class in `src/config/`
2. Update config validation if needed
3. Update UI in `src/ui/` (v1) or `web_client/src/` (v2)
4. Migration handled automatically on next startup

### Adding a New Database Table
1. Create model in `src/db_models.py` inheriting from `Base`
2. Add methods to `DatabaseCommander` if needed
3. Restart app—`Base.metadata.create_all()` creates new tables
4. For data migrations, see `src/migration/`

### Adding Hardware Support
1. Implement `PinController` interface in `src/machine/`
2. Update `gpio_factory.py` to detect and instantiate controller
3. Test with `uv run runme.py --calibration`

### Adding API Endpoint
1. Create router in `src/api/routers/`
2. Register in `src/api/api.py`
3. Add corresponding frontend integration in `web_client/src/`

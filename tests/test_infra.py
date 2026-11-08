"""Тесты инфраструктурных файлов: Docker, compose, CI, зависимости."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    """Текст файла из корня репозитория."""
    return (ROOT / name).read_text(encoding="utf-8")


def test_dockerfile_exists():
    assert (ROOT / "Dockerfile").is_file()


def test_dockerfile_has_healthcheck():
    assert "HEALTHCHECK" in read("Dockerfile")
    assert "/health" in read("Dockerfile")


def test_dockerfile_runs_as_non_root():
    assert "USER appuser" in read("Dockerfile")
    assert "useradd" in read("Dockerfile")


def test_dockerfile_starts_entrypoint():
    assert 'CMD ["/app/docker/entrypoint.sh"]' in read("Dockerfile")


def test_dockerfile_installs_runtime_requirements():
    assert "pip install --no-cache-dir -r requirements.txt" in read("Dockerfile")


def test_dockerignore_excludes_local_artifacts():
    ignored = read(".dockerignore")
    assert ".venv" in ignored
    assert "data/warehouse.sqlite" in ignored
    assert "tests" in ignored


def test_entrypoint_applies_migrations_and_builds_warehouse():
    script = read("docker/entrypoint.sh")
    assert "python -m scripts.migrate" in script
    assert "python -m scripts.build_dataset" in script


def test_entrypoint_starts_uvicorn():
    script = read("docker/entrypoint.sh")
    assert "exec uvicorn app:app" in script
    assert "--workers" in script


def test_compose_defines_app_service():
    compose = read("docker-compose.yml")
    assert "services:" in compose
    assert "build: ." in compose
    assert '"8000:8000"' in compose


def test_compose_persists_warehouse_volume():
    compose = read("docker-compose.yml")
    assert "lada-data:/data" in compose
    assert "volumes:" in compose


def test_compose_checks_readiness():
    assert "/ready" in read("docker-compose.yml")


def test_compose_sets_production_mode():
    compose = read("docker-compose.yml")
    assert "LADA_ENV: prod" in compose
    assert "LADA_WORKERS" in compose


def test_ci_workflow_exists():
    assert (ROOT / ".github" / "workflows" / "ci.yml").is_file()


def test_ci_runs_quality_gates():
    workflow = read(".github/workflows/ci.yml")
    assert "ruff check ." in workflow
    assert "python tools/style_check.py" in workflow
    assert "python -m pytest -q" in workflow


def test_ci_builds_warehouse_before_tests():
    workflow = read(".github/workflows/ci.yml")
    assert workflow.index("scripts.build_dataset") < workflow.index("pytest")


def test_ci_builds_docker_image():
    workflow = read(".github/workflows/ci.yml")
    assert "docker build -t lada-cifra:ci ." in workflow


def test_ci_matrix_covers_supported_pythons():
    workflow = read(".github/workflows/ci.yml")
    assert '"3.11"' in workflow
    assert '"3.12"' in workflow


def test_runtime_requirements_have_no_test_tools():
    runtime = read("requirements.txt")
    assert "pytest" not in runtime
    assert "ruff" not in runtime
    assert "fastapi" in runtime


def test_dev_requirements_extend_runtime():
    dev = read("requirements-dev.txt")
    assert dev.startswith("-r requirements.txt")
    assert "pytest" in dev
    assert "ruff" in dev


def test_pyproject_points_at_python_311():
    assert 'requires-python = ">=3.11"' in read("pyproject.toml")


def test_sql_lives_in_migrations():
    files = sorted((ROOT / "sql" / "migrations").glob("*.sql"))
    assert [path.name for path in files] == ["0001_schema.sql", "0002_views.sql"]

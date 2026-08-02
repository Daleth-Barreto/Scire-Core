import pytest

from backend.setup.init import InitResult, run_init, write_env_file


def test_write_env_file_creates_from_example(tmp_path):
    example = tmp_path / ".env.example"
    example.write_text("LLM_PROVIDER=openrouter\nOPENROUTER_API_KEY=\n", encoding="utf-8")

    write_env_file(tmp_path)

    env = tmp_path / ".env"
    assert env.exists()
    assert "LLM_PROVIDER=openrouter" in env.read_text(encoding="utf-8")


def test_write_env_file_does_not_overwrite(tmp_path):
    example = tmp_path / ".env.example"
    example.write_text("LLM_PROVIDER=openrouter\n", encoding="utf-8")
    env = tmp_path / ".env"
    env.write_text("LLM_PROVIDER=openai\n", encoding="utf-8")

    write_env_file(tmp_path)

    assert env.read_text(encoding="utf-8") == "LLM_PROVIDER=openai\n"


def test_write_env_file_missing_example_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_env_file(tmp_path)


def test_run_init_reports_summary(mocker, tmp_path):
    (tmp_path / ".env.example").write_text("LLM_PROVIDER=openrouter\n", encoding="utf-8")
    mock_admin = mocker.patch("backend.setup.init._ensure_database", return_value=("role-created", "db-created", "vector-created"))
    mock_tables = mocker.patch("backend.setup.init._create_tables")
    mock_check = mocker.patch("backend.setup.init._graph_ready", return_value=True)

    result = run_init(tmp_path, admin_url="postgresql+psycopg://admin:pw@localhost:5432/postgres")

    assert isinstance(result, InitResult)
    assert result.env_created is True
    assert result.env_existed is False
    assert result.role_status == "role-created"
    assert result.db_status == "db-created"
    assert result.vector_status == "vector-created"
    assert result.tables_ready is True
    assert result.admin_url_supplied is True
    mock_admin.assert_called_once()
    mock_tables.assert_called_once()


def test_run_init_without_admin_url_skips_db(mocker, tmp_path):
    (tmp_path / ".env.example").write_text("LLM_PROVIDER=openrouter\n", encoding="utf-8")
    mock_admin = mocker.patch("backend.setup.init._ensure_database")
    mock_tables = mocker.patch("backend.setup.init._create_tables")
    mock_check = mocker.patch("backend.setup.init._graph_ready", return_value=False)

    result = run_init(tmp_path)

    mock_admin.assert_not_called()
    mock_tables.assert_called_once()
    assert result.admin_url_supplied is False
    assert result.tables_ready is False


def _fake_psycopg(mocker, conn) -> None:
    client = mocker.MagicMock()
    client.__enter__.return_value = conn
    mocker.patch("backend.setup.init.psycopg.connect", return_value=client)


def test_ensure_database_creates_role_db_and_extension(mocker):
    conn = mocker.MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    _fake_psycopg(mocker, conn)

    from backend.setup.init import _ensure_database

    role, db, vector = _ensure_database(
        admin_url="postgresql+psycopg://admin:pw@localhost:5432/postgres",
        db_name="scire",
        db_user="scire",
        db_password="scire",
    )

    assert role == "created"
    assert db == "created"
    assert vector == "created"
    calls = [c.args[0] for c in conn.execute.call_args_list]
    assert any("CREATE ROLE" in call for call in calls)
    assert any("CREATE DATABASE" in call for call in calls)
    assert any("CREATE EXTENSION" in call for call in calls)


def test_ensure_database_detects_existing(mocker):
    conn = mocker.MagicMock()
    conn.execute.return_value.fetchone.return_value = ("scire",)
    _fake_psycopg(mocker, conn)

    from backend.setup.init import _ensure_database

    role, db, vector = _ensure_database("postgresql+psycopg://admin:pw@localhost:5432/postgres")

    assert role == "exists"
    assert db == "exists"
    calls = [c.args[0] for c in conn.execute.call_args_list]
    assert not any("CREATE ROLE" in call for call in calls)

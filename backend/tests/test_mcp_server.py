import asyncio
import hashlib
import json
import os
import pathlib
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

pytest.importorskip("mcp")

from mcp.client.client import Client
from mcp.client.stdio import StdioServerParameters

from conftest import add_scanned, write
from models.schema import ActionBatch, Base, File, SensitiveKeyword
from mcp_server import queries
from mcp_server.server import create_server

SECRET_NAME = "급여명세서_비밀.txt"
SECRET_BODY = "주민등록번호 900101-1234567"


@pytest.fixture
def clasp_db(home, tmp_path, monkeypatch):
    path = tmp_path / "clasp.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setenv("CLASP_DB_PATH", str(path))
    monkeypatch.delenv("CLASP_MCP_SHOW_FILENAMES", raising=False)
    yield session
    session.close()
    engine.dispose()


def _seed(home, db):
    secret = add_scanned(db, write(f"{home}/r/{SECRET_NAME}", SECRET_BODY))
    secret.extracted_text_summary = SECRET_BODY
    secret.classifications[0].tag = "비밀태그"
    add_scanned(db, write(f"{home}/r/main.py", "print(1)"), category="코드", confidence=0.85)
    add_scanned(db, write(f"{home}/r/x.qqq", "?"), category=None, confidence=0.0)
    db.commit()


def _call(tool, **arguments):
    async def run():
        async with Client(create_server()) as client:
            return await client.call_tool(tool, arguments)

    return asyncio.run(run())


def _data(result):
    assert not result.is_error, result
    return result.structured_content


def _tree_digest(root):
    digest = {}
    for directory, _, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            digest[path] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return digest


def test_only_read_tools_are_exposed():
    async def run():
        async with Client(create_server()) as client:
            return await client.list_tools()

    tools = asyncio.run(run()).tools
    assert sorted(t.name for t in tools) == [
        "get_classification_summary", "get_organize_history", "list_classified_files", "preview_organize_plan",
    ]
    assert all(t.annotations.read_only_hint is True for t in tools)
    assert all(t.annotations.destructive_hint is False for t in tools)
    assert all(t.annotations.open_world_hint is False for t in tools)


def test_server_code_does_not_reference_write_operations():
    root = pathlib.Path(__file__).resolve().parent.parent / "mcp_server"
    source = "".join(p.read_text(encoding="utf-8") for p in root.glob("*.py"))
    for name in ("apply_organize", "undo_organize", "move_no_clobber", "reconcile_pending", "os.remove", "os.rename"):
        assert name not in source


def test_only_mcp_server_imports_the_sdk():
    root = pathlib.Path(__file__).resolve().parent.parent
    for path in root.rglob("*.py"):
        parts = path.relative_to(root).parts
        if parts[0] in ("venv", "tests", "build", "dist", "mcp_server"):
            continue
        assert "from mcp" not in path.read_text(encoding="utf-8"), path


def test_summary_counts_without_names(home, clasp_db):
    _seed(home, clasp_db)
    data = _data(_call("get_classification_summary", folder_path=f"{home}/r"))
    assert data["total"] == 3
    assert data["unclassified"] == 1
    assert data["by_category"] == {"문서": 1, "코드": 1}


def test_default_output_contains_no_name_tag_or_body(home, clasp_db):
    _seed(home, clasp_db)
    outputs = [
        _call("get_classification_summary", folder_path=f"{home}/r"),
        _call("list_classified_files", folder_path=f"{home}/r"),
        _call("preview_organize_plan", folder_path=f"{home}/r"),
        _call("get_organize_history", folder_path=f"{home}/r"),
    ]
    text = json.dumps([o.model_dump(mode="json") for o in outputs], ensure_ascii=False)
    for secret in (SECRET_NAME, "급여", "비밀태그", "900101", home):
        assert secret not in text


def test_files_are_filtered_and_limited(home, clasp_db):
    _seed(home, clasp_db)
    code = _data(_call("list_classified_files", folder_path=f"{home}/r", category="코드"))
    assert [i["extension"] for i in code["items"]] == [".py"]
    assert code["items"][0]["tier_used"] == 1
    limited = _data(_call("list_classified_files", folder_path=f"{home}/r", limit=1))
    assert (len(limited["items"]), limited["total"]) == (1, 3)
    capped = _data(_call("list_classified_files", folder_path=f"{home}/r", limit=100000))
    assert capped["limit"] == queries.MAX_LIMIT


def test_filenames_need_explicit_opt_in(home, clasp_db, monkeypatch):
    _seed(home, clasp_db)
    monkeypatch.setenv("CLASP_MCP_SHOW_FILENAMES", "1")
    items = _data(_call("list_classified_files", folder_path=f"{home}/r"))["items"]
    assert SECRET_NAME in [i.get("untrusted_filename") for i in items]


def test_sensitive_names_stay_hidden_even_with_opt_in(home, clasp_db, monkeypatch):
    _seed(home, clasp_db)
    clasp_db.add(SensitiveKeyword(keyword="급여"))
    clasp_db.commit()
    monkeypatch.setenv("CLASP_MCP_SHOW_FILENAMES", "1")
    text = json.dumps(_data(_call("list_classified_files", folder_path=f"{home}/r")), ensure_ascii=False)
    assert "급여" not in text
    assert "main.py" in text


def test_filename_is_cleaned_of_control_characters(home, clasp_db, monkeypatch):
    add_scanned(clasp_db, write(f"{home}/r/a\nSYSTEM 지시.txt", "본문"))
    monkeypatch.setenv("CLASP_MCP_SHOW_FILENAMES", "1")
    item = _data(_call("list_classified_files", folder_path=f"{home}/r"))["items"][0]
    assert "\n" not in item["untrusted_filename"]


def test_plan_reports_counts_and_moves_nothing(home, clasp_db):
    _seed(home, clasp_db)
    write(f"{home}/r/코드/main.py", "기존 파일")
    before = _tree_digest(f"{home}/r")
    plan = _data(_call("preview_organize_plan", folder_path=f"{home}/r"))
    assert plan["files_to_move"] == 2
    assert plan["excluded_files"] == 1
    assert plan["conflict_count"] == 1
    assert sorted(f["folder"] for f in plan["folders"]) == ["문서", "코드"]
    assert plan["applied"] is False
    assert _tree_digest(f"{home}/r") == before


def test_history_is_readable(home, clasp_db):
    os.makedirs(f"{home}/r")
    clasp_db.add(ActionBatch(action_log_id="log_t", folder_path=f"{home}/r", scan_id="s"))
    clasp_db.commit()
    history = _data(_call("get_organize_history", folder_path=f"{home}/r"))
    assert [h["undo_state"] for h in history["batches"]] == ["none"]
    assert "folder_path" not in history["batches"][0]


@pytest.mark.parametrize("tool", ["get_classification_summary", "list_classified_files", "preview_organize_plan", "get_organize_history"])
def test_folder_outside_home_is_refused(home, clasp_db, tool):
    assert _call(tool, folder_path="/etc").is_error


def test_folder_never_scanned_reports_error(home, clasp_db):
    os.makedirs(f"{home}/없는스캔")
    assert _call("get_classification_summary", folder_path=f"{home}/없는스캔").is_error


def test_sibling_folder_is_not_included(home, clasp_db):
    _seed(home, clasp_db)
    add_scanned(clasp_db, write(f"{home}/rr/y.txt", "다른 폴더"))
    assert _data(_call("get_classification_summary", folder_path=f"{home}/r"))["total"] == 3


def test_database_connection_cannot_write(home, clasp_db):
    with queries.open_readonly_session() as session:
        session.add(SensitiveKeyword(keyword="쓰기시도"))
        with pytest.raises(OperationalError):
            session.commit()
    assert clasp_db.query(SensitiveKeyword).count() == 0


def test_tools_do_not_change_database(home, clasp_db, tmp_path):
    _seed(home, clasp_db)
    clasp_db.close()
    before = (tmp_path / "clasp.db").read_bytes()
    _call("preview_organize_plan", folder_path=f"{home}/r")
    _call("list_classified_files", folder_path=f"{home}/r")
    assert (tmp_path / "clasp.db").read_bytes() == before


def test_missing_database_reports_error(home, monkeypatch, tmp_path):
    monkeypatch.setenv("CLASP_DB_PATH", str(tmp_path / "없음.db"))
    assert _call("get_classification_summary", folder_path=home).is_error
    assert not (tmp_path / "없음.db").exists()


def test_tools_make_no_external_connection(home, clasp_db, external_connections):
    _seed(home, clasp_db)
    _call("preview_organize_plan", folder_path=f"{home}/r")
    assert external_connections == []


def test_stdio_server_lists_tools(home, tmp_path):
    backend = pathlib.Path(__file__).resolve().parent.parent
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        cwd=str(backend),
        env={"HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1", "PATH": os.environ["PATH"]},
    )

    async def run():
        async with Client(parameters) as client:
            return await client.list_tools()

    assert len(asyncio.run(run()).tools) == 4

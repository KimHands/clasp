import asyncio
import os

import pytest
from sqlalchemy.orm import sessionmaker

from conftest import write
from models.schema import AppSetting, Classification, CustomCategory, File, Rule, SensitiveKeyword
from services import scan_service


def _scan(db, monkeypatch, folder, scan_id):
    folder = os.path.normpath(folder)
    monkeypatch.setattr(scan_service, "SessionLocal", sessionmaker(bind=db.get_bind()))

    async def collect():
        return [event async for event in scan_service.run_scan(scan_id, folder)]

    events = asyncio.run(collect())
    db.expire_all()
    assert events[-1]["stage"] == 7
    return events


def _spy_reads(monkeypatch):
    reads = []
    real = scan_service.extract_text
    monkeypatch.setattr(scan_service, "extract_text", lambda p: reads.append(p) or real(p))
    return reads


def _latest(db, scan_id):
    return db.query(Classification).filter_by(scan_id=scan_id).one()


def test_manual_classification_shows_after_rescan(client, home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/a.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    file_id = db.query(File).one().id
    assert client.patch(f"/files/{file_id}", json={"category": "프레젠테이션"}).status_code == 200
    _scan(db, monkeypatch, f"{home}/r", "s2")
    item = client.get("/files", params={"scan_id": "s2"}).json()["data"]["items"][0]
    assert (item["category"], item["is_manual"]) == ("프레젠테이션", True)


def test_manual_classification_appears_once_per_file(client, home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/a.txt", "본문\n")
    write(f"{home}/r/b.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    file_id = db.query(File).filter_by(filename="a.txt").one().id
    client.patch(f"/files/{file_id}", json={"category": "프레젠테이션"})
    _scan(db, monkeypatch, f"{home}/r", "s2")
    data = client.get("/files", params={"scan_id": "s2"}).json()["data"]
    assert data["total"] == 2
    assert sorted(i["filename"] for i in data["items"]) == ["a.txt", "b.txt"]


def test_manual_from_other_folder_does_not_leak_into_scan(client, home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/a.txt", "본문\n")
    write(f"{home}/q/z.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/q", "other")
    client.patch(f"/files/{db.query(File).one().id}", json={"category": "프레젠테이션"})
    _scan(db, monkeypatch, f"{home}/r", "s1")
    names = [i["filename"] for i in client.get("/files", params={"scan_id": "s1"}).json()["data"]["items"]]
    assert names == ["a.txt"]


def test_unchanged_files_are_not_read_again(home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/a.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    reads = _spy_reads(monkeypatch)
    _scan(db, monkeypatch, f"{home}/r", "s2")
    assert reads == []
    assert _latest(db, "s2").category == _latest(db, "s1").category


def test_changed_file_is_read_again(home, db, monkeypatch, stub_embeddings):
    path = write(f"{home}/r/a.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    write(path, "내용이 바뀐 긴 본문\n")
    reads = _spy_reads(monkeypatch)
    _scan(db, monkeypatch, f"{home}/r", "s2")
    assert reads == [path]


@pytest.mark.parametrize("change", [
    lambda db: db.add(Rule(priority=1, type="extension", value="csv", folder_name="설문")),
    lambda db: db.add(SensitiveKeyword(keyword="없는키워드")),
    lambda db: db.add(CustomCategory(name="새카테고리", keywords="[]")),
    lambda db: db.add(AppSetting(key="local_llm_model", value="m")),
])
def test_settings_change_reclassifies_unchanged_files(home, db, monkeypatch, stub_embeddings, change):
    write(f"{home}/r/a.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    change(db)
    db.commit()
    reads = _spy_reads(monkeypatch)
    _scan(db, monkeypatch, f"{home}/r", "s2")
    assert len(reads) == 1


def test_rule_applies_on_rescan(home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/survey.csv", "a,b\n1,2\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    assert _latest(db, "s1").category == "스프레드시트"
    db.add(Rule(priority=1, type="extension", value="csv", folder_name="설문"))
    db.commit()
    _scan(db, monkeypatch, f"{home}/r", "s2")
    assert _latest(db, "s2").category == "설문"


def test_removing_sensitive_keyword_restores_analysis(home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/급여.txt", "본문\n")
    keyword = SensitiveKeyword(keyword="급여")
    db.add(keyword)
    db.commit()
    _scan(db, monkeypatch, f"{home}/r", "s1")
    assert db.query(File).one().extracted_text_summary is None
    db.delete(keyword)
    db.commit()
    _scan(db, monkeypatch, f"{home}/r", "s2")
    assert "본문" in db.query(File).one().extracted_text_summary


def test_file_without_previous_result_is_analyzed(home, db, monkeypatch, stub_embeddings):
    write(f"{home}/r/a.txt", "본문\n")
    _scan(db, monkeypatch, f"{home}/r", "s1")
    db.query(Classification).delete()
    db.commit()
    reads = _spy_reads(monkeypatch)
    _scan(db, monkeypatch, f"{home}/r", "s2")
    assert len(reads) == 1


def test_scanning_other_folder_does_not_hide_settings_change(home, db, monkeypatch, stub_embeddings):
    write(f"{home}/a/survey.csv", "a,b\n1,2\n")
    os.makedirs(f"{home}/b")
    _scan(db, monkeypatch, f"{home}/a", "s1")
    db.add(Rule(priority=1, type="extension", value="csv", folder_name="설문"))
    db.commit()
    _scan(db, monkeypatch, f"{home}/b", "s2")
    _scan(db, monkeypatch, f"{home}/a", "s3")
    assert _latest(db, "s3").category == "설문"

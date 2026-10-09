"""Running the site on its own computer: production server, uploaded photos, backups."""

import sqlite3
import zipfile
from importlib import reload

import pytest
from django.core.management import CommandError, call_command


def test_serve_refuses_to_run_with_debug_on(settings):
    settings.DEBUG = True
    with pytest.raises(CommandError, match="DJANGO_DEBUG"):
        call_command("serve")


def test_serve_starts_waitress_on_this_computer_only(settings, monkeypatch):
    settings.DEBUG = False
    calls = {}
    monkeypatch.setattr(
        "portal.management.commands.serve.serve", lambda app, **kwargs: calls.update(kwargs)
    )
    call_command("serve")
    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == 8000


def test_uploaded_photos_are_served_with_debug_off(client, settings, tmp_path):
    # urls.py is read once per test run with SERVE_MEDIA on (the default), DEBUG off (pytest).
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "albums").mkdir()
    (tmp_path / "albums" / "sports.jpg").write_bytes(b"jpeg bytes")

    response = client.get("/media/albums/sports.jpg")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == b"jpeg bytes"


def test_https_site_trusts_its_own_address_for_forms(monkeypatch):
    from school_portal import settings as project_settings

    monkeypatch.setenv("SITE_URL", "https://school.example")
    try:
        reload(project_settings)
        assert project_settings.CSRF_TRUSTED_ORIGINS == ["https://school.example"]
        assert project_settings.SESSION_COOKIE_SECURE
    finally:
        monkeypatch.delenv("SITE_URL")
        reload(project_settings)


@pytest.mark.django_db(transaction=True)
def test_backup_saves_database_and_photos(settings, tmp_path, make_event):
    make_event(title="Sports day")
    settings.MEDIA_ROOT = tmp_path / "media"
    (tmp_path / "media" / "albums").mkdir(parents=True)
    (tmp_path / "media" / "albums" / "sports.jpg").write_bytes(b"jpeg bytes")
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"
    (tmp_path / "private" / "achievements").mkdir(parents=True)
    (tmp_path / "private" / "achievements" / "win.jpg").write_bytes(b"private bytes")

    call_command("backup", to=tmp_path / "backups")

    [backup] = (tmp_path / "backups").glob("school-backup-*.zip")
    with zipfile.ZipFile(backup) as archive:
        assert archive.read("media/albums/sports.jpg") == b"jpeg bytes"
        assert archive.read("private_media/achievements/win.jpg") == b"private bytes"
        archive.extract("db.sqlite3", tmp_path)
    with sqlite3.connect(tmp_path / "db.sqlite3") as restored:
        titles = [row[0] for row in restored.execute("select title from portal_event")]
    restored.close()
    assert titles == ["Sports day"]
    assert not list((tmp_path / "backups").glob("*.tmp"))


@pytest.mark.django_db(transaction=True)
def test_backup_keeps_only_the_newest(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    folder = tmp_path / "backups"
    folder.mkdir()
    for day in ("2026-01-01", "2026-01-02", "2026-01-03"):
        (folder / f"school-backup-{day}-000000.zip").write_bytes(b"old")

    call_command("backup", to=folder, keep=2)

    names = sorted(file.name for file in folder.glob("*.zip"))
    assert len(names) == 2
    assert names[0] == "school-backup-2026-01-03-000000.zip"

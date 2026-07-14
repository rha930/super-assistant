
import pytest
from services.note_repository import NoteRepository


@pytest.fixture()
def repo(tmp_path):
    db_path = str(tmp_path / "test_notes.db")
    return NoteRepository(db_path=db_path)


class TestCreateNote:
    def test_returns_note_with_id(self, repo):
        note = repo.create_note("user1", title="My Note", content="hello")
        assert note["id"].startswith("note_")
        assert note["user_id"] == "user1"
        assert note["title"] == "My Note"
        assert note["content"] == "hello"
        assert note["created_at"]
        assert note["updated_at"]

    def test_default_title(self, repo):
        note = repo.create_note("user1")
        assert note["title"] == "Untitled Note"

    def test_title_truncated_at_200(self, repo):
        long_title = "x" * 300
        note = repo.create_note("user1", title=long_title)
        assert len(note["title"]) == 200


class TestGetNote:
    def test_returns_note_for_owner(self, repo):
        created = repo.create_note("user1", title="Test")
        fetched = repo.get_note("user1", created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]

    def test_returns_none_for_wrong_user(self, repo):
        created = repo.create_note("user1", title="Test")
        assert repo.get_note("user2", created["id"]) is None

    def test_returns_none_for_missing_id(self, repo):
        assert repo.get_note("user1", "nonexistent") is None


class TestUpdateNote:
    def test_updates_title(self, repo):
        created = repo.create_note("user1", title="Old")
        updated = repo.update_note("user1", created["id"], title="New")
        assert updated["title"] == "New"
        assert updated["updated_at"] >= created["updated_at"]

    def test_updates_content(self, repo):
        created = repo.create_note("user1", content="old")
        updated = repo.update_note("user1", created["id"], content="new")
        assert updated["content"] == "new"

    def test_partial_update_preserves_other_fields(self, repo):
        created = repo.create_note("user1", title="Keep", content="Also keep")
        updated = repo.update_note("user1", created["id"], title="Changed")
        assert updated["title"] == "Changed"
        assert updated["content"] == "Also keep"

    def test_returns_none_for_wrong_user(self, repo):
        created = repo.create_note("user1", title="Test")
        assert repo.update_note("user2", created["id"], title="Hack") is None


class TestAppendContent:
    def test_appends_with_separator(self, repo):
        created = repo.create_note("user1", content="First")
        updated = repo.append_content("user1", created["id"], "Second")
        assert updated["content"] == "First\n\nSecond"

    def test_appends_to_empty(self, repo):
        created = repo.create_note("user1", content="")
        updated = repo.append_content("user1", created["id"], "Only")
        assert updated["content"] == "Only"

    def test_returns_none_for_wrong_user(self, repo):
        created = repo.create_note("user1", content="x")
        assert repo.append_content("user2", created["id"], "y") is None


class TestDeleteNote:
    def test_deletes_existing(self, repo):
        created = repo.create_note("user1")
        assert repo.delete_note("user1", created["id"]) is True
        assert repo.get_note("user1", created["id"]) is None

    def test_returns_false_for_wrong_user(self, repo):
        created = repo.create_note("user1")
        assert repo.delete_note("user2", created["id"]) is False

    def test_returns_false_for_nonexistent(self, repo):
        assert repo.delete_note("user1", "nope") is False


class TestListNotes:
    def test_returns_notes_ordered_by_updated(self, repo):
        repo.create_note("user1", title="First")
        repo.create_note("user1", title="Second")
        notes = repo.list_notes("user1")
        assert len(notes) == 2
        # Most recently created (Second) should be first
        assert notes[0]["title"] == "Second"
        assert notes[1]["title"] == "First"

    def test_respects_limit(self, repo):
        for i in range(5):
            repo.create_note("user1", title=f"Note {i}")
        notes = repo.list_notes("user1", limit=3)
        assert len(notes) == 3

    def test_user_isolation(self, repo):
        repo.create_note("user1", title="User1 Note")
        repo.create_note("user2", title="User2 Note")
        notes = repo.list_notes("user1")
        assert len(notes) == 1
        assert notes[0]["title"] == "User1 Note"

    def test_includes_preview(self, repo):
        repo.create_note("user1", title="Test", content="Some preview content here")
        notes = repo.list_notes("user1")
        assert "preview" in notes[0]
        assert notes[0]["preview"].startswith("Some preview")

import os

import pytest
from services.history_repository_local import LocalChatHistoryRepository


@pytest.fixture()
def repo(tmp_path):
    db_path = os.path.join(str(tmp_path), "test.db")
    return LocalChatHistoryRepository(db_path=db_path, max_messages_per_conversation=5)


class TestAppendAndRetrieve:
    def test_append_returns_message_dict(self, repo):
        msg = repo.append_message("u1", "c1", "user", "hello")
        assert msg["role"] == "user"
        assert msg["content"] == "hello"
        assert msg["user_id"] == "u1"
        assert msg["conversation_id"] == "c1"
        assert msg["id"].startswith("msg_")

    def test_get_messages_returns_appended(self, repo):
        repo.append_message("u1", "c1", "user", "hi")
        repo.append_message("u1", "c1", "agent", "hello back")
        messages = repo.get_messages("u1", "c1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "agent"

    def test_messages_isolated_by_user(self, repo):
        repo.append_message("u1", "c1", "user", "from u1")
        repo.append_message("u2", "c1", "user", "from u2")
        assert len(repo.get_messages("u1", "c1")) == 1
        assert len(repo.get_messages("u2", "c1")) == 1

    def test_messages_isolated_by_conversation(self, repo):
        repo.append_message("u1", "c1", "user", "conv1")
        repo.append_message("u1", "c2", "user", "conv2")
        assert len(repo.get_messages("u1", "c1")) == 1
        assert len(repo.get_messages("u1", "c2")) == 1


class TestRetention:
    def test_trims_oldest_beyond_limit(self, repo):
        for i in range(8):
            repo.append_message("u1", "c1", "user", f"msg-{i}")
        messages = repo.get_messages("u1", "c1")
        assert len(messages) == 5
        assert messages[0]["content"] == "msg-3"

    def test_limit_param_on_get(self, repo):
        for i in range(4):
            repo.append_message("u1", "c1", "user", f"msg-{i}")
        messages = repo.get_messages("u1", "c1", limit=2)
        assert len(messages) == 2


class TestDelete:
    def test_delete_conversation(self, repo):
        repo.append_message("u1", "c1", "user", "hi")
        repo.append_message("u1", "c2", "user", "hi")
        repo.delete_conversation("u1", "c1")
        assert len(repo.get_messages("u1", "c1")) == 0
        assert len(repo.get_messages("u1", "c2")) == 1

    def test_delete_all_for_user(self, repo):
        repo.append_message("u1", "c1", "user", "hi")
        repo.append_message("u1", "c2", "user", "hi")
        repo.append_message("u2", "c3", "user", "hi")
        repo.delete_all_for_user("u1")
        assert len(repo.get_messages("u1", "c1")) == 0
        assert len(repo.get_messages("u1", "c2")) == 0
        assert len(repo.get_messages("u2", "c3")) == 1


class TestListConversations:
    def test_lists_conversations_with_preview(self, repo):
        repo.append_message("u1", "c1", "user", "first question")
        repo.append_message("u1", "c1", "agent", "first answer")
        repo.append_message("u1", "c2", "user", "second question")

        convos = repo.list_conversations("u1")
        assert len(convos) == 2
        ids = [c["conversation_id"] for c in convos]
        assert "c1" in ids
        assert "c2" in ids
        for c in convos:
            assert "preview" in c
            assert "message_count" in c

    def test_isolated_by_user(self, repo):
        repo.append_message("u1", "c1", "user", "hi")
        repo.append_message("u2", "c2", "user", "hi")
        assert len(repo.list_conversations("u1")) == 1
        assert len(repo.list_conversations("u2")) == 1


class TestMetadata:
    def test_metadata_persisted_and_retrieved(self, repo):
        repo.append_message("u1", "c1", "agent", "hi", metadata={"artifacts": [{"type": "graph"}]})
        messages = repo.get_messages("u1", "c1")
        assert messages[0]["metadata"]["artifacts"][0]["type"] == "graph"

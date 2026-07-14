from unittest.mock import MagicMock
from treeherder.etl.management.commands import ingest

REPO_META = {
    "owner": "o",
    "repo": "r",
    "branch": "main",
    "url": "https://github.com/o/r",
    "tc_root_url": "https://tc.example.com",
}


def test_query_data_pygithub(monkeypatch):
    """query_data must use PyGithub objects.

    This replaces test_query_data_consumes_compare_dict which was a regression guard
    for Bug 2009865. Since we now use PyGithub objects throughout query_data,
    we mock the repository and its methods.
    """
    mock_repo = MagicMock()

    # Define mock commits
    c1 = MagicMock()
    c1.sha = "C1"
    c1.commit.message = "Fix the thing"
    c1.commit.author.raw_data = {"name": "Dev", "email": "dev@example.com"}
    c1.commit.committer.raw_data = {"date": "2026-02-02T00:00:00Z"}

    # Define comparison results
    comp1 = MagicMock()
    # merge_base_commit
    mb1 = MagicMock()
    mb1.sha = "BASE"
    mb1.commit.committer.raw_data = {"date": "2026-01-01T00:00:00Z"}
    p1 = MagicMock()
    p1.sha = "PARENT"
    mb1.parents = [p1]
    comp1.merge_base_commit = mb1
    comp1.commits = []

    comp2 = MagicMock()
    mb2 = MagicMock()
    mb2.sha = "PARENT"
    mb2.parents = []
    comp2.merge_base_commit = mb2
    comp2.commits = [c1]

    # Mock get_commit for the parent
    parent_commit = MagicMock()
    parent_commit.sha = "PARENT"
    parent_commit.commit.committer.raw_data = {"date": "2026-02-02T00:00:00Z"}

    def fake_compare(base, head):
        if base == "main" and head == "HEAD":
            return comp1
        if base == "PARENT" and head == "HEAD":
            return comp2
        raise ValueError(f"Unexpected compare call: {base}...{head}")

    mock_repo.compare.side_effect = fake_compare
    mock_repo.get_commit.return_value = parent_commit

    mock_get_repo = MagicMock(return_value=mock_repo)
    monkeypatch.setattr(ingest.github, "get_repo", mock_get_repo)

    event_base_sha, commits = ingest.query_data(REPO_META, "HEAD")

    assert event_base_sha == "PARENT"
    assert commits == [
        {
            "message": "Fix the thing",
            "author": {"name": "Dev", "email": "dev@example.com"},
            "committer": {"date": "2026-02-02T00:00:00Z"},
            "id": "C1",
        }
    ]

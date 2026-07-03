import datetime
import os
from unittest.mock import MagicMock

import pytest
from github.Commit import Commit
from github.GithubException import UnknownObjectException
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest
from github.Repository import Repository

from treeherder.utils import github


# Helper function to create a mock PyGithub Commit object
def create_mock_commit(
    sha, message, author_name, author_email, committer_name, committer_email, date_str, parents=None
):
    mock_commit_obj = MagicMock(spec=Commit)
    mock_commit_obj.sha = sha
    mock_commit_obj.commit.message = message
    mock_commit_obj.commit.author.name = author_name
    mock_commit_obj.commit.author.email = author_email
    mock_commit_obj.commit.author.date = datetime.datetime.fromisoformat(
        date_str.replace("Z", "+00:00")
    )
    mock_commit_obj.commit.committer.name = committer_name
    mock_commit_obj.commit.committer.email = committer_email
    mock_commit_obj.commit.committer.date = datetime.datetime.fromisoformat(
        date_str.replace("Z", "+00:00")
    )
    mock_commit_obj.parents = [
        create_mock_commit(p, "", "", "", "", "", date_str) for p in (parents or [])
    ]
    return mock_commit_obj


# Helper function to create a mock PyGithub PullRequest object
def create_mock_pr(pr_id, base_repo_url, head_repo_url, base_sha, head_sha, commits=None):
    mock_pr = MagicMock(spec=PullRequest)
    mock_pr.number = pr_id
    mock_pr.base.repo.clone_url = base_repo_url
    mock_pr.head.repo.clone_url = head_repo_url
    mock_pr.base.sha = base_sha
    mock_pr.head.sha = head_sha
    mock_pr.get_commits.return_value = MagicMock(spec=PaginatedList, wraps=commits or [])
    return mock_pr


# Helper function to create a mock PyGithub Repository object
def create_mock_repo(owner, name):
    mock_repo = MagicMock(spec=Repository)
    mock_repo.owner.login = owner
    mock_repo.name = name
    return mock_repo


@pytest.fixture
def mock_github_client(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(github, "github_client", mock_client)
    return mock_client


@pytest.fixture
def set_github_token(monkeypatch):
    monkeypatch.setitem(os.environ, "GITHUB_TOKEN", "fake_token")
    # Reload the github module to re-initialize github_client with the token
    import importlib

    importlib.reload(github)


@pytest.fixture
def unset_github_token(monkeypatch):
    if "GITHUB_TOKEN" in os.environ:
        monkeypatch.delitem(os.environ, "GITHUB_TOKEN")
    import importlib

    importlib.reload(github)


class TestGithubUtils:
    def test_github_client_with_token(self, set_github_token):
        # The github_client is reloaded in the fixture, so we can access it directly
        assert github.github_client is not None
        assert github.github_client.auth is not None
        assert "login" in dir(github.github_client)  # Check if it's an authenticated client

    def test_github_client_without_token(self, unset_github_token):
        assert github.github_client is not None
        assert github.github_client.auth is None  # Should be unauthenticated
        assert "login" not in dir(github.github_client)  # Should not have user methods

    def test_get_github_repo(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_github_client.get_repo.return_value = mock_repo

        repo = github.get_github_repo("mozilla", "test_repo")
        mock_github_client.get_repo.assert_called_once_with("mozilla/test_repo")
        assert repo == mock_repo

    def test_get_github_repo_not_found(self, mock_github_client):
        mock_github_client.get_repo.side_effect = UnknownObjectException(
            status=404, data={}, headers={}
        )

        with pytest.raises(UnknownObjectException):
            github.get_github_repo("nonexistent", "repo")

    def test_get_pull_request(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_pr = create_mock_pr(123, "base_url", "head_url", "base_sha", "head_sha")
        mock_repo.get_pull.return_value = mock_pr
        mock_github_client.get_repo.return_value = mock_repo

        pr = github.get_pull_request("mozilla", "test_repo", 123)
        mock_github_client.get_repo.assert_called_once_with("mozilla/test_repo")
        mock_repo.get_pull.assert_called_once_with(123)
        assert pr == mock_pr

    def test_get_pull_request_commits(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_pr = create_mock_pr(
            123, "base_url", "head_url", "base_sha", "head_sha", commits=["commit1", "commit2"]
        )
        mock_repo.get_pull.return_value = mock_pr
        mock_github_client.get_repo.return_value = mock_repo

        commits = github.get_pull_request_commits("mozilla", "test_repo", 123)
        mock_pr.get_commits.assert_called_once_with()
        assert list(commits) == ["commit1", "commit2"]  # PyGithub PaginatedList can be iterated

    def test_compare_shas(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_comparison = MagicMock()
        mock_repo.compare.return_value = mock_comparison
        mock_github_client.get_repo.return_value = mock_repo

        comparison = github.compare_shas("mozilla", "test_repo", "base_sha", "head_sha")
        mock_github_client.get_repo.assert_called_once_with("mozilla/test_repo")
        mock_repo.compare.assert_called_once_with("base_sha", "head_sha")
        assert comparison == mock_comparison

    def test_get_all_commits(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_commit1 = create_mock_commit(
            "sha1", "msg1", "A1", "a1@e.com", "C1", "c1@e.com", "2023-01-01T12:00:00Z"
        )
        mock_commit2 = create_mock_commit(
            "sha2", "msg2", "A2", "a2@e.com", "C2", "c2@e.com", "2023-01-02T12:00:00Z"
        )
        mock_repo.get_commits.return_value = MagicMock(
            spec=PaginatedList, wraps=[mock_commit1, mock_commit2]
        )
        mock_github_client.get_repo.return_value = mock_repo

        commits = github.get_all_commits("mozilla", "test_repo")
        mock_github_client.get_repo.assert_called_once_with("mozilla/test_repo")
        mock_repo.get_commits.assert_called_once_with()
        assert list(commits) == [mock_commit1, mock_commit2]

    def test_get_all_commits_with_params(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_repo.get_commits.return_value = MagicMock(spec=PaginatedList, wraps=[])
        mock_github_client.get_repo.return_value = mock_repo

        params = {"sha": "some_sha", "author": "test_author"}
        github.get_all_commits("mozilla", "test_repo", params)
        mock_repo.get_commits.assert_called_once_with(sha="some_sha", author="test_author")

    def test_get_commit(self, mock_github_client):
        mock_repo = create_mock_repo("mozilla", "test_repo")
        mock_commit = create_mock_commit(
            "sha123", "msg", "A", "a@e.com", "C", "c@e.com", "2023-01-01T12:00:00Z"
        )
        mock_repo.get_commit.return_value = mock_commit
        mock_github_client.get_repo.return_value = mock_repo

        commit = github.get_commit("mozilla", "test_repo", "sha123")
        mock_github_client.get_repo.assert_called_once_with("mozilla/test_repo")
        mock_repo.get_commit.assert_called_once_with("sha123")
        assert commit == mock_commit

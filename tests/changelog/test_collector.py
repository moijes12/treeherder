import binascii
import json
import os
import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import responses

from treeherder.changelog.collector import collect
from treeherder.utils import github


def random_id():
    return binascii.hexlify(os.urandom(16)).decode("utf8")


def prepare_responses():
    # Placeholder for backward compatibility with tests/changelog/test_tasks.py
    pass


def mock_github(monkeypatch):
    now = datetime.now()

    def mock_get_repo(owner, repo_name):
        mock_repo = MagicMock()
        mock_repo.full_name = f"{owner}/{repo_name}"
        mock_repo.name = repo_name

        # Mock releases
        mock_release = MagicMock()
        mock_release.name = "ok"
        mock_release.tag_name = "some tag"
        mock_release.published_at = now
        mock_release.id = 12345
        mock_release.html_url = "url"
        mock_release.author.login = "tarek"
        mock_repo.get_releases.return_value = [mock_release]

        # Mock commits
        mock_commit_obj = MagicMock()
        mock_commit_obj.sha = random_id()
        mock_commit_obj.html_url = "url"
        mock_commit_obj.commit.message = "yeah"
        mock_commit_obj.commit.author.name = "tarek"
        mock_commit_obj.commit.author.date = now

        mock_file = MagicMock()
        mock_file.filename = "config/config.yml"
        mock_commit_obj.files = [mock_file]

        mock_repo.get_commits.return_value = [mock_commit_obj]
        mock_repo.get_commit.return_value = mock_commit_obj

        return mock_repo

    monkeypatch.setattr(github, "get_repo", mock_get_repo)


def test_collect(monkeypatch):
    yesterday = datetime.now() - timedelta(days=1)
    yesterday = yesterday.strftime("%Y-%m-%dT%H:%M:%S")
    mock_github(monkeypatch)
    res = list(collect(yesterday))

    # we're not looking into much details here, we can do this
    # once we start to tweak the filters
    assert len(res) > 0

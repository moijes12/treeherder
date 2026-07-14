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


def mock_github(monkeypatch):
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def mock_get_repo(owner_repo):
        owner, repo_name = owner_repo.split("/")
        mock_repo = MagicMock()
        mock_repo.full_name = owner_repo
        mock_repo.name = repo_name

        # Mock releases
        mock_release = MagicMock()
        mock_release.raw_data = {
            "name": "ok",
            "published_at": now_str,
            "id": random_id(),
            "html_url": "url",
            "tag_name": "some tag",
            "author": {"login": "tarek"},
        }
        mock_release.published_at = now
        mock_repo.get_releases.return_value = [mock_release]

        # Mock commits
        mock_commit_obj = MagicMock()
        mock_commit_obj.sha = random_id()
        mock_commit_obj.html_url = "url"
        mock_commit_obj.commit.message = "yeah"
        mock_commit_obj.commit.author.raw_data = {"name": "tarek", "date": now_str}
        mock_commit_obj.raw_data = {
            "sha": mock_commit_obj.sha,
            "html_url": mock_commit_obj.html_url,
            "commit": {
                "message": "yeah",
                "author": {"name": "tarek", "date": now_str},
            },
            "files": [{"filename": "config/config.yml"}],
        }
        mock_repo.get_commits.return_value = [mock_commit_obj]
        mock_repo.get_commit.return_value = mock_commit_obj

        return mock_repo

    monkeypatch.setattr(github.github, "get_repo", mock_get_repo)


def test_collect(monkeypatch):
    yesterday = datetime.now() - timedelta(days=1)
    yesterday = yesterday.strftime("%Y-%m-%dT%H:%M:%S")
    mock_github(monkeypatch)
    res = list(collect(yesterday))

    # we're not looking into much details here, we can do this
    # once we start to tweak the filters
    assert len(res) > 0

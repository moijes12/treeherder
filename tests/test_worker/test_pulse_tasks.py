import copy
from threading import local

import pytest
from celery.exceptions import Retry

from treeherder.etl.exceptions import MissingPushError
from treeherder.etl.push import store_push_data
from treeherder.etl.tasks.pulse_tasks import store_pulse_tasks
from treeherder.model.models import Job


def test_retry_missing_revision_succeeds(
    sample_data, sample_push, test_repository, mock_log_parser, failure_classifications, monkeypatch
):
    """
    Ensure that when the missing push exists after a retry, that the job
    is then ingested.
    """
    thread_data = local()
    thread_data.retries = 0
    rs = sample_push[0]
    job = copy.deepcopy(sample_data.pulse_jobs[0])
    job["origin"]["revision"] = rs["revision"]
    job["origin"]["project"] = test_repository.name

    # Mock handle_message inside store_pulse_tasks so we don't hit the network, and can raise MissingPushError on first call
    async def mock_handle_message(message, task_definition=None):
        if thread_data.retries == 0:
            raise MissingPushError("Missing push!")

        return [job]

    monkeypatch.setattr("treeherder.etl.tasks.pulse_tasks.handle_message", mock_handle_message)

    orig_retry = store_pulse_tasks.retry

    def retry_mock(exc=None, countdown=None, *args, **kwargs):
        assert isinstance(exc, MissingPushError)
        thread_data.retries += 1
        store_push_data(test_repository, [rs])
        return orig_retry(exc=exc, countdown=countdown, *args, **kwargs)

    monkeypatch.setattr(store_pulse_tasks, "retry", retry_mock)

    # First attempt should raise Retry because push is missing
    with pytest.raises(Retry):
        store_pulse_tasks.delay(job, "foo", "bar")

    assert thread_data.retries == 1
    assert Job.objects.count() == 0

    # Second attempt should succeed because push is now stored
    store_pulse_tasks.delay(job, "foo", "bar")

    assert Job.objects.count() == 1
    assert Job.objects.values()[0]["guid"] == job["taskId"]
    assert thread_data.retries == 1

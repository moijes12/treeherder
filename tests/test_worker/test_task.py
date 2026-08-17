import zlib
from functools import wraps
from threading import local
from unittest.mock import patch

import jsonschema
import pytest
from celery.exceptions import Retry
from django.db.utils import IntegrityError, OperationalError, ProgrammingError

from treeherder.etl.exceptions import MissingPushError
from treeherder.workers.task import retryable_task

thread_data = local()


def count_retries(f):
    @wraps(f)
    def inner():
        thread_data.retry_count += 1
        f()

    return inner


@pytest.fixture(autouse=True)
def reset_retry_count():
    thread_data.retry_count = -1
    yield


@retryable_task()
def successful_task(x, y):
    return x + y


def test_retryable_task():
    "Test celery executes a task properly"

    result = successful_task.delay(7, 3)
    assert result.wait() == 10


@retryable_task()
@count_retries
def throwing_task_type_error():
    raise TypeError


@retryable_task()
@count_retries
def throwing_task_key_error():
    raise KeyError


@retryable_task()
@count_retries
def throwing_task_value_error():
    raise ValueError


@retryable_task()
@count_retries
def throwing_task_index_error():
    raise IndexError


@retryable_task()
@count_retries
def throwing_task_integrity_error():
    raise IntegrityError


@retryable_task()
@count_retries
def throwing_task_programming_error():
    raise ProgrammingError


@retryable_task()
@count_retries
def throwing_task_unicode_error():
    raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")


@retryable_task()
@count_retries
def throwing_task_validation_error():
    raise jsonschema.ValidationError("Invalid schema")


@retryable_task()
@count_retries
def throwing_task_zlib_error():
    raise zlib.error("zlib compression error")


@pytest.mark.parametrize(
    "task_func, expected_exc",
    [
        (throwing_task_type_error, TypeError),
        (throwing_task_key_error, KeyError),
        (throwing_task_value_error, ValueError),
        (throwing_task_index_error, IndexError),
        (throwing_task_integrity_error, IntegrityError),
        (throwing_task_programming_error, ProgrammingError),
        (throwing_task_unicode_error, UnicodeDecodeError),
        (throwing_task_validation_error, jsonschema.ValidationError),
        (throwing_task_zlib_error, zlib.error),
    ],
)
def test_retryable_task_throws_non_retryable(task_func, expected_exc):
    "Test celery immediately raises an error for non-retryable exceptions without retrying"
    with pytest.raises(expected_exc):
        task_func.delay()
    assert thread_data.retry_count == 0


@retryable_task()
@count_retries
def throwing_task_should_retry():
    raise OperationalError


def test_retryable_task_throws_retry():
    "Test celery retry behavior on retryable exception"

    with pytest.raises(Retry) as e:
        throwing_task_should_retry.delay()
    assert str(e.value) == "Retry in 10s: OperationalError()"
    assert thread_data.retry_count == 0


@retryable_task()
@count_retries
def throwing_missing_push():
    raise MissingPushError("No push found")


@retryable_task()
@count_retries
def throwing_runtime_error():
    raise RuntimeError("Generic runtime error")


@patch("newrelic.agent.notice_error")
def test_newrelic_notified_on_generic_retryable_exception(mock_notice_error):
    "Test that New Relic is notified on generic retryable exceptions"
    with pytest.raises(Retry):
        throwing_runtime_error.delay()

    assert mock_notice_error.call_count == 1
    mock_notice_error.assert_called_with(attributes={"number_of_prior_retries": 0})
    assert thread_data.retry_count == 0


@patch("newrelic.agent.notice_error")
def test_newrelic_not_notified_on_hide_during_retries(mock_notice_error):
    "Test that New Relic is NOT notified on exceptions in HIDE_DURING_RETRIES"
    with pytest.raises(Retry):
        throwing_missing_push.delay()

    assert mock_notice_error.call_count == 0
    assert thread_data.retry_count == 0

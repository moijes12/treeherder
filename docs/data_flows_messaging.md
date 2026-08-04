# Deep-Dive: Data Flows & Messaging Infrastructure

This document provides an exhaustive, low-level blueprint of the data ingestion pipelines, message routing topologies, and analytical flows in Treeherder. It is designed to give maintainers a complete understanding of how RabbitMQ, Celery, and PostgreSQL coordinate to process millions of CI/CD jobs.

---

## 1. The Entry Point: Pulse, Pulse Guardian & RabbitMQ

Mozilla's continuous integration events are carried across **Pulse**, an AMQP 0-9-1 message broker network backed by **RabbitMQ**. To secure this network, access is managed through **Pulse Guardian**, which acts as a gateway proxy authorizing queue bindings, exchanges, and routing keys based on standardized permissions.

```
+-----------------------------------------------------------------------------------+
|                            EXTERNAL MOZILLA CI SYSTEM                             |
|                                                                                   |
|  +-------------------------+                 +---------------------------------+  |
|  |     Taskcluster Engine  |                 |    Mercurial / Git VCS Push     |  |
|  +------------+------------+                 +---------------+-----------------+  |
+---------------|----------------------------------------------|--------------------+
                |                                              |
                | Task Event Payload                           | VCS Commit Hook
                v                                              v
+-----------------------------------------------------------------------------------+
|                             PULSE GUARDIAN (AMQP)                                 |
|                                                                                   |
|   Exchanges:                                                                      |
|     - exchange/taskcluster-queue/v1/tasks                                         |
|     - exchange/hgmo/pushlog                                                       |
|                                                                                   |
|   Routing Keys:                                                                   |
|     - route.try.#                                                                 |
|     - route.autoland.#                                                            |
+------------------------+-------------------------------------+--------------------+
                         |                                     |
                         | AMQP Subscriber SSL                 | AMQP Subscriber SSL
                         v                                     v
+-----------------------------------------------------------------------------------+
|                             TREEHERDER INGESTION ENGINE                           |
|                                                                                   |
|  +-------------------------------------+   +-----------------------------------+  |
|  |       pulse_listener_pushes         |   |       pulse_listener_tasks        |  |
|  |      (Django Command Process)       |   |     (Django Command Process)      |  |
|  +------------------+------------------+   +-----------------+-----------------+  |
+---------------------|----------------------------------------|--------------------+
                      |                                        |
                      | Celery Task Dispatch                   | Celery Task Dispatch
                      v                                        v
+-----------------------------------------------------------------------------------+
|                        INTERNAL RABBITMQ BROKER & QUEUES                          |
|                                                                                   |
|      - store_pulse_pushes                                                         |
|      - store_pulse_jobs                                                           |
+--------------------------------------+--------------------------------------------+
                                       |
                                       | Worker Consumption
                                       v
+-----------------------------------------------------------------------------------+
|                            CELERY STORE_DATA WORKERS                              |
|                                                                                   |
|   - worker_store_pulse_data (Consumes metadata and records to Push/Job tables)    |
+-----------------------------------------------------------------------------------+
```

### Exchanges, Queues, and Routing Keys
Pulse Guardian distributes messages using a topic exchange routing pattern.
*   **VCS Push Exchange:** Typically `exchange/hgmo/pushlog`. Treeherder subscribes to this to detect whenever a developer lands code on an active branch.
*   **Taskcluster Exchange:** Typically `exchange/taskcluster-queue/v1/tasks`. This broadcasts status updates whenever a task is created, runs, fails, or completes.
*   **Filtering:** To avoid overwhelming database write capacity, the subscription filters out repositories not defined in the local repository fixture (`treeherder/model/fixtures/repository.json`). Treeherder only listens to routing keys matching allowed project names (e.g., `route.autoland.#`, `route.mozilla-central.#`, `route.try.#`).

---

## 2. The Ingestion Listening Layer

Treeherder spawns long-lived, supervisor-monitored daemon processes running custom Django management commands inside the container fleet:

1.  **`pulse_listener_pushes`:** Subscribes to VCS events. When a message is received, it extracts the repository URL, revision hash, commit author, push timestamp, and individual changeset details.
2.  **`pulse_listener_tasks`:** Subscribes to Taskcluster events. When a task changes state, it receives a payload with the `taskId`, `runId`, task definitions, platform architecture, and execution details.

### Message Processing and Internal Queueing
The listener processes do not perform database insertions or heavy transformations directly, preventing ingestion lag if the database is under load. Instead, the listeners validate the basic JSON structure, match the project name against registered repositories, and immediately emit an internal Celery task:

*   Push payloads are published to the internal RabbitMQ queue: **`store_pulse_pushes`**
*   Task/Job payloads are published to the internal RabbitMQ queue: **`store_pulse_jobs`**

This isolates external RabbitMQ servers (Pulse) from Treeherder's internal task-processing capacity, allowing internal queues to absorb ingestion spikes.

---

## 3. The Processing & Loader Layer

The Celery worker pool `worker_store_pulse_data` processes the internal queues. This worker executes loader routines found in `treeherder/etl/`:

### VCS Ingestion (`treeherder/etl/push_loader.py` & `treeherder/etl/pushlog.py`)
1.  **Repository Recognition:** The loader inspects the push repository URL and maps it to a database record in the `Repository` table. If the branch uses a wildcard rule (such as `releases/*`), it resolves the active branch using `Repository.resolve_branch`.
2.  **Deduplication & Transaction:** The loader opens a PostgreSQL transaction block (`transaction.atomic()`). It queries existing entries to prevent duplicate `Push` rows for identical commit hashes.
3.  **Changeset Parsing:** Individual commits included in the push are parsed. The loader writes records to the `Commit` table, automatically populating the `search_vector` field for fast commit-message searching.

### Task/Job Ingestion (`treeherder/etl/job_loader.py`)
1.  **Signature Matching:** Every task carries a set of parameters (platform, OS, architecture, job type, subtest suite, option list). The loader calculates a SHA-1 hash of these parameters using `OptionCollection.calculate_hash()` and references/creates a `ReferenceDataSignatures` record.
2.  **Foreign Key Resolution:** Platforms, Job Types, and Job Groups are mapped to their respective tables (`BuildPlatform`, `MachinePlatform`, `JobType`, `JobGroup`). If a platform option exists, the loader queries/populates the cached option collection map.
3.  **Upsert Operations:** The job record is inserted into the `Job` table with unique constraint mapping on its Taskcluster GUID. If the job status updates (e.g. from `running` to `completed`), the loader performs an update on the state, start/end times, and execution result.

---

## 4. The Log Parsing & Analytical Flow

Once a task's state changes to `completed` with a non-success status, or when performance tests conclude, Treeherder triggers downstream analysis.

```
                    [Job Status = COMPLETED]
                               |
                               | Dispatches
                               v
               +---------------+---------------+
               |      Log Parser Celery Task   |
               +---------------+---------------+
                               |
                 Parses raw stream from S3
                               v
               +---------------+---------------+
               |    Unstructured Log Parsing   |
               |             (S3)              |
               +---------------+---------------+
                               |
                               | Line Pattern Heuristics
                               v
               +---------------+---------------+
               |       FailureLine Extraction  |
               +---------------+---------------+
                               |
            Matches existing classified signatures
                               v
               +---------------+---------------+
               |     ClassifiedFailure Match   |
               +---------------+---------------+
                               |
          Updates bug notes / alerts sheriffs in UI
                               v
               +---------------+---------------+
               |      Bugscache / BugJobMap    |
               +-------------------------------+
```

### Log Parser Task Dispatch
The loaders dispatch log parsing Celery tasks asynchronously. Depending on the repository type (e.g., highly-active `try` vs. release branch), tasks are routed to different priority queues:
*   `parse_logs_try`
*   `parse_logs_integration` (e.g. `autoland`)
*   `parse_logs_trunk` (e.g. `mozilla-central`)

This routing logic is defined dynamically inside `treeherder/etl/jobs.py` based on the active repository's volume characteristics.

### Error Analysis & FailureLine Recording
1.  **Stream Fetching:** The Celery worker fetches the raw task log stream directly from Taskcluster's S3 buckets (or cache), processing it line-by-line without buffering the entire multi-gigabyte log in memory.
2.  **Structured Parsing (mozlog):** If the log is structured, the parser decodes individual JSON objects, extracting fields like `action`, `test`, `status`, `expected`, `message`, and `stack`.
3.  **Unstructured Parsing:** For plain-text logs, regex heuristics search for common test failures (e.g. `TEST-UNEXPECTED-FAIL`, `CRASH`, `TIMEOUT`).
4.  **Database Storage:** Discovered errors are stored as `TextLogError` and detailed as `FailureLine` records. They are linked together via `TextLogErrorMetadata` to enable rapid UI queries.
5.  **Deduplication & Classification:**
    *   The newly recorded `FailureLine` is compared against existing known `ClassifiedFailure` signatures.
    *   If a match is found, the system assigns the matching classification ID to the `best_classification` foreign key on the `FailureLine`.
    *   If a Bugzilla bug is associated with the classified failure, the system links the job to the bug in the `BugJobMap` table, allowing the UI to show the job as "automatically classified" under that bug.

### Performance Parsing (Perfherder Ingestion)
If the log indicates the presence of performance benchmark data:
1.  The parser identifies the `PERFORMANCE_DATA` or `PERFHERDER_DATA` JSON payload in the log stream.
2.  It extracts the metric name, test suite, and raw numerical performance points.
3.  The performance points are written to performance data tables, and a background task runs statistical calculations (e.g. comparing the run against a rolling average standard deviation).
4.  If a significant deviation (regression) is detected, the system generates an entry in the performance alerts table, notifying performance engineers.

---

## 5. Kombu & Celery Architectural Configuration

Treeherder uses **Kombu** as Django's messaging abstraction layer to configure Celery queues and routing topologies.

### Task Routing Settings
In `treeherder/config/settings.py`, Celery queues are defined under `CELERY_TASK_QUEUES`:
```python
CELERY_TASK_QUEUES = {
    'store_pulse_pushes': {
        'binding_key': 'store_pulse_pushes',
    },
    'store_pulse_jobs': {
        'binding_key': 'store_pulse_jobs',
    },
    'parse_logs_integration': {
        'binding_key': 'parse_logs_integration',
    },
    # ... additional parsing and alerting queues
}
```

### Celery Testing Configuration
To allow developer environments and test suites to run without requiring a live, external RabbitMQ broker container:
*   **The In-Memory Mock Broker:** In `treeherder/config/settings.py`, the `CELERY_BROKER_URL` can be overridden to `'memory://'`. Celery then simulates AMQP delivery inside local RAM, simplifying pytest setup.
*   **Eager Mode (`CELERY_TASK_ALWAYS_EAGER`):** In local development, running commands with `--enable-eager-celery` sets `CELERY_TASK_ALWAYS_EAGER = True`. This forces all Celery tasks to run synchronously in the main thread immediately upon dispatch, bypassing the RabbitMQ queues entirely. This is highly useful for stepping through ingestion code with a debugger.

### Concurrency and Load Boundaries
To prevent database connection pool exhaustion and disk write bottlenecks, workers are strictly regulated:
*   `--concurrency 1` is recommended for ingestion-heavy workers in development to ensure sequential, predictable load.
*   Worker prefetch limits (`CELERY_WORKER_PREFETCH_MULTIPLIER`) are tuned to prevent a single worker from hogging hundreds of tasks while other workers sit idle during high-volume pushes on the `try` repository.

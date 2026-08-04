# System Architecture & Component Interaction Guide

This document provides a detailed overview of the system architecture of Mozilla Treeherder. It describes why the project exists, its high-level and low-level component interactions, database schemas, frontend architecture, and interactions with external Mozilla CI/CD services.

---

## 🎯 Project Purpose & Requirements

### Why Treeherder is Needed
In a massive software project like Firefox, hundreds of developers submit commits daily across multiple repositories (such as `mozilla-central`, `autoland`, and `try`). Each push triggers thousands of automated builds, regression checks, and test suites across diverse operating systems and hardware configurations.

Without a centralized, high-throughput dashboard, it is impossible to:
1.  **Sheriff the Trees:** Identify whether a build failure was caused by a newly-landed patch (requiring a backout) or is an intermittent/flaky test.
2.  **Monitor Performance:** Spot performance regressions (e.g., page load delays or memory usage spikes) introduced by a commit.
3.  **Audit CI Health:** Analyze test run durations, resource consumption, and failure frequencies.

### Target Users
*   **Code Sheriffs:** Full-time quality engineers who monitor Treeherder to keep integration branches "green" by classifying failures and backing out broken commits.
*   **Firefox Developers:** View the status of their patches (especially on the `try` branch) and debug failures using parsed log extracts.
*   **Performance Engineers:** Monitor performance benchmarks and regressions (using the Perfherder component).

### Requirements

#### Functional Requirements
*   **Real-time Ingestion:** Ingest push and job events from Taskcluster and Mercurial/Git with sub-second latency.
*   **Failure Classification:** Allow sheriffs to map failures to existing Bugzilla bugs or create new bugs directly from the UI.
*   **Log Parsing:** Parse text logs of failed runs to isolate call stacks, failure messages, and memory dumps, exposing them as `FailureLines`.
*   **Performance Tracking:** Extract and store performance metrics, group them by test suites, and trigger statistical alerts for performance anomalies.

#### Non-Functional Requirements
*   **High Scalability:** Handle millions of jobs per week and process gigabytes of log lines daily.
*   **Low Latency UI:** Serve push summaries and job statuses with sub-second query execution times, even on branches containing thousands of active builds.
*   **Zero-Downtime Deployments:** Ensure database migrations and API schemas are fully backwards-compatible so that rolling updates do not break active clients or sheriffs.
*   **Data Retention/Pruning:** Automatically purge old jobs and log parsing artifacts (via data cycling) to control Postgres storage costs.

---

## 🏗️ High-Level System Architecture

The following diagram illustrates how Treeherder interacts with the wider Mozilla ecosystem:

```
                  +----------------------------------------------+
                  |              Mozilla Developer               |
                  +----------------------+-----------------------+
                                         | Push
                                         v
+------------------+      +--------------+--------------+      +-------------------+
|     Bugzilla     |      |       Autoland / HG         |      |    Taskcluster    |
+--------+---------+      +--------------+--------------+      +---------+---------+
         ^                               |                               |
         | Sync Bugs                     | Ingestion Event               | Job Results & Logs
         v                               v                               v
+--------+---------+      +--------------+--------------+      +---------+---------+
|  Treeherder REST |      |   Pulse (RabbitMQ Broker)   |      |   Taskcluster Logs|
|    Django API    |      +--------------+--------------+      +---------+---------+
+--------+---------+                     |                               |
         ^                               | Subscribes                    | Fetch & Parse
         | Reads / Writes                v                               |
+--------+---------+      +--------------+--------------+                |
|  React Frontend  |      |   Pulse Ingestion Listeners |----------------+
|    (Zustand)     |      +--------------+--------------+
+------------------+                     |
                                         | Schedules Tasks
                                         v
                          +--------------+--------------+
                          |   Celery Queue & Workers    |
                          +--------------+--------------+
                                         |
                                         | Read / Write State
                                         v
                          +--------------+--------------+
                          |  PostgreSQL / Redis Cache   |
                          +-----------------------------+
```

---

## ⚙️ Django Backend Applications

Treeherder is structured as a modular Django monolith. Below is a breakdown of the core backend applications under the `treeherder/` directory:

### 1. `treeherder/model/` (The Database Layer)
*   **Role:** Acts as the central domain layer, housing all relational database models, customized Django QuerySets (such as `FailuresQuerySet`), and database migration schemas.
*   **Key Files:**
    *   `models.py`: Defines core business logic structures (`Push`, `Commit`, `Job`, `FailureLine`, `ClassifiedFailure`, `TextLogError`, `BugJobMap`).
    *   `error_summary.py`: Implements heuristics to group and suggest matching Bugzilla bugs for specific test failures.
    *   `fixtures/`: Seed data for repositories (`repository.json`), branch paths (`repository_branch.json`), and failure classifications (`failure_classification.json`).

### 2. `treeherder/etl/` (Data Ingestion Pipeline)
*   **Role:** Extracts, transforms, and loads metadata from Taskcluster and repository pushes.
*   **Key Files:**
    *   `job_loader.py` & `push_loader.py`: Reconcile incoming JSON payloads into database objects.
    *   `management/commands/`: Hosts persistent CLI processes such as `pulse_listener_pushes` and `pulse_listener_tasks`, which run continuously inside Docker to ingest events.
    *   `artifact.py`: Fetches and processes external structured task artifacts (e.g. structured logs or JSON outputs) from Taskcluster.

### 3. `treeherder/webapp/` (The REST API Layer)
*   **Role:** Exposes Treeherder's data via a high-performance REST API built on Django REST Framework (DRF).
*   **Key Files:**
    *   `api/jobs.py`, `api/push.py`, `api/bug.py`: Controller views handling UI data queries.
    *   `api/serializers.py` & `api/performance_serializers.py`: Transform complex model instances into highly optimized JSON structures.
    *   `api/permissions.py` & `api/auth.py`: Manage role-based access control, checking if a client is authorized to classify a job or file a bug.

### 4. `treeherder/perf/` & `treeherder/perfalert/` (Perfherder)
*   **Role:** Manages performance ingestion and anomaly alerting.
*   **Key Files:**
    *   `tasks.py` & `alerts.py`: Process parsed performance log numbers, calculate standard deviations, and trigger alerts on sudden regressions.
    *   `models.py`: Defines `PerfSignature`, `PerfAlert`, and other statistical configuration tables.

### 5. `treeherder/log_parser/` (Failure Log Analytics)
*   **Role:** Asynchronously parses raw unstructured execution logs to isolate the exact cause of test crashes or suite timeouts.
*   **Key Files:**
    *   `tasks.py`: Celery tasks triggered upon a job transition to `completed`.
    *   `intermittents.py`: Evaluates whether a test failure matches a known intermittent footprint.

### 6. `treeherder/auth/` (Authentication)
*   **Role:** Manages secure Single Sign-On (SSO) login callback handlers, GITHUB_TOKEN verification, and active Django user sessions.

---

## 💻 React Frontend Architecture

The Treeherder frontend is a modern, single-page React application hosted under the `ui/` directory.

### Key Characteristics
*   **Asset Bundler:** Uses **RSPack** for ultra-fast, incremental compilation and hot module reloading.
*   **Build Commands:**
    *   `pnpm start:local` (local proxy development on port 5000)
    *   `pnpm start:stage` (safely tests with staging data)
    *   `pnpm build` (generates minified production assets in `.build/`)

### State Management (Zustand Stores)
Rather than relying on Redux, the application uses **Zustand** for lightweight, highly-decoupled reactive state management:
*   `pushesStore.js`: Manages the currently selected repository branch, lists of pushed commits, and active filter states.
*   `selectedJobStore.js`: Coordinates the currently selected job, its associated failure logs, and details in the lower drawer.
*   `pinnedJobsStore.js`: Allows sheriffs to pin multiple failures together to perform batch actions (e.g., classifying 10 intermittent failures under one bug).
*   `notificationStore.js`: Manages global banner alerts and toast notifications for user interactions.

---

## 🗄️ Relational Database Schema & Core Tables

The Postgres database is the source of truth for the entire pipeline. The diagram below shows the core relationships between the principal tables:

```
  +------------------+
  |    Repository    |
  +--------+---------+
           | 1
           |
           | N
  +--------+---------+
  |       Push       +-------------------------+
  +--------+---------+ 1                       | 1
           |                                   |
           | 1                                 |
           |                                   | N
           | N                                 |
  +--------+---------+                         |
  |      Commit      |                         |
  +------------------+                         |
                                               |
  +---------------------------+                |
  |  ReferenceDataSignatures  |                |
  +------------+--------------+                |
               | 1                             |
               |                               |
               | N                             |
  +------------+--------------+                |
  |            Job            |<---------------+
  +------+------------+-------+ N
         | 1          | 1
         |            |
         |            +-------------------------+
         | N                                    | N
  +------+------------+                +--------+---------+
  |    TextLogError   |                |    BugJobMap     |
  +------+------------+                +--------+---------+
         | 1                                    | N
         |                                      |
         | 1                                    | 1
  +------+------------+                +--------+---------+
  |TextLogErrorMetadata|               |    Bugscache     |
  +------+------------+                +--------+---------+
         | 1
         |
         | N
  +------+------------+
  |    FailureLine    |
  +-------------------+
```

### Table Details & Attributes

#### 1. `push`
*   **Represents:** A single push or landing action on a repository.
*   **Columns:** `id`, `repository_id`, `revision` (SHA hash), `author`, `time`, `branch`.

#### 2. `commit`
*   **Represents:** Individual changesets belonging to a push.
*   **Columns:** `id`, `push_id`, `revision`, `author`, `comments` (the commit message), `search_vector` (GIN index for commit search).

#### 3. `job`
*   **Represents:** A build task, run, or test suite.
*   **Columns:** `id`, `repository_id`, `guid` (UUID), `signature_id`, `build_platform_id`, `machine_platform_id`, `failure_classification_id`, `result` (e.g., SUCCESS, FAILURE), `state` (e.g., COMPLETED, RUNNING, PENDING), `tier` (1, 2, or 3).

#### 4. `text_log_error`
*   **Represents:** A parsed raw error line isolated from unstructured logs.
*   **Columns:** `id`, `job_id`, `line` (the raw text error), `line_number`, `new_failure`.

#### 5. `text_log_error_metadata`
*   **Represents:** High-performance mapping bridging `TextLogError` and `FailureLine`. It also hosts sheriff confirmation settings.
*   **Columns:** `text_log_error_id` (PK), `failure_line_id`, `best_classification_id`, `best_is_verified` (Boolean).

#### 6. `failure_line`
*   **Represents:** Structured error details extracted from standardized logger outputs (e.g., `mozlog`).
*   **Columns:** `id`, `job_guid`, `repository_id`, `action` (e.g., `test_result`), `line`, `test` (test file path), `status` (e.g., `FAIL`), `expected` (e.g., `PASS`), `message` (error message), `stack`.

#### 7. `bugscache`
*   **Represents:** A local cache of active Bugzilla tickets to avoid continuous external API querying.
*   **Columns:** `id`, `bugzilla_id`, `status` (e.g., NEW, RESOLVED), `resolution`, `summary`, `crash_signature`, `modified`.

#### 8. `bug_job_map`
*   **Represents:** The join table recording exactly which job failure was associated with which Bugzilla bug (classified manually by a sheriff or automatically).
*   **Columns:** `id`, `job_id`, `bug_id`, `created`, `user_id` (null if autoclassified).

---

## 🔌 Integration with Mozilla Services

Treeherder does not exist in isolation; it integrates tightly with other services:

### 1. Taskcluster
*   **Protocol:** AMQP (via Pulse) + HTTPS REST API.
*   **Interaction:**
    *   When a Taskcluster worker completes a task, it emits a message to the Pulse exchange.
    *   Treeherder listens to this event, grabs the metadata, and extracts the S3-hosted log URLs.
    *   Treeherder's log parser reads the S3 stream directly to find errors.

### 2. Pulse (Pulse Guardian)
*   **Protocol:** AMQP with SSL.
*   **Interaction:**
    *   Pulse Guardian is Mozilla's secured RabbitMQ broker system.
    *   Treeherder spawns long-lived consumer commands (`pulse_listener_pushes` and `pulse_listener_tasks`) which subscribe to Pulse exchanges, loading tasks on demand and feeding them into Celery queues.

### 3. Bugzilla (bugzilla.mozilla.org)
*   **Protocol:** HTTPS JSON-RPC / REST.
*   **Interaction:**
    *   Treeherder caches bug status inside `Bugscache` by periodically polling Bugzilla.
    *   When a sheriff classifies a failure inside the UI, Treeherder posts a structured comment on Bugzilla detailing the failure, including a link to the log and the repository revision.

### 4. PerfCompare & Perfherder
*   **Protocol:** HTTPS REST API.
*   **Interaction:**
    *   PerfCompare compares performance benchmarks across two revisions. Treeherder acts as the data repository, exposing standardized performance points which PerfCompare can fetch and plot side-by-side.

---

## 🛠️ Performance & Scalability Considerations

To ensure high responsiveness under high loads, Treeherder implements the following patterns:

1.  **Prefix & GIN Indexes:** Standard B-Tree indexes struggle on text paths and crash signatures. PostgreSQL GIN trigram indexes (`SearchVectorField`) are extensively used for rapid pattern matching on crash signatures and commit text searches.
2.  **LocMem Caching:** Frequently fetched option collections and repository branch mappings are aggressively cached in Redis or LocMem to avoid redundant table scans on hot endpoints.
3.  **Celery Concurrency Boundaries:** Log parsing is heavily throttled and isolated from task metadata storage to prevent logging lag from stalling push visibility.

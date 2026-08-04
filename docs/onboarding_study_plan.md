# Senior Engineer Onboarding & Maintainer Study Plan

Welcome to the Mozilla Treeherder team! This study plan is designed to help you transition from a Senior Engineer into a highly capable full-time maintainer of the `mozilla/treeherder` repository.

Treeherder is at the absolute center of Mozilla's continuous integration and development flow. It processes millions of tasks, ingests terabytes of logs, parses test results, and alerts on performance regressions. As a maintainer, you will not only write code but also collaborate closely with Code Sheriffs, Performance Engineers, and Release Engineering.

---

## 📅 The 6-Week Learning Path

### Week 1: Environment, Foundations, and First Commit
**Objective:** Set up your local environment, understand the key architecture components, and successfully run the full test suite.

*   **Reading Assignments:**
    *   `README.md` and `docs/installation.md`
    *   `docs/backend_tasks.md` and `docs/testing.md`
    *   System Architecture & Interactions Guide (`docs/architecture_overview.md`)
*   **Key Concept Focus:**
    *   How Docker Compose coordinates the `postgres`, `redis`, `rabbitmq`, `backend`, and `frontend` containers.
    *   The separation of the local standalone frontend server (port 5000) and the production-build Django server (port 8000).
*   **Practical Exercises:**
    1.  Install pre-commit hooks: `pre_commit install`.
    2.  Spin up the environment: `docker compose up --build`.
    3.  Enter the backend container and run tests:
        ```bash
        docker compose run backend bash
        pytest tests/etl/test_job_loader.py
        ```
    4.  Verify frontend linting and formatting:
        ```bash
        pnpm run lint
        pnpm run format
        ```
*   **Deliverable:** Submit a "Good First Bug" PR (e.g., fixing a simple layout issue or adding a small unit test) and walk it through our CI pipeline.

---

### Week 2: Data Ingestion & ETL (Pulse & Taskcluster)
**Objective:** Understand how data flows from task completion inside Taskcluster to Treeherder's Postgres tables.

*   **Reading Assignments:**
    *   `docs/infrastructure/data_ingestion.md`
    *   `docs/pulseload.md`
*   **Key Concept Focus:**
    *   Pulse Guardian queues, RabbitMQ broker, and Celery worker exchanges.
    *   The `treeherder/etl/` directory structure, specifically `job_loader.py`, `push_loader.py`, and commands in `treeherder/etl/management/commands/`.
    *   The `Repository` and `RepositoryBranch` models, and how wildcard matching resolves branches.
*   **Practical Exercises:**
    1.  Configure a Pulse local ingestion queue as documented in `docs/pulseload.md`.
    2.  Ingest a single push manually using `manage.py`:
        ```bash
        docker compose exec backend ./manage.py ingest push -p autoland -r <revision> -a --enable-eager-celery
        ```
    3.  Inspect the local Postgres database (`treeherder` database on port 5432) to see how records are added to `push`, `commit`, `job`, and `failure_line` tables.
*   **Deliverable:** Implement or modify an ETL-related unit test under `tests/etl/` ensuring correct handling of push payloads.

---

### Week 3: Log Parsing & Classification System
**Objective:** Master the structured and unstructured log parsing systems, which extract error failure lines and performance data.

*   **Reading Assignments:**
    *   `docs/submitting_data.md`
    *   `treeherder/log_parser/` codebase
*   **Key Concept Focus:**
    *   How `FailureLine`, `ClassifiedFailure`, `TextLogError`, and `TextLogErrorMetadata` tables map log errors to Bugzilla bugs.
    *   How Treeherder identifies intermittent failures and suggests classifications.
    *   How performance data is extracted via JSON patterns in logs (PERFORMANCE_DATA / PERFHERDER_DATA).
*   **Practical Exercises:**
    1.  Read `treeherder/model/error_summary.py` and trace how `get_useful_search_results` suggestions are built.
    2.  Write a custom python script or test that processes a raw mock test-suite log and extracts `FailureLines`.
    3.  Inspect how `JobNote` creates/updates failure classifications and links them to Bugscache.
*   **Deliverable:** Enhance log parsing heuristics or fix a bug in the intermittent failures commenter tool.

---

### Week 4: Frontend Development & State Management
**Objective:** Become proficient in Treeherder's React UI, its state management patterns, and interactive tools.

*   **Reading Assignments:**
    *   `ui/README.md` (if exists) or UI directories.
    *   State management with Zustand: Analyze `ui/shared/stores/`.
*   **Key Concept Focus:**
    *   How `selectedJobStore`, `pushesStore`, and `pinnedJobsStore` coordinate UI state without excessive prop drilling.
    *   PollyJS in frontend tests for API recording and replay mocking.
    *   RSPack-based asset compilation.
*   **Practical Exercises:**
    1.  Create a custom React component inside `ui/shared/` or modify an existing view (e.g., job details drawer or push list).
    2.  Run frontend Jest unit tests:
        ```bash
        pnpm test
        ```
    3.  Practice using the Stage proxy (`pnpm start:stage`) to safely test your React frontend modifications against the staging database.
*   **Deliverable:** Implement a frontend UI enhancement (e.g., adding an option to filter jobs or improving the display of log snippets) with comprehensive test coverage.

---

### Week 5: Performance Data (Perfherder & PerfCompare)
**Objective:** Learn how Treeherder processes, alerts, and compares performance metrics across commits (PerfCompare).

*   **Reading Assignments:**
    *   `treeherder/perf/` codebase and settings.
    *   Understanding mozilla/perfcompare and taskcluster-produced performance alerts.
*   **Key Concept Focus:**
    *   Performance alert models, statistical anomaly detection criteria (sheriffing criteria).
    *   How performance logs are parsed and ingested into `perf_signature` and `perf_data` points.
    *   Interactivity between Treeherder and perfcompare for analyzing regression graphs.
*   **Practical Exercises:**
    1.  Review alert-triggering tasks and methods inside `treeherder/perf/tasks.py`.
    2.  Simulate a performance regression ingestion locally and verify if an alert is generated.
*   **Deliverable:** Build/Refactor a unit test inside `tests/perf/` validating the regression alert generation logic.

---

### Week 6: System Administration, On-Call, & Sheriff Interaction
**Objective:** Learn how Treeherder is managed in production, how to troubleshoot ingestion lags, and how to support the Code Sheriffs.

*   **Reading Assignments:**
    *   `docs/infrastructure/administration.md`
    *   `docs/infrastructure/troubleshooting.md`
    *   `docs/data_cycling.md`
*   **Key Concept Focus:**
    *   Data retention rules: Pruning old jobs using `manage.py cycle_data`.
    *   Pulse queue lag diagnosis via RabbitMQ management dashboard and Celery worker metrics.
    *   Security group rules, Django middleware, and CORS configuration.
*   **Practical Exercises:**
    1.  Familiarize yourself with the staging instance (`treeherder.allizom.org`) and how deployment works (WhatsDeployed).
    2.  Review the Bugzilla integration API used to automatically post bug comments when sheriffs classify failures.
*   **Deliverable:** Shadow a senior maintainer on-call, reviewing incoming bug reports, triaging infrastructure issues, and responding to Slack/Matrix queries in `#treeherder`.

---

## 🛠️ Onboarding Code Challenges

To solidify your understanding of Treeherder's internals, complete these three progressive coding challenges during your onboarding:

### Challenge 1: The Branch Wildcard Matcher
*   **Goal:** Write a robust test suite that covers all edge cases of branch resolution in `Repository.resolve_branch`.
*   **Instructions:**
    *   Create a set of dummy `Repository` and `RepositoryBranch` records.
    *   Test exact match, trailing wildcards (e.g. `releases/lts-*`), overlap rules, and error handling when duplicate matches are resolved.

### Challenge 2: Custom Log Parser Heuristics
*   **Goal:** Add a new parser rule to identify custom build timeout indicators in unstructured task logs.
*   **Instructions:**
    *   Incorporate your pattern matcher into `treeherder/log_parser/`.
    *   Ensure that when the pattern is hit, it records a `FailureLine` with action `truncated` and status `TIMEOUT`.

### Challenge 3: Ingestion Queue Lag Simulator
*   **Goal:** Write a Django management command to mock high-volume Celery message ingestion and monitor queue health/performance metrics.
*   **Instructions:**
    *   Create a command `simulate_pulse_load` that publishes fake task payloads to RabbitMQ.
    *   Measure processing latency per job and log metrics suitable for Datadog or New Relic.

---

## 🤝 Maintainer Expectations & Workflow

As a full-time maintainer, you will represent the backbone of Mozilla’s development velocity. Here are the core workflows you must own:

1.  **Sheriff First Responder:**
    *   Code Sheriffs rely on Treeherder to keep Mozilla's integration branches green.
    *   If Treeherder ingestion experiences lag or UI crashes, prioritize it immediately. Sheriff tools must be highly available.
2.  **Pull Request Reviews:**
    *   Enforce strict style guides (Ruff, Biome, Markdownlint).
    *   Insist on tests (using the Pytest factory fixture pattern on the backend and Jest on the frontend).
    *   Ensure API schema migrations are backwards-compatible so they don't break the frontend during zero-downtime rolling upgrades.
3.  **Performance & Scaling Awareness:**
    *   With millions of jobs stored, Postgres indexes are critical. Always check query plans (using `django-debug-toolbar` locally) before adding new foreign key lookups or complicated filter clauses.
    *   Never perform unbounded queries on the `job` or `failure_line` tables.

*Welcome to the team! We are thrilled to have you build the future of Mozilla's developer experience.*

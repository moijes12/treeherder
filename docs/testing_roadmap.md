# Treeherder Testing Audit and Roadmap

This document provides an audit of the current testing state of the Treeherder project and outlines a phased roadmap to improve test coverage, reliability, and developer experience.

## 1. Current Test Approach and Coverage

### 1.1 Frontend (JavaScript/React)

- **Framework:** [Jest](https://jestjs.io/) with [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/).
- **Mocking:** `fetch-mock` for unit tests; [PollyJS](https://netflix.github.io/pollyjs/) for integration tests to record/replay API interactions.
- **Coverage Target:** The `.codecov.yml` specifies a 40% target for the UI. Recent runs show coverage varies significantly across modules, with some core stores and components below 50%.
- **Location:** Tests are located in `tests/ui/`, mirroring the `ui/` directory structure.

### 1.2 Backend (Python/Django)

- **Framework:** [Pytest](https://pytest.org/) with `pytest-django`.
- **Environment:** [Tox](https://tox.wiki/) is used to manage test environments and run tests across different segments (general, perf, telemetry, frontend).
- **Services:** Relies on Docker Compose to provide PostgreSQL, Redis, and RabbitMQ.
- **Coverage Location:** Backend coverage is currently reported via Codecov from the `python-tests-*` CircleCI jobs.
- **Location:** Tests are located in the `tests/` directory.

### 1.3 Continuous Integration

- **Platform:** CircleCI.
- **Workflow:** Parallel jobs for linting (Biome, Ruff, Markdownlint) and testing (JS unit tests, multiple Python test shards).

---

## 2. Identified Gaps and Weaknesses

### 2.1 Developer Experience & Tooling

- **Dependency Conflicts:** There are version mismatches in Python requirements (e.g., `urllib3` conflict between `common.txt` and `dev.txt`), making local environment setup outside of Docker fragile.
- **Local Test Complexity:** Running backend tests locally requires a complex dance of Docker services and environment variables, which can be a barrier for new contributors.

### 2.2 Frontend Coverage Gaps

- **Zustand Stores:** Core state management stores like `selectedJobStore.js` (~60%) and `pinnedJobsStore.js` (~53%) have significant untested logic, especially around edge cases in data ingestion.
- **Complex Components:** Major UI components such as `JobArtifacts.jsx` (~50%), `RevisionInformation.jsx` (~42%), and `TaskclusterCallback.jsx` (~15%) have low coverage.
- **Stale Integration Data:** PollyJS recordings for integration tests can become stale as API responses evolve, leading to "false green" tests or difficult-to-debug failures.

### 2.3 Backend Coverage Gaps

- **ETL Logic:** While many ETL processes are tested, the complexity of Taskcluster and Pulse interactions means many failure modes are only covered by basic mocks.
- **Database Layer Tests:** Many model methods in `treeherder/model/models.py` lack direct unit tests, relying instead on high-level API tests.
- **Celery Worker Reliability:** Testing of Celery tasks in `treeherder/workers/` is often done in "eager" mode, which misses issues related to serialization or distributed state.
- **Performance Testing:** Performance tests exist but are sharded and slow, leading to them often being skipped during local development.

---

## 3. Enhancement through Testing Types (Phased Approach)

### 3.1 Unit Tests (Phase 1-2)

- **Frontend:** Isolated logic in Zustand stores and UI helpers.
- **Backend:** Direct testing of Django model methods, service layer functions, and ETL transformation logic without external side effects.

### 3.2 Integration Tests (Phase 2-4)

- **Frontend-Backend:** Verifying components interact correctly with backend APIs (using PollyJS).
- **Service Integration:** Verifying Treeherder interacts correctly with mock Taskcluster/Bugzilla APIs using the `responses` library.
- **Celery Integration:** Moving beyond "eager" mode to test tasks in a real RabbitMQ/Redis environment in specific CI shards.

### 3.3 End-to-End (E2E) and Specialized Tests (Phase 4)

- **User Journeys:** Using Puppeteer/Playwright to verify critical flows (Login -> Filter -> Job Details).
- **Accessibility:** Automated `axe-core` checks.
- **Performance Regression:** Ensuring ingestion throughput (jobs/sec) doesn't degrade.

---

## 4. Thresholds and Guardrails

To maintain quality, we will implement the following guardrails:

### 4.1 Development

- **Pre-commit Hooks:** Mandatory ruff, black, biome, and markdownlint checks.
- **Local Coverage Reports:** Developers are encouraged to run `pytest --cov` or `pnpm test:coverage` before submitting PRs.

### 4.2 Testing (CI)

- **Codecov Thresholds:** Fail PRs if coverage drops by more than 1% or if new code is below 40% (current) / 60% (future target).
- **Required Status Checks:** JS and Python test suites must pass 100% on master and PR branches.

### 4.3 Production

- **Error Rate Monitoring:** Use Sentry/New Relic to track 5xx errors and JS exceptions.
- **Canary Health Checks:** Automated validation of key endpoints during deployment.

---

## 5. Production Canaries (GCP Strategy)

Given Treeherder's deployment to GCP (via GAR and potentially GKE or Cloud Run), canaries provide a safe way to roll out changes.

- **Traffic Splitting:** Use GKE Ingress or Cloud Run traffic management to route 5-10% of traffic to the "prototype" or "new-release" version.
- **Automated Rollbacks:** Monitor canary health (HTTP 200 rates, latency) and automatically revert traffic if regressions are detected.
- **Staged Rollout:** Gradually increase traffic (10% -> 25% -> 50% -> 100%) after verification at each stage.

---

## 6. Phased Roadmap

The following phases are designed to be broken down into individual Bugzilla tickets.

### Phase 1: Foundation and Tooling Stability

*Goal: Ensure every developer can run the full suite easily and reliably.*

1. **Reconcile Python Dependencies:** Standardize `urllib3` and other conflicting packages across `requirements/*.txt` files.
2. **Improve Local Test Bootstrapping:** Enhance `tests/README.md` or provide a script to automate the setup of the test database and cache for local Pytest runs.
3. **Audit Stale PollyJS Recordings:** Identify and refresh integration test recordings that haven't been updated in over 6 months.

### Phase 2: Core State and Logic Coverage

*Goal: Secure the "brain" of the application.*

1. **Backend Model Tests:** Add unit tests for critical methods in `treeherder/model/models.py` and `treeherder/perf/models.py`.
2. **ETL Failure Mode Coverage:** Implement unit tests for `treeherder/etl/` that specifically simulate failures in external APIs (Taskcluster, Bugzilla) and Pulse message drops.
3. **Store Coverage (Zustand):** Increase coverage of `selectedJobStore.js` and `pushesStore.js` to >80%.
4. **Helper Utilities:** Target 100% coverage for critical helpers in `ui/helpers/` (e.g., `taskcluster.js`, `location.js`).

### Phase 3: High-Impact Components and Workers

*Goal: Fortify the most used parts of the Treeherder dashboard and async workers.*

1. **Celery Task Verification:** Increase testing depth for `treeherder/workers/`, ensuring tasks are verified for serialization and error handling.
2. **Job View Fortification:** Increase coverage for `JobArtifacts.jsx` and `JobInfo.jsx`.
3. **Revision Details:** Focus on `RevisionInformation.jsx` and `RevisionLinkify.jsx` to ensure commit data is always rendered correctly.
4. **Auth Callback Reliability:** Rewrite or expand tests for `TaskclusterCallback.jsx`.

### Phase 4: Integration and End-to-End Depth

*Goal: Catch regressions that unit tests miss.*

1. **Expanded Integration Suite:** Add PollyJS-backed integration tests for the "Perfherder" views.
2. **Pulse/Taskcluster Simulation:** Improve backend test fixtures for Pulse consumers to better simulate real-world data lag and malformed payloads.
3. **Performance Test Optimization:** Audit and optimize existing performance tests in `tests/perf/` to reduce their runtime.
4. **Accessibility Testing:** Integrate automated accessibility checks (e.g., `jest-axe`) into the frontend test suite.

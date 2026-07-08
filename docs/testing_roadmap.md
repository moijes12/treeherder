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
- **Performance Testing:** Performance tests exist but are sharded and slow, leading to them often being skipped during local development.

---

## 3. Phased Roadmap

The following phases are designed to be broken down into individual Bugzilla tickets.

### Phase 1: Foundation and Tooling Stability

*Goal: Ensure every developer can run the full suite easily and reliably.*

1. **Reconcile Python Dependencies:** Standardize `urllib3` and other conflicting packages across `requirements/*.txt` files.
2. **Improve Local Test Bootstrapping:** Enhance `tests/README.md` or provide a script to automate the setup of the test database and cache for local Pytest runs.
3. **Audit Stale PollyJS Recordings:** Identify and refresh integration test recordings that haven't been updated in over 6 months.

### Phase 2: Core State and Logic Coverage

*Goal: Secure the "brain" of the application.*

1. **Store Coverage (Zustand):** Increase coverage of `selectedJobStore.js` and `pushesStore.js` to >80%, focusing on error handling during fetch failures.
2. **Helper Utilities:** Target 100% coverage for critical helpers in `ui/helpers/` (e.g., `taskcluster.js`, `location.js`).
3. **Backend Utils:** Increase coverage for common utilities in `treeherder/utils/`.
4. **ETL Failure Mode Coverage:** Implement unit tests for `treeherder/etl/` that specifically simulate failures in external APIs (Taskcluster, Bugzilla) and Pulse message drops, ensuring robust error recovery.

### Phase 3: High-Impact UI Components

*Goal: Fortify the most used parts of the Treeherder dashboard.*

1. **Job View Fortification:** Increase coverage for `JobArtifacts.jsx` and `JobInfo.jsx`.
2. **Revision Details:** Focus on `RevisionInformation.jsx` and `RevisionLinkify.jsx` to ensure commit data is always rendered correctly.
3. **Auth Callback Reliability:** Rewrite or expand tests for `TaskclusterCallback.jsx` to handle various authentication failure scenarios.

### Phase 4: Integration and End-to-End Depth

*Goal: Catch regressions that unit tests miss.*

1. **Expanded Integration Suite:** Add PollyJS-backed integration tests for the "Perfherder" views.
2. **Pulse/Taskcluster Simulation:** Improve backend test fixtures for Pulse consumers to better simulate real-world data lag and malformed payloads.
3. **Performance Test Optimization:** Audit and optimize existing performance tests in `tests/perf/` to reduce their runtime, facilitating more frequent execution during development.
4. **Accessibility Testing:** Integrate automated accessibility checks (e.g., `jest-axe`) into the frontend test suite.

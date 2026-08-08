# Bugzilla Tickets for Improving Test Coverage

This document outlines the content for Bugzilla tickets to address testing gaps in the Treeherder project. Tickets are categorized by functional area where code coverage is currently below 90%.

---

## Backend Tickets (treeherder/)

### Ticket 1: Improve Coverage for Data Ingestion (ETL)

- **Summary:** Increase test coverage for `treeherder/etl/` to 90%+
- **Description:**
  Current coverage for ETL processes (Bugzilla, Jobs, Pushes) is significantly below the 90% target.
  **Tasks:**
  - Add unit tests for edge cases in `treeherder/etl/bugzilla.py`.
  - Improve coverage for Mercurial/Git push ingestion in `treeherder/etl/push.py`.
  - Simulate API failures and malformed data payloads to ensure robust error handling.

### Ticket 2: Strengthen Database Model Logic Tests

- **Summary:** Increase test coverage for `treeherder/model/` and `treeherder/perf/` models
- **Description:**
  Many core logic methods in Django models (Managers, save overrides, and property methods) are currently only tested indirectly via APIs.
  **Tasks:**
  - Write direct unit tests for custom Managers in `treeherder/model/models.py`.
  - Ensure performance signature logic in `treeherder/perf/models.py` is fully covered.

### Ticket 3: Fortify Service Layer Wrappers

- **Summary:** Increase test coverage for `treeherder/services/`
- **Description:**
  The wrappers for Taskcluster and Pulse services have low granular coverage.
  **Tasks:**
  - Add unit tests for Taskcluster URL generation and client factory logic in `taskcluster.py`.
  - Increase coverage for Pulse message consumers and exchange configurations.

### Ticket 4: Comprehensive API Viewset Testing

- **Summary:** Increase test coverage for `treeherder/webapp/api/`
- **Description:**
  Several API endpoints, particularly those related to jobs, pushes, and performance data, have coverage gaps.
  **Tasks:**
  - Expand `pytest` coverage for complex query parameters in `performance_data.py`.
  - Ensure all failure response paths (400, 403, 404) are verified for major viewsets.

---

## Frontend Tickets (ui/)

### Ticket 5: Secure Core State Management (Stores)

- **Summary:** Increase test coverage for Zustand stores in `ui/shared/stores/`
- **Description:**
  The "brain" of the UI (pushesStore, selectedJobStore, pinnedJobsStore) has coverage between 50% and 80%.
  **Tasks:**
  - Add unit tests for state transitions during network errors.
  - Verify complex filtering and sorting logic within the stores.

### Ticket 6: Fortify Job View Components

- **Summary:** Increase coverage for job-view components (`ui/job-view/`)
- **Description:**
  Critical components like `JobArtifacts.jsx` and `JobInfo.jsx` currently have ~50% coverage.
  **Tasks:**
  - Add RTL tests for artifact rendering and external link generation.
  - Verify UI behavior for expired or missing task metadata.

### Ticket 7: Improve Logviewer Reliability

- **Summary:** Increase coverage for `ui/logviewer/` and related tabs
- **Description:**
  The logviewer components and the `LogviewerTab.jsx` have extremely low coverage (some at 0%).
  **Tasks:**
  - Add tests for log line parsing and highlighting.
  - Verify search match navigation within the classic log viewer.

### Ticket 8: Expand Perfherder View Coverage

- **Summary:** Increase test coverage for `ui/perfherder/`
- **Description:**
  Alert views and graph components in Perfherder need more robust testing, especially around data visualization edge cases.
  **Tasks:**
  - Add tests for magnitude abbreviation and framework selection.
  - Verify downstream summary fetching logic.

### Ticket 9: Verify Auth Callback Flows

- **Summary:** Increase test coverage for `ui/taskcluster-auth-callback/`
- **Description:**
  `TaskclusterCallback.jsx` currently has ~15% coverage. This is a critical path for user authentication.
  **Tasks:**
  - Simulate various authentication failure scenarios and verify error message display.
  - Verify successful token handling and redirection.

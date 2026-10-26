# FULL extras (start from JOB-STANDARD.md)

A job is FULL only when it spans several services. Copy `JOB-STANDARD.md`, set **Lane:** FULL, then add:

- **Phase 0:** one t0 table per service, and each service's gate runner.
- **Phase 2:** a row per cross-service contract (the interface, its owner, what changes).
- **Phase 4:** a `Needs` column (task → the tasks it waits for) and the order the work orders go out in.
- **Phase 6:** base-vs-head per service; the independent inspection's pack covers every service's diff.
- **Phase 7:** one safety fact per service boundary.

Everything else, including both inspections, is the same as STANDARD.

# Database snapshots for LocalDatabase smoke tests

Place anonymized SQLite snapshot files in this directory to validate `LocalDatabase.initialize()` and migrations against real-world schemas. Snapshots should:

- be fully scrubbed of personal data;
- use the `.sqlite` extension;
- target recent schema versions that require migration coverage;
- stay small enough for quick CI runs.

Do not commit production databases or sensitive information. If no snapshots are available, the smoke test will be skipped automatically.

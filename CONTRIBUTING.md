# Contributing

Thank you for helping.

1. Open an issue before a large design change.
2. Do not add credentials, private addresses, transcripts, model files, or
   runtime state.
3. Keep paid tests separate from local tests.
4. Add a failure test for each lifecycle fix.
5. Run `./scripts/release-check.sh` before a pull request.

Version 0.1 supports only the documented Vast RTX 5090 profile. Mark support for
another provider or GPU as experimental until it passes the full validation
gate.

Provider adapters and model profiles must follow [docs/EXTENDING.md](docs/EXTENDING.md).

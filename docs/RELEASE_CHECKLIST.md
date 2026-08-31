# Release checklist

- [ ] Working tree is clean and the release commit is pushed.
- [ ] `REQUIRE_SHELLCHECK=1 ./scripts/release-check.sh` passes.
- [ ] `./scripts/clean-install-check.sh` passes without GPU rental.
- [ ] GitHub test and Gitleaks jobs pass on the release commit.
- [ ] Production uses the exact release commit and the private Pi route passes.
- [ ] Only one intended paid instance exists, or all compute is stopped.
- [ ] README, validation evidence, changelog, and third-party terms are current.
- [ ] The release tag points to the exact tested commit.
- [ ] Release notes state alpha limits, hourly price cap, storage cost, and cleanup.

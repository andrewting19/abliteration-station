## Summary

Describe the user-visible change and the first failure it fixes.

## Validation

- [ ] `REQUIRE_SHELLCHECK=1 ./scripts/release-check.sh`
- [ ] `./scripts/clean-install-check.sh` when install behavior changed
- [ ] Failure test added for lifecycle behavior
- [ ] Paid hardware test kept separate from local tests

## Safety and cost

- [ ] No credentials, private addresses, prompts, transcripts, model files, or runtime state
- [ ] Price caps and cleanup behavior are unchanged or clearly documented
- [ ] New provider or model support is marked experimental until it passes the full acceptance gate

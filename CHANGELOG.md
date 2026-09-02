# Changelog

## 0.3.0 - 2026-09-02

- Remove the failed provider-copy experiment from the default request path.
- Move the 120K performance and tool gate after first-token recovery and run it
  only after the route becomes idle.
- Report dependency, runtime, target-download, draft-download, quantization,
  model-load, and route phases separately in Pi.
- Accept viable hosts with at least 32 GB of system RAM and try CUDA 13.0 when
  no CUDA 13.2 offer can be secured below the configured price cap.
- Carry rejected offer IDs across CUDA tiers and reject fresh containers that
  do not become usable within five minutes.
- Download verified RTX 5090 runtime and Q4 draft artifacts. Keep the pinned
  source-build and BF16-draft paths as verified fallbacks.
- Skip the source clone when the verified runtime cache matches the pinned
  source tree.
- Store deferred performance-gate results in the service state directory.

## 0.2.2 - 2026-09-01

- Open the compatibility Pi launcher immediately. Model wake now occurs only
  through the local proxy, where Pi can show lifecycle progress.
- Detect a failed Vast stopped-instance copy instead of waiting for its full
  copy timeout before using the public bootstrap fallback.

## 0.2.1 - 2026-08-31

- Show the actual retained-GPU, replacement-rental, workspace-copy, bootstrap,
  performance-gate, and private-route phases in Pi with phase estimates.
- Fail over after Vast's scheduling window instead of waiting five minutes for
  a retained GPU that is no longer available.
- Prefer Vast's stopped-instance workspace copy for a fresh host. Keep public
  downloads and compilation as the verified fallback.

## 0.2.0 - 2026-08-31

- Package the integration for installation with `pi install`.
- Register the provider and model from the Pi extension instead of editing
  `models.json`.
- Add Pi commands for setup, model selection, status, wake, stop, and doctor.
- Keep the root-owned lifecycle proxy as a companion service that survives Pi.
- Remove copied legacy extensions and provider entries during service upgrade.
- Keep `pi-abliteration-station` as a compatibility launcher.
- Allow five minutes for a stopped Vast host to enter its restart path before
  replacement.
- Exclude each failed live offer during one rental sweep so retries do not
  select the same unavailable offer.
- Allow up to two hours for a verified fresh bootstrap. Large model downloads
  must not be killed by the former 30-minute controller timeout.
- Clear old wake errors when a healthy route is available and migrate the old
  timeout defaults during an upgrade.

## 0.1.1 - 2026-08-31

- Load provider adapters from configuration without editing the controller.
- Read Pi model identity and context from the configured model profile.
- Fix CUDA compatibility selection and provider fallback in the service sandbox.
- Stream cold-start progress to the Pi launch terminal.
- Correct the long-context gate and add a required tool loop.
- Add clean install and uninstall, ShellCheck, Gitleaks, and contribution templates.
- Complete uninstall cleanup while preserving provider and credential state.

## 0.1.0 - 2026-08-29

- Add demand-start and idle-stop lifecycle control for Vast.ai.
- Add the private Tailscale model route and bearer authentication.
- Add exact Q3, 262K, native-thinking, chat, and speed gates.
- Add wake serialization for concurrent requests.
- Add Pi provider configuration, launcher, and visible wake status extension.
- Add local unit, integration, syntax, package, and secret-scan gates.

# Changelog

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

# Security policy

## Supported version

Only the latest tagged release is supported. Version 0.1 is alpha software.

## Report a vulnerability

Do not open a public issue for a credential leak or a route exposure. Use the
private security-report function in the GitHub repository.

## Security model

The default design has three controls:

- The local lifecycle proxy listens only on `127.0.0.1`.
- The remote model server listens only on `127.0.0.1`.
- Tailscale TCP Serve and a random bearer key protect remote access.

The installer stores secrets with mode `0600`. It does not put keys in the
repository. The deployment sends secrets only through SSH or the private
Tailscale connection.

## Operator duties

- Use a dedicated server and a dedicated Tailscale tag or account policy.
- Use a reusable, pre-authorized Tailscale auth key with the smallest useful
  privileges.
- Rotate the Vast, Tailscale, and inference keys after a suspected leak.
- Do not expose ports 17070 or 17072 on a public interface.
- Review the Vast price cap before you start the service.
- Delete old Vast instances when you no longer need retained storage.
- Do not add real Pi requests to tests or bug reports.

## Files that must stay private

- `/root/.config/vastai/vast_api_key`
- `/root/.config/abliteration-station/inference_api_key`
- `/root/.config/abliteration-station/tailscale_auth_key`
- `/var/lib/abliteration-station/vast-private/tailscaled.state`
- `/etc/abliteration-station/config.json` after local changes
- model files, build caches, captured prompts, and provider state
- `/var/lib/abliteration-station/metrics/requests.jsonl` because timing and
  usage history can still reveal work patterns

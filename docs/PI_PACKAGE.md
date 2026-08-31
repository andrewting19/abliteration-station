# Pi package design

Abliteration Station uses two parts. This separation is intentional.

## Pi package

Pi installs the repository with `pi install`. The package:

- registers the private OpenAI-compatible provider and model;
- shows GPU wake progress in the TUI;
- provides model, status, wake, stop, setup, and doctor commands;
- contains the companion-service installer;
- updates with Pi package commands.

The extension runs inside the Pi process. It does not store provider keys. It
does not own a paid GPU after Pi exits.

## Companion service

The root-owned systemd service:

- keeps the loopback proxy available while Pi is closed;
- serializes concurrent GPU start operations;
- rents, starts, validates, and stops Vast compute;
- keeps Vast and Tailscale credentials outside the Pi package;
- forwards cancellation to the model server;
- stops paid compute after the idle limit.

The package must not silently request a password. `/abliteration-setup` runs
the installer directly when Pi runs as root. With an unprivileged Pi process,
it uses passwordless `sudo` if available. Otherwise, it displays the exact
one-time command for the user to run in a terminal.

## Installation states

1. Package only: commands and model metadata load, but inference is not ready.
2. Service installed: the proxy and lifecycle programs exist.
3. Configured: private Vast and Tailscale keys exist and the proxy is active.
4. Selected: `/abliteration-use` makes the model active in Pi.
5. Ready or sleeping: Pi can use the same open session in both states.

The extension must give a clear error for each incomplete state.

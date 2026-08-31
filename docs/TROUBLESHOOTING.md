# Troubleshooting

## Pi reports that the wake failed

Run:

```sh
sudo abliteration-station status
sudo journalctl -u abliteration-station-proxy.service -n 200 --no-pager
sudo /usr/local/lib/abliteration-station/vast/qwen-vast instances
```

The first error in the provider output is the useful error. Common causes are
no qualified offer below the price cap, no Vast balance, a stopped host that no
longer accepts SSH, or a Tailscale key that cannot add a node.

## Pi waits but shows no wake status

Run `/reload` in Pi after installation. Then run `/abliteration-status`. Confirm
that `/root/.pi/agent/extensions/abliteration-station-status.ts` exists.

## The private host name does not resolve

Enable MagicDNS in the Tailscale admin console. Confirm that the client server
is connected to the same tailnet. Run `tailscale status` and look for
`qwen38-vast`.

## A fresh deployment is slow

This is expected. A fresh host downloads and verifies the model files, builds a
pinned CUDA runtime, quantizes the draft model, and runs a long-context speed
test. The launcher prints each provider stage to the terminal. If there is no
new output for five minutes, inspect the service journal and Vast instance
state with the commands above. Keep the Vast instance stopped instead of
deleting it if you want the
faster retained-instance start path. Retained storage can still cost money.

## The long-context speed gate fails

The model is sensitive to CPU speed, PCIe bandwidth, and disk speed. The
controller rejects a host below 80 decode tokens per second. Raise the price cap
or wait for a better offer. Do not lower the gate unless you accept lower agent
speed.

## Pi reports a context error

Confirm that the model record has `contextWindow` and `maxTokens` set to
262,144. Run `sudo abliteration-station-audit`. Pi still needs room for output inside the
same total context window.

## Stop all paid compute

Run `sudo abliteration-station stop`. Then inspect the Vast.ai instance list. This stops
the recorded instance but does not delete it or stop its storage charge.

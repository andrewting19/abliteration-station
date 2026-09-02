# Abliteration Station

**Private abliterated models on demand for Pi. Rent the GPU, wake the model,
and stop paying when it sleeps.**

Abliteration Station gives [Pi](https://github.com/earendil-works/pi) a private,
OpenAI-compatible Qwen model on a rented Vast.ai GPU. It starts compute on
demand, keeps an open Pi session usable after idle shutdown, and stops paid GPU
compute after ten minutes without an inference request.

Version 0.3 is an alpha release. It is an official Pi package with a
configurable provider adapter and
model profile boundary, but supports one fully tested deployment profile:

- Qwen3.8-27B Unleashed `Q3_K_XL`;
- Qwen3.8-27B DFlash2 `Q4_0` draft decoding;
- one RTX 5090;
- 262,144 tokens of context;
- native medium thinking and temperature 1.0;
- a private Tailscale route;
- Vast.ai as the compute provider.

The repository does not contain model weights, credentials, Pi transcripts, or
Tailscale state. The installer downloads model files from Hugging Face and
builds the pinned llama.cpp/DFlash runtime on the rented host.

## What it does

When Pi sends an inference request, the local proxy does this work:

1. It reuses a healthy route, or starts the retained Vast instance.
2. If no retained instance exists, it rents one qualified RTX 5090 below the
   configured price cap.
3. It downloads a verified portable runtime when the host supports it. A
   pinned source build remains the fallback.
4. It verifies the exact model, quantization, context, and chat behavior before
   it accepts a fresh host.
5. It forwards the original request after the model is ready.
6. When the route becomes idle, it runs the long-context speed and tool gates
   without delaying the first interactive response.
7. It stops GPU compute after the idle limit. It does not delete retained data.

Concurrent requests share one start operation. A Pi extension shows the wake
state and elapsed time. Pressing Escape cancels the forwarded HTTP request.

## Requirements

Use a dedicated Ubuntu or Debian server that stays on while you use Pi. The
installer currently requires root and systemd.

- Python 3.11 or newer, with `venv`
- Node.js 20 or newer
- `curl`, `jq`, `openssh-client`, `openssl`, `util-linux`, and `systemd`
- Tailscale, connected to a tailnet with MagicDNS enabled
- Pi coding agent, available as `pi`
- a funded Vast.ai account and API key
- a reusable Tailscale auth key
- at least 150 GB of disk on the rented host

The first fresh deployment can take several minutes. It downloads and verifies
the target model, a portable DFlash draft, and a pinned CUDA runtime. If a
portable artifact is not compatible or available, it builds llama.cpp from the
pinned source and can quantize the draft locally. A retained Vast instance
normally starts much faster.

## Install

Install the package from GitHub:

```sh
pi install git:github.com/andrewting19/abliteration-station@v0.3.0
```

Start Pi and run `/abliteration-setup`. On a root-based Pi server, this
installs the durable local service directly. On other systems, Pi shows the
exact one-time `sudo` command. Then add the two private service keys:

```sh
sudo abliteration-station-configure
sudo abliteration-station-audit
```

`abliteration-station-configure` asks for the Vast.ai and Tailscale keys without echoing
them. It stores them in root-only files. For unattended setup, pass them as
`VAST_API_KEY` and `TAILSCALE_AUTH_KEY` environment variables.

The default maximum Vast price is $0.53 per hour. To use another limit, run
`sudo systemctl edit abliteration-station-proxy.service` and add:

```ini
[Service]
Environment=QWEN38_MAX_DPH=0.45
```

Restart the service after you save the override.

## Use with Pi

Start or continue a normal Pi session:

```sh
pi
pi --continue
```

Run `/abliteration-use` once to select Qwen with native medium thinking. Pi
retains the selected model. You can also select
`abliteration-station/qwen38-cloud` from Pi's model picker.

If the instance stopped while Pi stayed open, send the next prompt normally.
The prompt stays queued while the proxy starts the model. The Pi status line
shows the wake timer. The package supplies these commands:

- `/abliteration-use`: select Qwen and medium thinking;
- `/abliteration-status`: show route, request, and idle state;
- `/abliteration-wake`: start the retained GPU before a prompt;
- `/abliteration-stop`: stop paid compute but keep retained storage;
- `/abliteration-doctor`: check the lifecycle installation;
- `/abliteration-setup`: install or upgrade the companion service.

The old `pi-abliteration-station` launcher remains as a compatibility command.
New installations do not need it.

Useful lifecycle commands are:

```sh
sudo abliteration-station doctor
sudo abliteration-station status
sudo abliteration-station ensure
sudo abliteration-station stop
sudo abliteration-station-audit
```

`stop` stops compute but keeps the Vast instance and its storage. Vast can
still charge for retained storage. Delete the instance in Vast.ai when you no
longer need it.

## Measured reference result

The accepted reference host used an RTX 5090, at least 32 GB of system RAM, and
a qualified CPU and PCIe path. The corrected 117,046-token gate reached 119.0
decode tokens per second. A separate 239,310-token near-limit gate reached 83.1
decode tokens per second. A retained-host cold start has reached the model in
about 30 to 47 seconds when Vast can return the same GPU. These results are not
guarantees. Host CPU, PCIe, disk, network, and current Vast capacity can change
them.

## Security

The model server listens on the rented host loopback interface. Tailscale TCP
Serve makes it available only inside the tailnet. A bearer key protects the
OpenAI-compatible endpoint. The local Pi proxy listens on `127.0.0.1`.

Read [SECURITY.md](SECURITY.md) before installation. Do not commit configuration
files, runtime state, keys, model files, or captured prompts.

## Test

Run the local release gates:

```sh
./scripts/release-check.sh
```

The default test does not rent a GPU. The paid hardware acceptance test is in
[docs/VALIDATION.md](docs/VALIDATION.md).

## Limits

- Version 0.3 supports only Vast.ai and one RTX 5090 profile.
- The installer supports root-based Linux systems with systemd.
- The fast portable CUDA runtime is limited to the verified CUDA 13.2 RTX 5090
  profile. Other compatible hosts use the pinned source-build fallback.
- The long-context performance gate runs after the first interactive request.
  A newly routed host can therefore respond before its deferred performance
  result is available.
- One model slot is configured. Parallel long-context requests compete for it.
- The lifecycle code can stop or rent compute. Review the price cap first.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more detail.
Forks that add a provider or model profile must follow
[docs/EXTENDING.md](docs/EXTENDING.md).

Cost and speed work must use the [measurement contract](docs/MEASUREMENT.md).
Future ideas are in the [experiment backlog](docs/EXPERIMENT_BACKLOG.md), and
the source inventory is in [docs/RESEARCH_SOURCES.md](docs/RESEARCH_SOURCES.md).

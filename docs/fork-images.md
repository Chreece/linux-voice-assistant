# Maintained Docker images

This fork keeps the custom voice behavior on the current
[OHF-Voice upstream](https://github.com/OHF-Voice/linux-voice-assistant).

| Branch | Moving image tag | Platforms |
| --- | --- | --- |
| `main` | `ghcr.io/chreece/linux-voice-assistant:latest` | AMD64, ARM64 |
| `usb-respeaker` | `ghcr.io/chreece/linux-voice-assistant:usb-respeaker` | AMD64, ARM64 |
| `pi0w` | `ghcr.io/chreece/linux-voice-assistant:pi0w` | ARM64 |

`custom` is an alias of `usb-respeaker`; `pi02w` is an alias of `pi0w`.
The old `pi02w` branch is kept at the same revision as `pi0w`.
Existing installations can keep these image tags.

The USB branch also publishes the official upstream controller as
`ghcr.io/chreece/linux-voice-assistant:respeaker-usb-peripheral` for AMD64
and ARM64. The LED Python script is unchanged. The packaging supplies the
correctly named requirements file so there is no local build step.

## Updates

The default branch's **Synchronize upstream and refresh images** workflow checks
upstream hourly, at minute 17 UTC. GitHub may delay scheduled jobs. It rebases
`main` onto the latest upstream `main`, then reapplies the USB and Pi changes on
that new base. Branch refs are updated together using an atomic push and exact
force-with-lease checks. The workflow calls the image builder directly, because
pushes made with `GITHUB_TOKEN` do not trigger another push workflow.

For fully unattended synchronization, add an Actions repository secret named
`UPSTREAM_SYNC_TOKEN`: a fine-grained token restricted to this repository with
**Contents: read and write** and **Workflows: read and write**. Renew it before
its expiration. A dedicated GitHub App with those permissions is another option
for a permanent integration. Build jobs still use their ordinary `GITHUB_TOKEN`.
Without that secret, routine application updates can use the default token, but
GitHub rejects changes that introduce new workflow-file contents. The workflow
warns when the credential is missing. This is a
[GitHub permission limitation](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token),
not a reason to drop upstream workflow changes.

Source changes trigger a build. The hourly check during 04:00 UTC also refreshes
the images with the current base image and allowed dependency versions. Manual
workflow runs force an image refresh. Pushes to the maintained branches build
immediately. A merge conflict stops synchronization before any remote branch
changes; a failed test or build leaves published moving tags unchanged. Neither
conflicts nor test failures are automatically resolved by dropping custom code.

The build runs the Python lint and test scripts and synchronization integration
tests. It builds on native AMD64/ARM64 runners, verifies the installed wake-word
libraries and libmpv, and checks the peripheral's imports and command line. Moving
tags are published only after both architectures pass. A final ref check skips
publication if someone has pushed a newer source revision during the build.
These checks do not replace microphone, speaker, LED, or Pi hardware testing.

Every source revision also has a tag such as `usb-respeaker-<full-commit-SHA>`.
Docker labels record the source revision. Build logs and failures appear under
the repository's Actions tab. GitHub can disable scheduled workflows in public
repositories after 60 days without repository activity. To prevent inactivity
during quiet upstream periods, the sync workflow records the checked upstream
SHA and UTC month in `maintenance/upstream-check.json`. It commits that source
record only when the SHA or month changes, so repeated hourly checks of the
same source create no extra commits. This records a source check, not a passing
build or hardware test. The record and all branch rebases are pushed together;
a later rebase conflict leaves every remote branch unchanged. If the workflow
is already disabled, re-enable it in Actions so these checks can resume.

## USB ReSpeaker server

Use [deploy/compose.usb-respeaker.yml](../deploy/compose.usb-respeaker.yml) with
your existing `.env`. It includes the satellite, its USB LED controller, Piper,
and the published [Whisper ROCm image](https://github.com/Chreece/Whisper-rocm).
It retains the existing service names, named volumes, PulseAudio socket/cookie
mounts, and peripheral port 6056. Check the host-specific audio names and cookie
path when using it on another machine.

Whisper stays on full `large-v3`, Greek, FP16, beam size 2,
`CT2_CUDA_ALLOCATOR=cub_caching`, and `GPU_MAX_HW_QUEUES=1`. CTranslate2 uses the
device name `cuda` for ROCm. Model downloads are allowed on the first run; later
runs reuse the model cache. The Whisper image is AMD64 only and belongs on the
AMD GPU server, not on a Pi satellite.

Once the Compose file is installed, download all current images with:

```sh
docker compose pull
```

Apply the downloaded images to running containers with:

```sh
docker compose up -d
```

To download and apply in one command:

```sh
docker compose up -d --pull always
```

`pull` fetches registry images; it does not fetch repository files, rebuild an
image, or recreate a running container. No recurring `git pull` or local Docker
build is needed for these images. Keep your existing `.env` and named volumes.
If an older Compose override bind-mounts a patched `satellite.py`, remove that
specific obsolete code override: the maintained image already contains the
custom voice behavior and a bind mount would hide new upstream code.

## Pi satellites

Use `ghcr.io/chreece/linux-voice-assistant:pi0w` for both the permissions helper
and satellite service. See [the Pi profile](https://github.com/Chreece/linux-voice-assistant/blob/pi0w/docs/pi_zero_2w.md). It targets a
Raspberry Pi **Zero 2 W with a 64-bit OS**, uses the local wake-word engine, and
leaves speech recognition/TTS on the Home Assistant/server side. Original
ARMv6 Zero/Zero W boards and 32-bit OS installs are not supported by this image.

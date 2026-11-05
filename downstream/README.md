# Downstream patch queue

The upstream baseline is pinned in `config.json` at version `1.6.1`
(`384ce020cc655133e95aaad5cc085f3985f0ed99`). The maintenance workspace's
root `VERSION` remains the upstream baseline; do not change it to the fork
version. The application patch queue may set a fork version in a prepared
tree for development, but release builds inject their version from the tag
through `GITHUB_REF_NAME` on every platform. Maintenance files are not
application patches. Build and package from a
prepared tree, not from the main workspace. Python 3, Git, network access to
the upstream URL, and the relevant platform toolchain are required.

`patches/series` is the sole application order. Each entry names one numbered
`git format-patch` mail patch in the same directory. `patches/tests.json` has
exactly the same keys. The queue carries remote monitoring, native multi-host
integration, fork release and updater changes, and platform fixes. Never place
credentials in this repository or a patch.

## Single maintenance branch

Use `downstream/patch-build` for all ongoing fork work: the upstream pin,
application mail patches, test registrations, CI, packaging and release tools.
Do not create a branch per task or per fork release. Remove obsolete task
branches only after confirming their commits are retained here. Publish this
branch before deleting remote task branches; never rewrite published tags.

Application development still happens in disposable prepared trees. Export
its commits as mail patches and commit the queue and maintenance changes on
`downstream/patch-build`; never copy the patched application tree over this
maintenance checkout. `main` is not an additional required staging branch.
Release tags are created from the latest already-committed
`downstream/patch-build` revision. Published tags and assets remain immutable.


## Remote sources

On macOS and Windows, local sources and enabled SSH-connected Linux hosts
operate at the same time. They are grouped by host and source in the native
dashboard, whose available statistics aggregate across sources; there is no
target selector. Unavailable values are not zeros, and offline periods remain
gaps in history. History exports match the visible history; local diagnostic
reports exclude remote data. See the [fork release notes](../docs/releases/v1.6.1-fork.2.md)
for setup, collector requirements and verification limitations.
Floating orb source settings on macOS and Windows also allow selection by host
and source, including enabled remote hosts.
On Windows, global source switches apply to local and remote instances of a
source. An orb's host/source exclusions are separate: they affect that orb and
its associated views without excluding the same source on another host.
Undetected sources do not make an otherwise valid rate incomplete; detected
sources with unknown rates and offline intervals remain unknown and produce
history gaps. Chart estimate indicators mean that the visible range contains
estimated segments, not necessarily that the current rate is being estimated;
omp does not provide per-token measurements.

## CI and releases

The GitHub workflows check out the maintenance repository and prepare an
independent tree in the runner's temporary directory. Application tests,
builds and packaging run against that tree, so a changed pin, series, patch or
test registry affects the build without copying application files into the
maintenance checkout. Preparation needs Python 3, Git and access to the pinned
upstream repository on every runner.

`Release` is the **only complete release gate**: it prepares the pinned tree,
runs the required cross-platform validation and packaging, and publishes only
after all required jobs succeed. The separate `CI` workflow has been removed;
`Linux` is a reusable workflow called by `Release`, not a separately
dispatchable gate. Ordinary branch pushes do not publish or start full builds.

Commit and push all intended changes to `downstream/patch-build`, then run the
release wrapper from a clean checkout of that branch:

```sh
bash downstream/release.sh --plan  # read-only inspection
bash downstream/release.sh         # launch and wait for publication
```

The wrapper requires Git, network access, push access to `origin`, and an
authenticated `gh` session with access to the upstream repository and fork
releases, drafts, and Actions, including permission to write releases and
Actions. It queries the latest upstream release and its tag commit; if that
commit does not match `downstream/config.json`, it stops rather than silently
building a stale pin. First migrate the pin and patch queue, then retry.
The wrapper tags the latest already-committed `downstream/patch-build`; it
does not stamp versions, create commits, or modify the patch queue or docs.
Make and commit any needed queue or documentation changes before launching it.
The wrapper selects the next fork number after the highest published release.
An unpublished candidate of that number is retried by cancelling its old runs
and cleaning up the old draft and tag before recreating it. The wrapper checks
again immediately before deletion, but GitHub's API does not provide an atomic
draft-only delete. While the wrapper runs, nobody, including third-party
automation or administrators, may manually publish the same tag: a concurrent
publication can race that check. Published releases must never be replaced.
The wrapper reports success only after publication and all release assets are
ready. `--plan` performs queries without changing anything.

To check a macOS bundle locally against its tested Linux collector, run
`python3 downstream/verify-collector-zip.py <zip> <collector>` from the
maintenance workspace. It checks archive and extracted executable permissions
and byte equality. Release also runs `downstream/test-verify-collector-zip.py` with
synthetic archives covering missing, non-executable, changed and valid files.

The `Release` workflow runs on `v*` tag pushes in `yooztech/agent-speed`; the
tagged commit must be an ancestor of `downstream/patch-build`. Fork tags use
`vX.Y.Z-fork.N`; `GITHUB_REF_NAME` supplies the version injected into the
prepared release tree and used by all platform builds and packages.
The workflow publishes Linux, macOS and Windows artifacts together, including
the x86_64 collector in macOS and Windows packages. Windows offers both a
portable ZIP and a per-user installer.
The Windows installer smoke test exercises legacy startup migration, upgrades
with startup enabled and disabled, and explicit installer task overrides.
Drafts can be retried and published; published releases are left unchanged.
A successful build does not establish runtime compatibility on every target
system; real GUI SSH end-to-end operation has not been verified on a physical
remote host.

Published fork tags and assets are immutable: changes after publication require
a new fork version and tag, not replacement of `v1.6.1-fork.2` assets. The
historical `v1.6.1-fork.1` release notes remain available separately.

## Prepare for focused development

From the main workspace, choose an output path **outside** the workspace that
does not exist:

```sh
python3 downstream/manage.py prepare /tmp/agent-speed-prepared
```

Prepare clones the pinned upstream and applies every entry in order with
`git am`; it stops on the first failure and leaves the output for diagnosis.
The `verify` implementation remains a maintenance diagnostic, not a release
prerequisite. Do not run full registered platform suites before starting
Release: Release owns those checks and blocks publication on failure. Use
only focused checks needed to resolve a concrete problem. UI, real remote
end-to-end, disconnect/reconnect and performance checks require appropriate
environments and are not established by successful compilation.

The current registry runs the Linux CMake build and CTest suite, and `swift
test` on macOS. Linux needs a C++ toolchain, CMake, and the dependencies used
by the Linux project; if `/usr/src/googletest` is present it is used instead of
fetching GoogleTest. macOS needs Xcode and Swift. The registry currently has
no Windows-specific commands; a Windows verification run therefore does not
establish coverage of the remote-monitoring patch.

For the headless Linux collector, build on a compatible target Linux host and
architecture from the prepared tree with `macos/scripts/build-linux-collector.sh`.
It requires CMake 3.22+, a C++20 compiler, pkg-config, and development libraries
for zstd, Brotli, SQLite, ICU, and OpenSSL; Qt is not required. The resulting
binary is dynamically linked and must match the target system's architecture
and libraries. From the maintenance workspace,
`python3 downstream/check-collector.py` reports host build prerequisites;
`python3 downstream/check-collector.py path/to/agent-speed-collector` instead
checks that binary's runtime dependencies with `ldd`. Supply only trusted
binaries. These diagnostics do not compile or build the collector, establish
compatibility on other hosts, or replace runtime testing.

Each registry entry has this form (replace examples with actual commands):

```json
{
  "0001-example.patch": {
    "regression": [{"platform": "linux", "run": "command-for-regression"}],
    "related": [{"platform": "macos", "run": "command-for-related-tests"}],
    "reason": ""
  }
}
```

Platforms are `linux`, `macos`, `windows`, or `all`. Register real regression
and directly related tests for behavioral patches; test commands may build as
needed. For a patch with no applicable tests, leave both arrays empty and
explain why in `reason`. An unregistered patch fails preparation and
verification; a nonempty reason is not a substitute for behavioral tests.
Registry commands are trusted code: review them before running verification.

## Develop and export

1. Prepare a separate checkout outside the main workspace. Make focused,
   linear commits there, with application code, tests and directly relevant
   product documentation together. Do not include `downstream/` or this fork's
   handoff document. Do not reset the maintenance workspace or commit patched
   application files there; commit only queue and maintenance changes on
   `downstream/patch-build`.
2. With a clean development checkout and the configured pin as an ancestor,
   export into another new directory outside the main workspace:

   ```sh
   python3 downstream/manage.py export /tmp/agent-speed-prepared /tmp/agent-speed-export
   ```

   Export runs `git format-patch` for the baseline-to-HEAD range and writes
   `series` and `tests.json` beside the patches. Existing test registrations
   with unchanged filenames are retained; new entries are intentionally empty.
3. Review the exported patches and update their test registrations. Replace
   the main workspace's queue files with the complete reviewed export, removing
   obsolete patches as well. Check replay in a fresh tree, then let the single
   Release pipeline perform full platform validation. Do not push, publish or
   rewrite history without authorization.

## Updating the upstream pin

Use `python3 downstream/manage.py --base <full-candidate-sha> prepare
<new-output>` to trial a candidate without changing the configured pin. For
conflicts, resolve and re-create the linear commits in a separate development
checkout, export against that same candidate with `--base`, and review the
complete replay before committing the pin and queue migration. The next
Release performs full platform validation and blocks publication on failure;
do not precede it with duplicate full suites. When upstream absorbs a patch, confirm equivalent behavior,
remove its patch, series entry and test registration together, and record the
upstream commit or PR in the change description. Never use a direct merge as a
substitute for replaying and testing the queue.

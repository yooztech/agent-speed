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
exactly the same keys. Patches are grouped by independently meaningful
features; corrections and regression-test fixes for a downstream feature belong
in that feature's patch rather than a later corrective patch. The queue carries
remote monitoring, native multi-host integration, fork release and updater
changes, and platform fixes. Never place credentials in this repository or a
patch.

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
On Windows, source switches for local monitoring do not filter remote sources.
Remote data remains associated with its host. An orb's host/source exclusions
are separate: excluding a source on one host affects that orb and its associated
views without excluding the same source on another host.
Undetected sources do not make an otherwise valid rate incomplete; detected
sources with unknown rates and offline intervals remain unknown and produce
history gaps. Chart estimate indicators mean that the visible range contains
estimated segments, not necessarily that the current rate is being estimated;
omp does not provide per-token measurements.

The current queue contains collector daemons shared by the same Unix UID and
full executable SHA-256, plus the activity-scoped mobile relay publisher.
Byte-identical collector assets share one daemon even at different paths;
different digests run independently without stopping older clients. Native
deployment and the exact runtime identity handshake are unchanged. Runtime
endpoints are private to `~/.agent-speed/daemons/<sha256>/`; persistent collector
history is private to `~/.cache/agentspeed-collector/<sha256>/`. Old global
endpoints, locks and caches are not migrated or removed. Each digest pays its
own scanning and memory cost. Lease IDs and relay authorization are not
digest-namespaced; their owners must revoke or unsubscribe the originating
authorization rather than assume another daemon can cancel it.
The prepared tree's `docs/shared-collector.md` defines control v2, lease
confirmation and coexistence rules. The [implementation handoff](../docs/remote-agent-monitoring-handoff.md#共享-collector-实施记录)
retains earlier local asset provenance and isolated SSH/TLS observations.
Unpublished local assets and checks are not a Release, an upgrade of previously
installed clients, or proof of APNs/iPhone delivery.

The independent, unreleased Widget statistics feed is carried by feature patch
`0016-Add-independent-widget-statistics-feed.patch`; it is independent of
ActivityKit's ten-second routine cadence and immediate known-state edges. It adds negotiated
`widget_statistics_v2` controls, a separately revocable authorization of at most
30 days, and a fixed statistics-only relay path with 30-minute routine attempts.
It reuses the single collector ingestion and per-timezone history projections;
missing dates/counts remain unknown. A null past day may only mean that the
scan covered that day and found no records, never that the history was not
ready: a projection whose history is missing, stale or labelled for another
calendar day does not replace a lease's stored statistics, the daemon refreshes
its own projection instead, and the covering correction is published as soon as
it exists as one bounded attempt that still observes Retry-After. Only the first
confirmation attempt may carry unscanned past days. Recorded rows keep counting
after their source is no longer detected, so a day keeps a known lower bound.
The mobile reader's temporary merge that tolerates older daemons storing
unscanned windows is removed once this publisher rule is deployed; null past
days are not an acceptable long-term output. A positive subscription ACK
confirms a genuine HTTP 200 storage response, not WidgetKit/APNs delivery. New local
development assets must retain pin, full ordered queue hashes, source commit/tree,
build commands/toolchain and actual ELF SHA/identity provenance. Never distribute
the compile-time loopback test-transport executable or call an unpublished
development artifact a GitHub release.

The existing network traffic views also show supported remote Linux source
traffic on macOS and Windows. The collector measures the SSH user's non-loopback
TCP traffic using the existing traffic service; it requires no sudo. Traffic is
kept separate by host and source. Older collectors may not provide traffic;
unknown values and offline history are not treated as measured zeroes. Live
rates clear on disconnect while the last observed totals remain available.
On Windows, a host is online only after a valid collector snapshot; malformed or incompatible frames do not keep the
connection healthy. Connection errors include a bounded stderr tail and exit code when available. Weighted average
speed uses measured output and time, with each machine/source counted once; missing categorized totals remain unknown.
Duplicate connections prefer current online history over stale history. An unavailable traffic sample has an unknown
rate, distinct from the zero live rate of a disconnected host; last known totals remain visible when available.

### Codex quota on macOS and Windows (unreleased)

The quota patches add an optional Codenotch-style edge-attached floating surface
and a Subscription page inside the existing Settings window. The floating
renderer is pinned to Codenotch commit `835550a342871779135b6484d6899161c5222f7c`:
macOS uses its native shape and layout, while Windows hosts its HTML/CSS/SVG in
WebView2 rather than approximating those pixels with WPF controls. Windows needs
the Microsoft Edge WebView2 Runtime; if unavailable, Settings reports that
requirement instead of substituting a different surface. Settings retains the
supplied account-card/progress-bar design. The existing transient dashboard
flyout shows at most two summaries near a limit, when blocked, or when sign-in
is required; clicking one opens Settings. Status-item bodies, taskbar widgets,
orbs and History do not carry quota data.
The local Codex login is read without modifying credentials, and account usage
polling is independent of the speed monitor. The contract, polling rules and
synthetic fixtures are in the prepared tree's `spec/QUOTA.md`. Unknown readings
remain unknown, not zero.

The quota persistence regression gives each provider actor its own `UserDefaults`
instance for the same suite, avoiding non-Sendable instance sharing under Swift 6.
The provider and all ten quota tests compile and pass under Swift 6.2 on Linux in
a disposable package using swift-crypto and FoundationNetworking. The macOS core
tests, update-relaunch checks, app-bundle build and archive verification also
passed in [Release run 43440127058](https://github.com/yooztech/agent-speed/actions/runs/43440127058).
Release run `43548237236` subsequently failed while compiling the redesigned
macOS notch: the cached `NSFont` and two `Animatable` witnesses violated Swift 6
isolation. Feature patch 0020 now keeps font measurement on the main actor and
uses sendable value state with nonisolated animation witnesses. The focused
Linux Swift 6.2 language probe passes strict concurrency checking; this is not
an AppKit/SwiftUI SDK build. The subsequent Release run `43551664293` reached
the app-test compilation and failed in the snapshot harness: the system
accessibility environment properties are read-only, not writable overrides.
Snapshot rendering now supplies explicit internal accessibility preferences to
the actual notch and its settings orb; normal application rendering still reads
the real system environment. The native bitmap tests retain all 32 edge/state
captures and use explicit AppKit image/color/file types. This repair has not
yet been compiled or executed against the macOS SDK.
The macOS build and tests have not passed for this redesigned surface. Linux
syntax checks and language probes must not be reported as macOS validation.
The redesigned native surfaces and real-login behavior remain unverified on
Windows and macOS. A same-browser fixture comparison can establish equality of
the shipped Windows renderer and its pinned reference for the compared states;
it does not establish native window placement, hit testing, font rasterization
or mixed-DPI behavior. Do not claim pixel identity without matching native
screenshots. Claude quota and Linux quota interfaces are future phases.

### Standalone collector release assets (unreleased)

When formally released, the pipeline is intended to publish
`agent-speed-collector-linux-x86_64`, the exact Linux x86_64 collector
embedded in both Windows ZIPs and the macOS ZIP, plus
`agent-speed-collector-linux-x86_64.sha256` and
`agent-speed-collector-linux-x86_64.json`. The checksum file is a single
`sha256sum` line naming the executable. `SHA256SUMS.txt` includes all three
standalone assets as well as the other release assets, but not itself. The
publisher checks the standalone checksum and compares it with each desktop ZIP
before publishing. No separate collector build is performed.

Consumers must resolve the GitHub latest release **once**, retain its immutable
`tag_name`, and fetch all three exact asset names from that same release/tag;
never resolve `latest` independently per download. Require a published release,
all assets, metadata `format_version` 1, the exact resolved `release_tag`,
`os` `linux`, `architecture` `x86_64`, and the supported protocol version 1.
Require the single checksum entry to name the exact executable and verify its
SHA-256 against both that entry and metadata `sha256` before installing or
executing. Abort on missing, malformed, mismatched or unsupported data: do not
fall back to older releases, legacy names, other architectures or unverified
downloads. SHA-256 checks consistency, not authenticity: obtain release data
over authenticated HTTPS from the intended repository and protect the trust
channel. Published release assets must not be replaced.

Resolve `https://api.github.com/repos/yooztech/agent-speed/releases/latest`
once; download from
`https://github.com/yooztech/agent-speed/releases/download/<tag>/<asset-name>`.
The checksum format is `<64 lowercase hex characters>  agent-speed-collector-linux-x86_64\n`;
after checking the exact filename, `sha256sum -c agent-speed-collector-linux-x86_64.sha256`
verifies the executable in the download directory. Set executable permissions
when installing the raw attachment; HTTP downloads do not preserve Unix mode.

Metadata records the release tag, maintenance commit (which identifies the
ordered patch queue), pinned upstream commit, protocol and observed ELF
interpreter, shared libraries and version requirements from the Ubuntu 22.04
build. These observations do not guarantee compatibility on another host;
check the trusted executable with `python3 downstream/check-collector.py PATH`
on the target. Only Linux x86_64 is packaged; no ARM64 compatibility is implied.

The pending shared collector retains metadata `format_version` 1 and outer
stdio NDJSON `protocol.version` 1. Its separate `protocol.shared_collector`
descriptor records `control_version` 2, capabilities `live_activity_v2`,
`live_activity_edges_v1`, `shared_collector_v1` and `widget_statistics_v2`, and the `--identity` contract:
the prefix `shared-collector-v2`, a space, the executable SHA-256, and a newline. The
release build opts into identity verification only for its trusted production
collector; packaging runs the staged executable and rejects a mismatching
identity or digest. Identity is evidence of the trusted build's declared
contract, not independent proof of functionality or authenticity. Packaging
without this explicit opt-in does not claim shared capabilities. Consumers
requiring shared control must reject missing or mismatched descriptors and must
not infer compatibility with older clients or binaries. The Widget declaration
applies to future builds of the full queue containing feature patch 0016, not
to immutable previously published fork.8 metadata. Runtime capability negotiation
is still required; no new release is claimed here.

### Shared collector and activity relay (unreleased)

The shared-daemon implementation belongs in the existing ordered application
feature patches, not in this checkout's unpatched application source or a
separate integration patch queue. Its protocol, security, lifecycle and build
contract is `docs/shared-collector.md` in the prepared tree. Local verification
and asset provenance are recorded in
[the maintenance handoff](../docs/shared-collector-handoff.md). Mobile changes
are implemented directly by the mobile project's integration owner; no mobile
patch artifact is distributed from this repository.

No Cloudflare deployment, Apple signing, APNs delivery, push, tag or release is
performed by that local implementation. The existing mobile package and its
legacy collector asset are not automatically migrated. All clients sharing a
Unix account must adopt the versioned deployment and daemon identity handshake;
already-shipped same-UID executables cannot be remotely constrained by the new
daemon. Host logout/cgroup policy must permit detached processes; no root
service or linger setting is installed.

The pending `live_activity_continuity_v1` capability separates a publisher
binding from the relay's individual Apple activity destinations. Only an explicit
`continuity: true` subscription may use the advertised
`activityMaxLeaseSeconds: 2592000` limit; its absolute expiry is not renewed by
publishing. Legacy subscriptions retain their eight-hour limit. Continuity keeps
the normal ten-second latest-only cadence even when quiet, subject to existing
backoff and response-completion deadlines. A successful normal publish response
may request one daily usage summary for the next normal request; this reuses the
same fixed-timezone sample without a second log scan. Input/output are known
lower bounds when coverage is incomplete. The measured output/time pair covers
only final responses with valid durations; completeness of input/output coverage
does not imply every output token has a measured duration. Mobile and relay
consumers must negotiate this capability; existing published assets do not gain
continuity support from these maintenance changes.
For continuity, HTTP 200 `{ok:true,apnsAccepted:boolean,usageRequested?:...}`
confirms validated snapshot persistence at the relay, not APNs acceptance or
device delivery. Apple destination failures and their backoff stay inside the
relay and do not terminate the publisher binding. Publisher authorization,
schema, database and genuine publisher rate-limit failures remain HTTP errors.

### Remote parity corrections (unreleased)

- Windows orb and leaderboard values use missing placeholders when their selected live or daily data is incomplete.
- Windows remote agents preserve configured versus selected effort and speed. Duplicate SSH destinations are rejected
  when saving, while editing a host without changing its own destination remains valid.
- Disabling a host retains its in-memory history but excludes it from current views and totals. Re-enabling uses it only
  as stale data until refreshed; deletion or a destination change clears the old host state.
- Both platforms keep available performance-history rows visible and show an incomplete-data notice when another
  selected host has not supplied performance history. Known empty histories remain distinct from missing histories.
- Windows remote-host and all-host CSV exports include host-specific daily traffic when the traffic columns are visible;
  unavailable traffic is blank, not zero.

Focused Linux verification covers the portable Core and Presentation consumers plus the protocol-to-CSV smoke path.
The Windows application cross-compiles on Linux; native Windows/macOS rendering, macOS compilation, and real SSH
disable/reconnect behavior still require target-platform validation. These checks do not replace the Release gate.


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

Actions progress shows each job's status, elapsed time and current running step.
Direct terminal output updates in place; the wrapper pipes through `tee`, so its
terminal and persistent log instead show only job changes and a roughly one-minute
heartbeat. The run link is printed once. A dash means timing is not yet available.

Transient network failures in the maintenance-owned GitHub/Git queries, source clone, dependency restore and package
setup use bounded retries: four attempts with 1, 2 and 4 second backoff. Authentication, validation and conflicting
remote state fail without blind retries. Polling and retries remain bounded by the overall workflow-watch deadline.
The local watcher exiting does not cancel an already-started Actions run.

To recover observation of an existing run without rebuilding, cancelling, deleting drafts or changing tags:

```sh
bash downstream/release.sh --resume RUN_ID
```

Resume verifies the Release workflow, push event, tag and commit before attaching, then checks the formal published
release and all expected nonempty assets. It can run from a dirty checkout because it performs no release mutations.
Use the existing run ID rather than launching a new candidate after a polling connection failure.

Release writes reconcile remote state after an ambiguous response, including on the final attempt: an accepted tag
push, draft creation, upload or publication is not blindly repeated. Published releases remain untouched. Matching
uploaded assets are reused; conflicting assets fail instead of being clobbered. Normal unpublished-candidate cleanup
still follows the safeguards below. Do not manually publish the same tag while release automation is active.
After successful draft creation, an absent release-list result is checked up to four times, with 1, 2 and 4 seconds
between checks. These bounds cover visibility checks and backoff in addition to existing network timeouts, not a strict
seven-second total. If the draft remains invisible, publication stops; a draft may still exist for a safe later retry.
This visibility retry does not change reconciliation of an ambiguously failed create request.

NuGet's own HTTP retry settings also cover implicit restore operations inside the unchanged packaging scripts.
CMake dependency acquisition retries only configuration, not the subsequent build or tests. Packaging curl downloads,
checkout, artifact and setup actions additionally have their own request-level retry policies; these do not guarantee
that every internal request or persistent outage can recover. Exhausted or permanent failures still block release.

The wrapper requires Git, network access, push access to `origin`, and an
authenticated `gh` session with access to the upstream repository and fork
releases, drafts, and Actions, including permission to write releases and
Actions. The wrapper verifies that the configured upstream tag resolves to the
commit in `downstream/config.json` and stops if it does not. It also queries the
latest upstream release; a different tag produces a warning, while the release
continues using the configured pin. Only when choosing to upgrade, manually
migrate and commit the pin and patch queue before releasing against the new baseline.
Before any cancellation, draft deletion or tag mutation, the wrapper prepares
the complete patch queue once in a temporary tree and runs a local preflight
against that tree. On Linux and macOS it requires the .NET 10 SDK. It probes
`DOTNET_ROOT`, then each `dotnet` on `PATH`, then `~/.dotnet/dotnet`, selecting
the first installation whose `--list-sdks` reports a 10.x SDK. The selected
installation is used for all .NET build and test subprocesses; the wrapper does
not install SDKs. It retries dependency restore before building the complete `windows/AgentSpeed.slnx` in Release
with Windows targeting enabled and `--no-restore`, including compilation of all Windows tests.
It then runs the exact Core traffic smoke test
`AgentSpeed.Core.Tests.RemoteConsumerTests.RemoteTrafficIsOptionalAndRetainsCountsAcrossDisconnectAndRestart`
and the complete `AgentSpeed.Presentation.Tests` suite, both targeting `net10.0`
in Release with `--no-build`. The Presentation suite is a required gate, including
CPU and Effort tests without filtering. Failure blocks tag mutation and preserves
the preflight log. This does not run the full Core suite or validate the native
Windows UI.

The preflight runs its test subprocesses sequentially, and the Presentation
suite additionally disables xUnit test collection parallelism within the suite.
The Windows Release job uses the same Presentation setting. All Presentation
tests and their existing thresholds remain in effect; external processes can
still contend for CPU, so this does not isolate the host from load.

The host also determines which native core tests run: Linux requires CMake,
CTest, a C++ toolchain and the Linux core's build dependencies; it configures
and builds the headless core and runs CTest. GoogleTest may be supplied from
`/usr/src/googletest`; otherwise CMake fetches it, requiring network access.
macOS requires Swift and runs `swift test`. A Linux host does not validate the
macOS build, and a macOS host does not validate the Linux build. Preparation,
missing prerequisites, build or test failures stop the release; there is no
bypass. `--plan` does not prepare a tree or require these toolchains.

The local preflight is not the full release gate: native UI validation, tests
on other platforms, and release packaging remain the responsibility of
`Release`.
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
After pushing the tag, the wrapper announces that it is looking for the Actions run, then prints its URL once found.
Redirected output reports job/step changes and a roughly one-minute heartbeat. Transient GitHub API failures retry;
exhausted failures or the workflow timeout stop local observation with an error. Resume the existing run as described
above; a local observation failure alone is not evidence that the remote workflow failed.

Focused maintenance checks run without publishing to GitHub:

```sh
python3 downstream/test-release.py
python3 downstream/test-publish-release.py
python3 downstream/test-manage.py
```

They cover release selection and safety, transient query failures, ambiguous write reconciliation, read-only resume,
published asset immutability, and failed-clone cleanup that preserves pre-existing user directories.

To check a macOS bundle locally against its tested Linux collector, run
`python3 downstream/verify-collector-zip.py <zip> <collector>` from the
maintenance workspace. It checks archive and extracted executable permissions
and byte equality. Release also runs `downstream/test-verify-collector-zip.py` with
synthetic archives covering missing, non-executable, changed and valid files.

Windows release verification compares the installer ProductVersion with the
tag version, allowing only trailing ASCII spaces. Inno Setup's
[SetupLdr version resource](https://github.com/jrsoftware/issrc/blob/main/Projects/Res/SetupLdr.version.rc)
reserves space-filled placeholders for these fields. Executable ProductVersion
verification remains separate and permits .NET build metadata.

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
Windows xUnit analyzer warnings are errors; use predicate assertion overloads
instead of filtering a collection before `Assert.Single`.


The current registry runs the Linux CMake build and CTest suite, and `swift
test` on macOS. Linux needs a C++ toolchain, CMake, and the dependencies used
by the Linux project; if `/usr/src/googletest` is present it is used instead of
fetching GoogleTest. macOS needs Xcode and Swift. The registry also contains
Windows Core, Presentation and native-consumer commands; a Linux run does not
establish native Windows/macOS UI or packaging coverage.

For the headless Linux collector, build on a compatible target Linux host and
architecture from the prepared tree with `macos/scripts/build-linux-collector.sh`.
It requires CMake 3.22+, a C++20 compiler, pkg-config, and development libraries
for zstd, Brotli, SQLite, ICU, OpenSSL and libcurl (`libcurl4-openssl-dev` on Ubuntu); Qt is not required. The resulting
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

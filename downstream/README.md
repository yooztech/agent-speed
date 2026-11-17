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
Release tags are created from the already-committed `downstream/patch-build`
revision selected at invocation, not a later workspace revision. Published tags
and assets remain immutable.

### Windows/macOS parity is mandatory

Every product adjustment must land for Windows and macOS in the same task,
including provider behavior, persistence, refresh scheduling, settings, localized
wording and floating-window interactions. Native implementations may use different
APIs, but user-visible capabilities and behavioral contracts must remain aligned.
Do not report a Windows-only implementation as complete or silently defer macOS.
An intentional platform-only exception requires explicit user approval. Focused
portable checks must identify what they actually exercise; unavailable native UI,
SDK or live-account verification remains explicitly unverified, never a reason to
omit the corresponding implementation.



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
The editor includes alternate connections retained by machine/source deduplication;
each connection remains independently selectable, while readings count a machine's
source only once after applying exclusions. Duplicate host labels are disambiguated
by connection information. On both platforms, an orb-opened dashboard follows that
orb's current selection without waiting for a new sample. Tray/taskbar, menu-bar
and other global dashboard entries use a separate, persisted host/source selection;
they do not inherit any orb's selection or change monitoring/collection settings.
Global dashboard source controls live in General settings and update the open
dashboard without waiting for a new sample. Each orb remains independently
configurable. Hiding or deleting the associated orb closes its dashboard rather
than silently displaying all sources. These changes belong to feature patch 0011;
its remote traffic row integration belongs to 0015. Native desktop behavior
requires Windows/macOS acceptance, not a Linux-only test or syntax check.
For the independent global selection, focused Linux-hosted checks passed 135
Presentation tests and 10 OrbSubset Core tests. The Windows application
cross-compiles with zero warnings/errors, and the changed Swift files pass
syntax parsing. Native Windows interaction, macOS SDK type checking and macOS
behavior tests remain unverified. The Linux portable Swift projection probe
could not use the unchanged production dependency closure: it depends on Apple's
`os`/`OSAllocatedUnfairLock` and `CryptoKit`. No substitute models or visual
assertions were used, and no package, Actions or Release was created.
All 25 patches replay successfully from the pinned baseline; all 3,147 non-build
files in the replayed tree match the checked prepared tree byte-for-byte.

For the earlier orb-bound correction, focused Linux-hosted checks passed 100 orb settings/feed/context
Presentation tests and nine OrbSubset Core tests. The Windows WPF application and
native test assembly also cross-compile with zero warnings/errors; these checks
do not execute a Windows desktop or prove native popup interaction.
Four Swift Core projection/history regressions also pass in a disposable Linux
package using the real implementation and extracted original model declarations;
all 30 changed Swift files pass syntax parsing. Neither check type-checks AppKit
or SwiftUI, executes the macOS App tests, or verifies native popover interaction.
The final 22-patch queue replays successfully from the pinned baseline. Both native
source/test trees match the checked prepared tree byte-for-byte; existing quota
patch ownership and concurrent changes are preserved. No package or Release was
created.
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

### Subscription quota on macOS and Windows (unreleased)

The quota patches add an optional Codenotch-style edge-attached floating surface
and a Subscription page inside the existing Settings window. The floating
renderer is pinned to Codenotch commit `835550a342871779135b6484d6899161c5222f7c`:
macOS uses native shapes and layout, and Windows uses cached WPF vector drawing.
The application, native tests and profiling harness target `net10.0-windows`;
the former browser-specific Windows SDK/CsWinRT target and dependencies, HTML
resource, navigation policy and Runtime-install prompts are removed. The
dashboard orb's existing Vortice Direct3D/DirectComposition dependencies remain
in use and are not part of that removal.
WPF-parsed paths remain immutable: a separate geometry group carries the drawing
transform. Assigning `Transform` directly to a `Geometry.Parse` result throws
before the first native placement because WPF returns a frozen geometry.
Flattened WPF paths may carry a null transform: that means identity, not an
invalid path. The HWND-region converter uses identity in that case and then
appends device DPI. The former grip-only liquid converter is now removed.
The Windows implementation has no WebView2 runtime, browser process, JavaScript
bridge or composition-capture surface. Its native input region follows the
actual visible geometry rather than a transparent host rectangle. Settings retains the
supplied account-card/progress-bar design. The existing transient dashboard
flyout shows at most two summaries near a limit, when blocked, or when sign-in
is required; clicking one opens Settings. Status-item bodies, taskbar widgets,
orbs and History do not carry quota data.
Local and enabled SSH-host Codex/OpenCode Go/Kimi Code accounts share the Subscription
source selector, cards, floating quota panel and qualifying summaries. Remote
sources are identified by host UUID plus provider, not host label; All sources
includes enabled remote hosts, while explicit selections remain host-scoped.
The remote collector reads credentials on its host, queries the supplier there
and returns only structured quota observations over the existing SSH connection.
Borrowed tool sessions remain read-only; remote secrets are never read back to
the desktop. The explicit Kimi key setup action described below sends a newly
entered key from desktop Settings to the selected host over encrypted SSH stdin.
Quota polling is independent of speed sampling and obeys the existing network
consent, automatic/manual selection and persisted provider retry deadlines.
Disconnects retain successful observations as stale with their original time;
unknown or unauthenticated readings are not zero allowance. Older collectors
without the quota command produce a bounded unavailable state rather than a
permanent refresh. This cross-platform remote increment belongs to feature patch
`0023-Read-remote-subscription-quota-over-SSH.patch`; it does not move unrelated
base quota fixes out of 0020/0021 or the Go increment out of 0022. The wire,
polling and credential-isolation contract is in the prepared tree's
`spec/QUOTA.md`. Native desktop and real-account acceptance must be reported
separately from portable checks; this feature does not authorize packaging,
Actions or Release publication.

Collectors advertising `quota_accounts_v1` additionally expose nullable
`accountIdentity: {id, displayName}` in quota snapshots, including cache-only
discovery. The legacy nullable-string `account` field remains unchanged for
older native clients. Only the current CLI account per provider is discoverable;
clients bind by host, provider and opaque account ID, retaining old bindings
offline rather than following a host's replacement account. Codex has an explicit
account claim and receives a private, persistent random mapping; token rotation
for that claim preserves the ID. Missing/rejected credentials or an unsafe or
unavailable identity store are not bindable. Deleting the store resets its
identity namespace. OpenCode Go and Kimi expose no verified stable user-account
claim in their credential stores and return null rather than treating a token,
session digest, credential row or organization as an account. Their ordinary
quota behavior remains available. No raw account claim, token or token hash is
sent to clients. Generic identity protocol and Windows/macOS consumer integration
belong to 0023; Kimi-specific null-identity coverage belongs to 0024.


Focused remote-quota checks passed on Linux: 16 collector/provider/real-stdio
regressions, 10 Windows Core wire/persistence tests, 173 selected Presentation
tests, and 14 Swift wire/controller/remote-lifecycle tests using the real portable
sources under Swift 6.2.4. The Windows application and native test assembly
cross-compile with zero warnings/errors; five changed macOS native integration
surfaces pass syntax parsing, not SDK type checking. A throwaway real-collector
stdio scenario passed its cache-only replies through the production Windows
consumer and Swift decoder while metrics continued; the synthetic credential
was not transmitted and missing observations remained unknown. All 23 patches
replay from the pin, and all 3,126 replayed source files match the checked prepared
tree byte-for-byte. Real supplier accounts, native macOS SDK/desktop and Windows
desktop interactions remain unverified. No package, Actions or Release was made.

#### Provider implementation reference: Codenotch first

Codenotch is the quota implementation reference as well as the visual reference.
Before adding a supplier, inspect its existing adapter at the pinned commit
`835550a342871779135b6484d6899161c5222f7c`: credentials, endpoint selection,
response parsing, authentication/entitlement states and persisted backoff.
Verify differences against official supplier sources rather than independently
rediscovering an already implemented integration. This does not authorize
enabling every supplier or upgrading the reference pin.

OpenCode Go is already covered by Codenotch's
[`OpenCodeProvider.swift`](https://github.com/vinzdg/codenotch/blob/835550a342871779135b6484d6899161c5222f7c/Sources/Providers/OpenCodeProvider.swift),
`OpenCodeCredentials.swift`, `OpenCodeUsage.swift` and `OpenCodeSchema.swift`.
The pinned implementation distinguishes Go API keys (`/zen/go/v1/usage`) from
OAuth credentials (`/inference/go/v1/usage`, with the actual organization header).
Its OAuth 401 handling checks Console authentication before concluding that a
missing Go plan means sign-out. Do not assume API keys and OAuth tokens can use
the same route, or that the local machine has a signed-in account. Newer official
OpenCode sources may differ; document the selected credential/route contract and
its evidence instead of silently mixing versions. Preserve the MIT notice when
porting reference code and distinguish synthetic checks from live-account proof.

Kimi Code is added for local Windows/macOS accounts and enabled SSH Linux hosts
by `0024-Add-local-and-remote-Kimi-Code-quota.patch`. Its original OAuth path
follows the pinned Codenotch `KimiCredentials.swift`, `KimiProvider.swift` and
`KimiUsage.swift`: read-only `credentials/kimi-code.json` under `KIMI_CODE_HOME`
or the current user's `~/.kimi-code`. Kimi Code CLI owns OAuth login and renewal;
Agent Speed never refreshes or modifies its session. The Kimi Code subscription
API key is distinct from a Moonshot Platform pay-as-you-go key.
The adapter preserves five-hour, weekly, monthly-total and monthly-code windows
when reported, preferring precise `used_ratio` values over legacy rounded counts.
Unknown readings remain unknown; an absent plan is not zero allowance.
Automatic polling uses the existing five-minute cadence, while successful Kimi
requests impose no hard manual-refresh floor. Persisted retry/backoff and
account-isolated structured caches remain binding. See `spec/QUOTA.md` in the
prepared tree for the wire, credential, parser and status contract.

Both native Subscription settings let users configure a Kimi Code subscription
key and region for the local source or any enabled remote host, without a local
CLI login or manual remote configuration. Keys take precedence over borrowed
OAuth; an invalid or inaccessible configured key never silently falls back to a
different CLI account. China and International use their corresponding fixed
`api.kimi.com` and `api.kimi.ai` Code usage endpoints. API keys do not share the
CLI access token's fifteen-minute expiry. The CLI renewal limitation remains
when no key has been configured.

Local keys use current-user DPAPI on Windows and Keychain on macOS. For a remote
source, the desktop sends the newly entered key through the existing no-PTY SSH
stdin channel, never argv or shell interpolation; the collector automatically
stores region and key in an owned private `~/.agent-speed/quota/kimi.json`
(`0600` under private `0700` directories). Users do not create or edit this file.
The separate correlated `kimi_credentials` control supports metadata, set and
delete; responses never contain secrets or key fragments. Saving and supplier
verification are distinct operations, and verification respects network consent
and provider backoff. The UI masks entry and never reads a saved remote key back.
No key is included in ordinary settings, quota observations, logs or exports.
On both desktops, the key editor closes automatically only after the save and
quota verification both succeed. Save-only, network-consent/backoff and failure
outcomes keep the editor open with their existing messages; key removal does not
close it.
This key channel deliberately extends the OAuth-only pinned Codenotch reader;
the official Code documentation confirms subscription key/region support, and
CodexBar documents key-authenticated `/usages` reads. See the prepared
`spec/QUOTA.md` for the complete storage, wire and account-isolation contract.

Focused Linux-hosted Kimi checks passed: 26 collector/provider/real-stdio
regressions (including cache-only three-provider replies, expiry and continued
metrics), 44 Windows Core provider/wire tests, 177 selected Presentation tests,
and 26 Swift provider/wire/remote-lifecycle tests using the real sources in a
disposable Swift 6.2.4 package. The Windows application/native test assembly
cross-compiles; five changed macOS presentation files pass syntax parsing.
These are not native macOS SDK or Windows/macOS desktop checks, and no live
authenticated Kimi account was queried. All 24 patches replay successfully from
the pinned upstream baseline. No package, Actions or Release was made.

The regional key/provisioning extension passed 43 focused collector and real-stdio
regressions, 106 Windows Core key/provider/transport tests, 72 selected Presentation
tests, and 28 portable Swift 6.2.4 provider/transport/controller tests. The Windows
application and native test assembly cross-compile, and eight changed macOS native
integration/settings files pass syntax parsing. A throwaway production Windows
Core consumer drove the actual isolated collector test executable over stdin/stdout:
regional key set/get/delete, private `0600` persistence, cache-only quota, expired
CLI rediscovery, continued snapshots and no secret echo passed without supplier HTTP.
The collector test executable's private temporary HOME is not a deployed production
collector or an SSH acceptance test. Combined key/account-identity integration also
passed 21 Windows wire tests and 12 portable Swift wire/controller tests. Real Kimi
key/account access, actual Keychain/DPAPI execution and native desktop interaction
remain unverified on this Linux host. No package, Actions or Release was created.
The merged collector checks also passed nine Codex account-identity regressions.
A same-key delete/recreate race exposed filesystem revision reuse; managed keys
now persist a fresh random internal revision on every save. The repaired ABA,
regional persistence, unchanged-key backoff and protocol-isolation checks pass.
Revision nonces are not returned to clients and do not reset supplier cooldowns.
The complete 24-patch queue, including regional keys and the concurrent safe
account-identity/native-geometry changes, replays successfully from the upstream
pin. Key provisioning remains in owning feature patch 0024; generic account
discovery remains in 0023.

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
captures and use explicit AppKit image/color/file types. Release run
`43555523521` compiled the application and tests, then failed four quota tests
with 15 assertion issues. The subsequent repair shares the real settings-arc
target between window interception and the button, tests reset-date semantics
instead of punctuation, and compares pixels against matched native controls
in a common color space. Release run
[`43559746957`](https://github.com/yooztech/agent-speed/actions/runs/43559746957)
then compiled the application and tests; its two remaining failing notch tests
reported 58 issues on each attempt, all from full-strength green/blue samples
being compared with source-color literals. The matched native-control
comparisons passed. Native offscreen rendering, preference-rendering checks,
pixel comparisons, and PNG encoding comparisons are now moved out of ordinary
`QuotaNotchTests` into the explicit debug-only `QuotaNotchVisualHarness` route.
The actual notch/settings-orb rendering and provider behavior are unchanged;
the optional harness still renders those real components, retains the canonical
paint/attenuation comparisons at their existing thresholds, and writes all 32
2x edge/state PNGs. From a prepared tree on macOS, run
`swift run --package-path macos --configuration debug AgentSpeed --quota-notch-visual-checks /tmp/quota-notch-native`
to opt into those diagnostics. They are not discovered by `swift test` and do
not block Release as ordinary tests. The registered `QuotaNotchTests` suite keeps
nonvisual animation-state, hover/drag ownership, unknown/status and reset-formatting
behavior only. Drawing, geometry-coordinate, bitmap and shape-point assertions
are not ordinary test or Release gates and are not replaced with similar tests.
Release run `43695455501` compiled the macOS application and tests, then failed four
quota tests among 1,637 tests: two brittle lifecycle waits, an exact floating-point
layout-pin test, and a genuine resting-grip input-path assertion. The correction
deletes the layout-pin test and unused constants, materializes CoreGraphics stroke
outlines before path operations, and uses controlled refresh ticks and actual task
completion for lifecycle tests instead of short sleeps or polling deadlines. It
does not restore live-window, synthetic-pointer or capture gates on either platform.
The existing resting-arc test retains center pass-through and painted-arc input
checks. Linux syntax/portable checks are not native AppKit/SwiftUI verification;
the changed native geometry still requires macOS execution.
The resting-arc regression checks the final grip input and host hit routing,
including painted arc points, rather than requiring each internal contour to
exclude the center. This removal does not establish native verification.
The four formal controller lifecycle tests pass on Linux with Swift 6.2.4 using
the real controller, scheduler, providers and test source in a disposable package.
All seven changed Swift files pass syntax parsing. The 22-patch queue also replays
successfully, and the replayed native source/test trees match the checked prepared
tree byte-for-byte. These results do not establish native geometry or hosting-view
hit-test acceptance; no new Release run was triggered.

Release run `43707052770` first failed the hover-grace test, then its retry
terminated at `NSApp.appearance` in `AppModel`. The orb-dashboard test activated
the real appearance observer without first creating `NSApplication`, unlike
normal startup. Its fixture now initializes AppKit before model activation;
production appearance handling is unchanged. Quota hover grace now uses the
existing main-queue scheduler, armed at departure rather than after an enqueued
task begins. Its three behavior tests use controlled time for the unchanged
250-ms interval, cancellation and one-time expiry notification. The actual model,
scheduler and three tests pass together under Linux Swift 6.2.4; all three
changed Swift files pass syntax parsing. These checks do not execute AppKit or
establish that the macOS Release gate passes.
The six-dot grip retains its original arc-to-disc-to-six-drops transition on both
platforms. The intermediate disc is intentional, not a defect to remove. macOS
liquid rendering follows the existing Windows fractional-alpha threshold,
eroded inner fill and premultiplied raster composition rather than a binary
contour followed by a separate stroke. Windows retains its original visual
effect; no corresponding Windows flicker has been reproduced.
Grip hover is acquired by physical pointer movement into the control, not by
animation moving underneath a stationary pointer. Once acquired, its initial
input contour and fixed final-pose routes retain ownership until real departure,
without retaining duplicate paint or intercepting the rest of the transparent
window. Held drag and reduced-motion behavior use the same interaction contract.
These base corrections belong to macOS patch 0020 and Windows patch 0021.
Quota automation checks nonvisual provider, persistence, lifecycle, animation-state
and hover/drag ownership behavior. It does not validate drawing. Pixel/color,
snapshot, glyph/path, contour/topology, raster/filter-output, layout-coordinate
and shape-point assertions are removed from ordinary tests on both platforms,
including geometry tests presented as hit-region verification. Drawing acceptance
requires the actual native surface or explicitly manual visual diagnostics.
Without that environment, appearance remains unverified; portable assertion
counts, extracted geometry scripts and CI reruns are not substitutes.

The drawing-gate cleanup changes tests and their registration descriptions only;
production drawing and the disc animation are unchanged. Windows Presentation and
native test assemblies compile; retained Swift test source passes syntax parsing,
not macOS SDK compilation. No tests, drawing probes, CI or Release runs were
executed for this cleanup.
The full 25-patch queue replays successfully and matches the checked cleanup tree
byte-for-byte. This proves queue integrity, not visual correctness.

Release run [43797161025](https://github.com/yooztech/agent-speed/actions/runs/43797161025)
failed both native gates despite the earlier cross-build and portable checks.
Windows compiled but failed all five dispatcher-lifecycle cases because their
setup asserted that Subscription settings contained exactly one button; the Kimi
key action legitimately adds another. The two unrelated whole-page button-count
assertions are removed where this dispatcher/reader integration test is introduced,
in 0022; owner-dispatcher delivery, result publication and all invalidation checks
remain. macOS failed to compile ten assertions where
Swift Testing rewrote a mutating `intent.update` call through an immutable
receiver. Patch 0020 evaluates each mutation into a local Boolean before
`#expect`, preserving the call order and assertions. Syntax parsing and extracted
precondition harnesses did not exercise that macro expansion; they were not proof
of native test compilation. Neither failure is treated as a runner flake, and no
test is skipped or failure gate relaxed. Do not use another CI or Release run as
a debugging step or ask the user to validate these fixes through CI. Exercise the
actual failure paths locally; unavailable native checks remain unverified, not
passed. No Actions or Release run is authorized by these corrections.
The corrected Windows application and native test assembly cross-compile with
zero warnings/errors. Two Swift 6.2.4 tests using the real Testing macros and the
unchanged production intent type compile and pass with strict concurrency and
warnings as errors. These checks cover the macro failure and assembly compilation,
not execution of the five Windows WPF cases or the complete native macOS suite.

Release run [43800228990](https://github.com/yooztech/agent-speed/actions/runs/43800228990)
then exposed separate failures: Windows `HistoryServiceTests.StopAndDisposeAreIdempotent`
imposed an undocumented five-second stopwatch limit, while macOS reported 17 real
grip paint/input issues. macOS no longer uses SwiftUI boolean path normalization
to combine grip strokes and clips: the same explicit primitive/clip footprint
now drives source coverage, painted support, native hosting-view input and hover.
The production geometry file can compile independently, but that does not verify
native drawing. Previous portable geometry/pixel assertion counts are withdrawn
as drawing-verification evidence; their ordinary drawing gates are removed rather
than replaced. The original disc transition and fractional-alpha filter remain.
Native SwiftUI/AppKit rendering and visual acceptance remain unverified here.

Dedicated patch 0025 replaces the upstream history stopwatch assertion with real
Ready publication, worker termination/restart and disposed-state checks. Its test
fixtures explicitly isolate all 16 source roots: the previous defaults could scan
the developer's real omp transcripts. All six actual `HistoryServiceTests` pass
locally with the isolated roots. No Windows/macOS production history behavior is
changed. No CI, Actions or Release run was launched to verify these corrections.
The full 25-patch queue replays successfully, with all 3,151 source files matching
the locally checked repair tree and reconstructed tree byte-for-byte.

The redesigned native surfaces and real-login behavior remain unverified on
Windows and macOS. Portable geometry checks and SVG previews validate shared
shape calculations, not native window placement, hit testing, font rasterization
or mixed-DPI behavior. Do not claim pixel identity without matching native
screenshots. Claude quota and Linux quota interfaces are future phases.

The Windows native replacement retains the source-neutral Subscription page and
Light, Dark or System appearance. The multi-window feature adds a real OpenCode Go
adapter beside Codex. Quota bars, rings and flyout summaries show remaining allowance;
period colors are stable and warnings are separate. All providers on macOS and
Windows omit the low-remaining-quota red dot on floating rings, without a
replacement; rings, percentages and other status indicators are unchanged.
Dashboard and quota-window visibility controls remain independent.

The Windows quota fixes preserve Nonzero winding in transformed grip geometry
and return asynchronous quota completion to the surface's owning Dispatcher.
Reader disposal, source removal and consent revocation still invalidate pending
results. Settings composition checks support multiple account cards, and flyout
bars show remaining allowance rather than used allowance.

The downstream-only live-HWND region, synthetic desktop mouse-path and native
capture harness is removed. It is not an additional Release requirement for
quota windows. Nonvisual state/ownership, provider, persistence and refresh-lifecycle
checks remain. Drawing/shape assertions and geometry-point substitutes do not
establish native click-through, pixels or visual acceptance and are not gates.

The approved compact multi-window design retains the real supplier marks, matte
center disks, round progress caps and native concave flares. Rings run longest
outside to shortest inside: month, week, five hours. Center disks now shrink to
36/30/24 logical pixels and marks to 22/19/16 for one/two/three-or-more windows.
Four-pixel strokes with six-pixel radial pitch give 52/58/64-pixel outer diameters
for one/two/three rings, instead of increasing a fixed large center by 16 per ring.
Each account has aligned compact reading rows beneath its ring group, not a long
horizontal legend repeating the supplier/host on every period. Ordinary periods
use short labels and percentages; five hours is `5h` in the body and `5小时额度`
in Simplified Chinese details. Distinct feature scopes and arbitrary supplier
durations remain identifiable, and no windows or over-limit numeric values are
hidden. Painted bounds, placement and input geometry share the same four-edge
metrics. Source-specific credentials, account isolation and backoff stay separate.
The compact follow-up preserves these existing ring, center-disk and mark sizes:
the three-ring group is already 64 logical units across, with a 24-unit disk,
16-unit mark and four-unit clearance to the innermost ring. It does not shrink
production rings from the earlier preview's erroneous 76-unit baseline. Instead,
each account receives its own ring-and-reading extent, avoiding a single-ring
account inheriting the tallest multi-window account's blank space. Body padding
and inter-account spacing are tightened without reducing reading fonts or hiding
windows. Native font measurements still determine the final envelope; preview
dimensions are not a pixel-size contract.
Focused compact-layout checks pass 121 quota Presentation cases; the Windows
application and native test assembly cross-compile with zero warnings/errors.
All five changed Swift source/test files pass syntax parsing, and the actual
portable Swift layout implementation executes the varying-cell layout proof.
A throwaway C# probe links the production geometry and projects 20 growing-source
layouts across all four edges to browser-inspected SVGs. Its reading measurements
are synthetic: neither these projections nor portable checks establish native
font rasterization, desktop hit testing or Windows/macOS visual acceptance.
No package, Actions or Release is created for this change.
The complete 24-patch queue replays from the pin; all 3,151 replayed source files
match the compact prepared tree byte-for-byte, including retained concurrent Kimi
changes. The compact implementation belongs to 0020/0021, with only necessary
multi-window integration in 0022 and later patches rebased onto that layout.
The width refinement trims horizontal chrome and bases both native reading rows
on measured content instead of reserving a fixed macOS multi-window text width.
It preserves ring/mark sizes, reading fonts and complete percentages, including
two-decimal Kimi values; the widest enabled account still determines the shared
shell. Long readings may legitimately require more width. It does not change
vertical compact spacing, quota refresh or grip behavior. No new visual, pixel,
geometry-coordinate, glyph or supplier-count tests are added, and width snapshots
are not acceptance gates. Native appearance remains a manual acceptance item.
For left/right attachment, horizontal body insets change from seven to four
logical units per side; the minimum depth remains 70. Top/bottom depth rules,
eight-unit along-edge padding/account gaps and ring-to-reading spacing stay as
before. Both platforms measure complete label/value strings without the former
macOS fixed reading width or native text-width caps, so long content keeps its
natural required width rather than wrapping or truncating to force a target.
This refinement adds or modifies no test files or assertions.
The Windows application cross-build passes with zero warnings/errors. Both
changed Swift files pass syntax parsing, and the shared production layout file
passes Swift 6.2.4 type checking. These are compilation checks, not native
AppKit/WPF rendering or text-measurement acceptance; no drawing tests, CI run,
package or Release is used to validate this visual adjustment.
All 25 patches replay successfully, with all 3,146 tracked source files matching
the checked width-refinement prepared tree byte-for-byte.

The multi-window/OpenCode Go feature is carried by
`0022-Add-multi-window-quota-and-OpenCode-Go-provider.patch`. Focused Linux-hosted
verification passed 110 Codex/Go Core tests and 299 quota/settings Presentation
tests. The subsequent Go pacing alignment passed all 26 Go tests again; Codex
was unchanged. Windows native tests cross-compile with no warnings/errors and a
self-contained Windows x64 development build publishes successfully. A temporary
Swift 6.2 package ran the actual portable quota models/providers and their 24
tests using SQLite and swift-crypto; seven changed native Swift files also pass
syntax parsing, which is not an AppKit/SwiftUI SDK build. A browser-inspected
production-geometry probe covers two three-window sources on all four edges,
but is not WPF font/pixel/input proof. The current environment has neither local
OpenCode credentials nor an authenticated Console session: no real subscription
request or native desktop acceptance has been claimed. These checks are not a
Release and do not authorize publication.

Quota base corrections belong to their platform's existing feature patch:
`0020` owns macOS Codex behavior and native surfaces, `0021` owns Windows Codex,
and `0022` owns the multi-window/OpenCode Go increment and its integration.
Shared prerequisites must be introduced before their consumers; patch 0022 is
not a holding area for unrelated macOS corrections. Codex and Go restore private,
account-partitioned structured snapshots offline as stale; Codex adds optional
reset-card count/expiry and the same one-shot startup-floor exception, while
authentication rejection, legacy schedules, failures and usage/reset-endpoint
429 deadlines remain binding. Source selection and automatic/manual polling now
belong to the application lifecycle rather than a visible subscription surface.
Automatic refresh wakes an unavailable source at its provider retry deadline,
instead of waiting for the next five-minute poll. Before the current account has
any validated successful observation, transient failures retry after 5, 10, 20
and then at most 30 seconds. The native timer and the actual local/remote provider
request floors both implement this cadence; a timer-only wake blocked by a long
provider floor is not sufficient. A valid cached observation is shown stale and
does not count as a cold start. First success exits cold pacing and restores the
normal cadence/backoff. HTTP 429 and explicit Retry-After on other error/probe
responses remain authoritative, including waits longer than the normal cadence;
legacy future deadlines of unknown cause are not blindly shortened. Auth/access
and unsupported states do not enter rapid retry. Remote readiness triggers the
existing immediate startup read. Source/network/automatic-off/disposal cancellation
and manual-mode semantics remain intact; unknown is never filled with zero.
Cached or stale quota observations retain normal floating-cell brightness on both
platforms: provider marks, rings and readings do not dim because of observation
age, refresh failure or disabled network access. Existing status and original
observation timestamps still distinguish retained data from a successful refresh;
normal expansion animation and ring-track contrast remain unchanged.
Startup retry policy distinguishes a genuinely cold account from a valid cached
observation. With automatic refresh enabled, the former uses the 5/10/20/30-second
transient-failure cadence above; a cached account uses normal backoff, starting at
60 seconds, then 120 and 240 seconds. Automatic refresh disabled means the startup
read does not enable background retries. Authentication/access rejection needs
user action, and persisted rate-limit or explicit Retry-After deadlines still bind.
Focused follow-up verification passes 127 Windows Core Codex/cold-start/remote
cases and 30 real-source Swift cold/warm-start/controller/lifecycle tests. The new
warm-start scenario restores a valid cached observation, fails startup HTTP with
503, keeps the stale reading, prevents an early request at 59 seconds and recovers
through an actual HTTP request at 60 seconds. The corresponding Windows native
regression compiles with the application and native test assembly (zero warnings
or errors), but cannot execute on this Linux host. Three changed Swift files pass
syntax parsing; native WPF/AppKit brightness and live-account startup failures
remain unverified. This follow-up does not change production retry policy or run
packaging, Actions or Release.
All 24 updated patches replay from the pinned baseline, and all 3,139 replayed
source files match the verified prepared tree byte-for-byte.
Base platform fixes remain in 0020/0021, Go in 0022, collector/remote integration
in 0023 and Kimi in 0024; no unrelated visual changes accompany this correction.
Cold-start verification passes 186 Windows Core provider/transport cases, ten
portable retry-policy cases, 76 real-source Swift provider/controller/remote tests
across seven suites, and 32 collector quota cases. The deadline tests count actual
transport requests before and at 5/10/20/30-second deadlines, not merely timer
wakes; they cover first success, warm cached data, rate limits/Retry-After,
restart/legacy pacing, source cancellation and immediate remote readiness.
Windows application/native tests cross-compile with zero warnings/errors. These
are synthetic isolated HTTP checks, not live supplier-account or native desktop
execution. No visual layout, wire/credential route, package or Release changed.
The corrected 24-patch queue replays from the pin with all 3,138 source files
byte-identical to the checked tree. Owning-boundary checks also pass: 37 base
macOS provider/controller tests without Go/remote/Kimi, 97 base Windows Codex/cold
HTTP tests plus native app/test cross-compilation, and collector/test syntax
checking at 0023 before Kimi prerequisites are introduced at 0024.
Quota cleanup removes `QuotaNotchBodyInputTests` and other ordinary test assertions
that freeze historical press points, default body/card dimensions, ring/logo/drop
sizes, outline clearances or literal path fragments. These visual measurements
are not Release contracts and must not be re-pinned after adding a supplier or
changing layout. Equivalent macOS dimension assertions are removed too. Dead
test-only clearance helpers are deleted; live placement/input helpers remain.
Provider/window data, cold-start/rate-limit/cancellation behavior, persistence,
drag/hover lifecycle and relationships derived from current paint/input geometry
remain tested. No skip, production-layout workaround or new Release run is added.
Focused cleanup verification passes all 84 remaining Presentation geometry/layout
cases. The final and base-0021 Windows application/native test assemblies compile;
the base boundary reports zero warnings/errors. The changed macOS native test file
passes syntax parsing, not AppKit execution. All 24 patches replay, and all 3,137
source files match the checked tree byte-for-byte; the obsolete body-input test
file remains absent. Neither full Release preflight nor Release publication was
rerun for this cleanup.
The subsequent native Windows Release run `43728516768` failed four edge cases in
`AllTripleRingsExactReadingsAndScopeExtrasStayInsideNativeBody`: all three reading
strings passed the concatenated-text check, but the test assumed each reading
occupied one complete `GlyphRun` and counted only two matching runs. This is not
evidence that a quota window was missing. The entire theory and the separate
provider-logo geometry-node/path-serialization assertions are removed, together
with their unused drawing-tree reflection helper. Provider cell availability,
multi-cell extent and native interaction coverage remain. macOS has no equivalent
glyph-run/path-node count assertion. No production renderer is changed to satisfy
these tests, and the cleanup does not initiate another Release run.
For this follow-up cleanup, the Windows application and native test assembly
cross-compile with zero warnings/errors. All 24 patches replay, with all 3,137
source files byte-identical to the frozen cleanup source. Native Windows test
execution remains unavailable on the Linux host; compilation is not represented
as a passing native test run or Release gate.
Earlier compact-layout/deadline checks passed 155 formatting/geometry cases, the four
replacement edge-containment cases and nine deadline/backoff policy cases.
Windows application/native tests cross-compile with zero warnings/errors.
The real Swift controller and remote-lifecycle regressions pass under Swift
6.2.4, including a provider 429 deadline, independent source wakeups and queued
cancellation; extracted production geometry/label proofs also pass. Five changed
native Swift source/test surfaces pass syntax parsing. A browser-inspected
preview uses the production Windows geometry, formatting and real logo paths for
all four edges and one through four rings; browser text shaping is approximate,
not native WPF or AppKit rendering/input acceptance. No package or Release was
created for these checks.
The corrections remain in their owning patches: base Mac lifecycle/single-ring
and wording in 0020, base Windows lifecycle/single-ring and wording in 0021,
multi-window rows/adaptive geometry in 0022, and remote integration in 0023;
Kimi stays in 0024. The final 24-patch queue replays successfully, and all 3,136
source files match the checked final tree byte-for-byte. At the 0020 boundary,
all twelve real controller tests pass in the portable Swift package without Go,
remote transport or Kimi dependencies. The 0021 single-Codex Windows application
also cross-compiles with zero warnings/errors before its Reader migration.
macOS now exposes automatic refresh, All sources/individual source selection and
the independent default-off Keep expanded switch. Native account cards include
all remaining-allowance windows, reset countdowns, balances/reset cards and the
original update timestamp. The floating panel includes every enabled account
and its windows, with hover folding, the external arc/disc/six-drop grip, drag
capture/placement, context-menu settings and local observation-boundary labels.
The old single-provider picker and gear/settings action are removed. Eleven
changed native Swift/test files pass syntax parsing; two tests extracted from
the actual production grip-motion implementation pass, including exact delayed
poses, return-to-idle and reduced motion. This is not native UI acceptance.
The opt-in macOS visual harness now defines 176 four-edge/theme/scale/state
notch captures and four localized details captures; it has not run on this host.
The repartitioned queue replays all 22 patches in a fresh prepared tree. Its final
Git tree is exactly `872156c9c88834c214b2342067babd7a6973f523`, identical to the
pre-repartition tree: this changes patch ownership, not the delivered source.
Patches 0001–0019 are preserved; 0020 now contains the complete base macOS
implementation, 0021 retains the base Windows implementation, and 0022 adds Go
and its multi-window integration without hiding the base platform corrections.
At the 0020 boundary alone, the real Codex/model/persistence sources compile in
a Linux Swift 6.2 portable package without Go or SQLite; twelve base native
source/test files also pass syntax parsing. These dependency checks are not a
macOS SDK build or native desktop acceptance. The final-source tests below were
not rerun for this ownership-only change because the final tree is identical.
The Linux Swift 6.2 portable package executes the real models, providers and
persistence code: all 32 tests in four suites pass, including cache corruption,
startup throttling, reset-endpoint 429, token rotation and cancelled/replaced
requests. Controller code and its tests compile with Swift 6 strict concurrency,
but their executable cannot link against this host's Swift 6.2.0 Observation
runtime (`swift::threading::fatal` is missing from its dynamic runtime exports).
The attempted Swift 6.2.1 toolchain download timed out; no product workaround,
suppression or substitute controller was introduced. Controller runtime tests,
macOS SDK builds, native desktop rendering/input and real accounts remain
unverified here. This is not a package or Release.


The floating surface is drawn directly with cached WPF paths, glyphs and text.
The main surface uses a bounded, stable animation canvas and the details card
uses a separate tightly sized HWND; both are nonactivating. For one Codex source,
the canvas is 70.5 by 214.37 DIP vertically or 190.37 by 98.5 DIP horizontally.
Unused canvas is excluded from input. Rendering, hit classification and the
Win32 window region share each frame's body and external grip geometry/mask.
Region coordinates and placement use the monitor's physical work area and DPI.
The browser, navigation/nonce bridge, screen-sized transparent input surface,
cursor polling and full-window capture/diagnostic alpha scans remain removed.
Only the control family's finite arc/disc/drop transitions use the tight local
source rasterizer, alpha filter and mask-to-input conversion; they never filter
the body or desktop. Mouse events and finite transitions drive updates; settled
or hidden surfaces have no animation subscription and do not rebuild Settings
on cursor movement.

By default, without pointer attention, the quota surface collapses to a black 10-by-79-DIP
edge tab (79 by 10 on a horizontal edge). Pointer entry expands it; leaving the
body and details card starts the existing 250-ms grace period before collapse.
Details-card hover, an open context menu and dragging keep it expanded. Only the
painted tab accepts input while collapsed; the stable animation canvas does not
reserve a transparent desktop-sized hit area. The settings shortcut and gear
remain absent; Settings stays available through the existing context menu and
tray entry. Native-dev.9 corrects the earlier removal of the necessary visible
entry arc: an expanded resting body shows an independent quarter arc in its
trailing flare pocket before hover. It is not the body's own flare. The arc
remains visible when the temporary disc divides into six nearby dots; the final
pose is Arc=1, Disc=0, Reveal=1, without a permanent disc, gear or settings action.
The original body stays 104 DIP vertically or 80 DIP horizontally, with no footer.
Arc and temporary disc retain their 0.9 reference scale: arc radius25.65,
fill stroke6.12 plus two-DIP edge outline (8.12 total), disc radius20.97 DIP.
The enlarged dot grid is independently diameter8.0/pitch12.5 DIP, with the
existing30% hover growth to10.4 DIP, one-DIP outline and unchanged squeeze ratios.
Its outlined envelope is34 by21.5 DIP neutral or36.4 by23.9 DIP at settled hover;
hitboxes, fan, corridor and liquid core/neck consumers share those real dimensions.
The arc/body are not globally enlarged. Their common anchor remains edge-local
(38.7, BodyEnd + 38.7); final drops move only eight DIP tailward from that anchor,
not the old 43.2-DIP reach or intermediate proposals. Production stroke geometry
gives an 8.49-DIP body-to-arc gap and 17.23-DIP body-to-disc gap; the probe records
the actual nearest quarter-arc/dot outlined clearances, not axial offsets.
The shared motion restores the arc's 340-ms delay plus 950-ms initial separation,
220-ms arc-to-disc morph, then 20-ms delay plus 420-ms drop division. On leave,
drops return for200 ms, wait100 ms and roll the temporary disc back into the arc
over400 ms; quick arc return during collapse takes260 ms. Hover uses the original
220-ms-response/0.55-damping spring, with held squeeze and immediate reduced motion.
Only actual painted arc/disc/drop geometry and its small connecting routes form
one Grip family. The old body-edge blind hotspot is removed. Touching an emerging
arc carries its exact last-painted GooArc phase/return flags until family return
finishes, rather than replacing the touched paint or using an invisible snapshot.
An activation-only, nonzero-filled fan of eighteen eight-DIP-wide straight routes
connects both arc ends and midpoint to all six dots; overlap unions without holes.
It is not a whole transparent circle or canvas, and the unhovered arc has no fan.
Pointer-leave is reclassified against the painted frame, so a native-region update
does not close the control under a stationary pointer. Grip and Alt-body presses
still capture the painted pose before the stable four-DIP press-DPI threshold.
Pending/active gestures hold expansion; release resamples and persists the anchor.
Reduced motion settles every channel and idle states stop rendering.

Native-dev.10 adds the Subscription switch “Keep expanded” / “保持展开” directly
after the floating-panel visibility row, with the same OptionRow and native toggle
style and four-language automation names. `quotaNotch.keepExpanded` defaults false;
missing or nonboolean values preserve hover collapse without a version migration.
It is independent of `quotaNotch.show` and monitor/edge/along placement. Enabled
startup and re-show install an expanded body before the first visible native frame,
even if Settings has never opened. The body and its resting entry arc stay open,
but the six drops still require real control-family hover/hold. The switch does not
invent pointer attention, open a card, refresh quota or reconstruct a provider.
Turning it off applies immediately while retaining real body/card/menu/grace and
pending/active capture attention until that interaction ends. Hide/close clear
interaction and stop finite rendering; re-show reads the saved preference again.
The approved dev.9 dimensions, placement, paint and liquid-control motion are unchanged.


The floating details card's successful bottom label reads “刚刚更新”,
“X分钟前更新”, “X小时前更新” or “X天前更新”, derived from its original ObservedAt and
localized in all four languages (English “Updated …”), instead of a timeless “latest”. Missing time is unknown;
future timestamps never display negative ages. Offline/error/stale/waiting and
authentication states keep precedence. Only the visible details card and open
tray summary run local observation-boundary clocks: a reading aged 59 or 119
seconds updates one second after opening. Snapshot/visibility changes reschedule
the deadline; hidden/unloaded/disposed displays stop it, and the main black tab
does not run this timer. These clocks make no HTTP requests and do not change
provider polling, startup cache, account isolation or old/new 429 protection.

Native-dev.10's final new-preference serializer/default-layout checks, Windows
Release test cross-compile, production-settings save/reload proof, full formal
queue tree replay and self-contained win-x64 publish are recorded in
`artifacts/quota-native-dev-10/BUILDINFO.json` and `verification.log`. The relative-age
wording delta comes from isolated commit `2d9e63b43df755ebddadf6e47069228eb2cf9400`;
its agent reported QuotaFormatTests 52 passed once. That external result is
attributed, not represented as a local dev.10 run or rerun. Core/Geometry/Motion
checks are not rerun because those implementations did not change. Windows
regressions cover first SourceInitialized paint/native region, pin/unpin and real
attention/grace/card/capture/menu lifecycle, independent resting arc, hidden/re-show
and finite/reduced motion. They are cross-compiled only here, not executed natively.
The page-to-service regression includes disk reload and handler/factory counters
after advancing beyond the quota floor; no native UI screenshot is claimed.
The new package remains unpublished: no tag, push, Release or full-platform gates.
The dev.10 source archive captures the actual current formal queue. Concurrent,
pre-existing documentation edits in patches 0014 and 0016 are preserved, not
replaced with dev.9 inputs. BUILDINFO records their current hashes and the final
replayed/built tree; this task modifies none of patches 0001–0020. Narrow settings
checks are reused only after byte-identical affected production/test source proof.


Native-dev.9's narrow QuotaNotch Geometry/Orb/GripMotion checks, Release Windows
test cross-compile and self-contained win-x64 publish are recorded in
`artifacts/quota-native-dev-9/BUILDINFO.json` and `verification.log`. Core and
QuotaFormat are unchanged and are not rerun or assigned copied historical counts.
The self-contained `probe/motion-preview.html` plays actual production frames,
including unhovered visible arc, liquid entry, temporary disc, retained arc with
same-pocket drops, captured emerging-arc carry, hover/squeeze, return and reduced
motion on four edges in both themes. Its diagnostic switch shows only the actual
compact activation fan. Liquid frames show clipped production vector sources,
not a substitute shader: native WPF union/flatten/local-goo pixels cannot run here.
The prior original browser proof and dev.8 evidence remain intact; the new
`probe/before-after.png` labels those sources alongside dev.9 states honestly.
Windows regressions cover all eighteen arc-to-dot slow straight transfers with
forced leave/grace expiry, real paint/hit/installed-region checks, emerging-arc
carry and device-pixel parity at1/1.25/2x, but are compiled, not run on Linux.
Neither the preview nor compilation proves native hover, first-downward drag,
pixels/fonts, capture, click-through, mixed DPI, monitor transfer or real-login.
The development archive remains unpublished; no release/tag/push/full suite/CI
is performed. Source-generated snapshot JSON and all cache/startup/429 protections
remain intact without suppressions; the approved Subscription layout is unchanged.




Automatic quota polling runs independently of whether Settings, the flyout or
the floating surface is open, while preserving manual mode, network consent and
provider backoff.
Native-dev.7 synchronously restores the current account's last successful structured
snapshot before first Subscription render or notch Show, preserving the original
observation time as stale, even with networking off. Once networking is permitted,
one startup refresh is attempted per Surface lifetime, including manual mode with
no visible page. Source/network toggles do not reset this one-shot allowance.
Only a validated version-1 account snapshot permits bypassing the ordinary
successful five-minute floor; authentication rejection, failures and persisted
429 deadlines (including reset-credit 429 after successful usage) remain binding.
Legacy schedules without a validated snapshot retain their future NextAllowedAt:
the old format cannot distinguish the ordinary floor from an optional-endpoint
429 extension. A successful request after that deadline upgrades the format;
subsequent starts can bypass the ordinary successful floor. Cache misses/corruption,
account changes and cancellation never expose another account or commit obsolete
HTTP results. Cache uses LocalAppData/AgentSpeed/quota/<sha256account>.json with
atomic same-directory replacement, inherited Windows ACLs (0700/0600 on Unix),
and no credentials, headers or raw response. Tests use isolated synthetic auth/cache
and injected HTTP handlers, not real credentials or quota endpoints.
Native-dev.6's approved Subscription account layout is unchanged:
provider identity and plan, full-width remaining-allowance windows, absolute
reset times with localized day/hour/minute countdowns, and a separated footer
with balances/reset cards on the left and the original update time on the right.
The page's minute timer updates only reset labels while the page is active; it
does not request data, recreate controls or keep running after page closure.
Available reset cards may show the nearest valid reported expiration, parsed
independently of count; an authoritative zero suppresses the expiry label.
Unknown count/expiry remain unknown, never a quota reset or monetary balance.
Preferences use aligned switches and the existing orb-style source editor.
All sources defaults on, includes future supported readers, persists separately
and disables individual choices; legacy explicit JSON lists migrate to all off.
Codex and OpenCode Go are the implemented adapters. The diagnostics disclosure/callback and
credential-storage footer are removed, while initialization failures remain
visible. Cards retain updated time, not source/precision/next-available metadata,
and Subscription has its own icon. Internal safe native diagnostics remain for
regressions; no hidden replacement diagnostics UI is introduced.

The Windows implementation was cross-checked against
[WIsland's native window choreography](https://github.com/AsamiAkito/wisland/blob/11ebd0f0a3af2afcb5b8a4d9792f4f6f011f53f4/wisland/ui/island.py).
Only its anchored-animation-canvas principle was adopted. WIsland creates a
translucent, frameless, nonactivating Qt QWidget and paints a QPainterPath.
Its `setMask` call clips the inner content widget; it is not this implementation's
WPF-to-GDI input-region conversion. That conversion is downstream code, not a
copied WIsland display path. The 900-by-680 host, constant compact animation,
cursor polling and desktop-sampled glass are not imported. WIsland is MIT
licensed; no implementation code was copied from it.

Initial native-dev.1 verification passed 51 Codex provider tests, 307 related Presentation
tests and a subsequent 21-test geometry/envelope check. The Windows native test
assembly compiles; it has not executed on this Linux host. A throwaway probe
compared 48 orb states and 14 grip states against the pinned reference's actual
JavaScript geometry: scalar deviation was zero and sampled path deviation was
at most 0.01014 DIP. SVG previews use the actual shared C# paths, not native WPF.
The conservative model-derived local filter benchmark allocated zero steady-state
bytes: orb/grip were about 0.31/0.16 ms at 1x, 1.82/1.09 ms at 2x and
15.72/4.09 ms at 4x on this host. These are filter-only microbenchmarks, not
Windows frame times, end-to-end input latency or a native visual acceptance.

Native-dev.2 fixes the frozen-path initialization failure reported on Windows
and integrates compact account cards and direct source selection. Its Windows
test assembly and self-contained win-x64 publication build with no warnings or
errors, and 311 related Presentation tests pass. The subsequently added
`QuotaNotchWindowTests` live-window harness has been removed; it is not part of
the registered Windows filter or the Release gate. Native desktop startup,
click-through and layout acceptance are not established by Linux compilation.


Portable geometry/input/placement checks and compilation are not native Windows
interaction or pixel validation. Windows must still verify cross-process desktop
click-through outside the drawn shapes, responsive clicks/dragging, DPI changes
and the pinned visual appearance; do not mark those checks passed from a browser
or Linux-only result. No release is authorized by this development work.


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
Actions. Before remote discovery, the wrapper captures the starting committed
SHA and exports its tracked tree into an isolated temporary directory. The
starting checkout must be clean and its SHA must match `origin/downstream/patch-build`.
The wrapper verifies that the upstream tag configured in that snapshot resolves
to the commit in its `downstream/config.json` and stops if it does not. It also queries the
latest upstream release; a different tag produces a warning, while the release
continues using the configured pin. Only when choosing to upgrade, manually
migrate and commit the pin and patch queue before releasing against the new baseline.
Before any cancellation, draft deletion or tag mutation, the wrapper runs the
snapshot's `downstream/manage.py` against its committed configuration and complete
patch queue, preparing the application once in a second temporary tree. The local
preflight uses only that prepared tree, never live workspace inputs. Both temporary
trees are removed afterward, including on failure. On Linux and macOS it requires the .NET 10 SDK. It probes
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
The selected SHA remains fixed throughout the invocation. Later edits (including
untracked files), local commits, branch switches and local tag changes do not
change the snapshot, preflight inputs or final release tag target, and are not
rejected by a later checkout-cleanliness check. The wrapper does not stamp
versions, create commits, or modify the caller's patch queue, docs or local tags;
local candidate tags are not used to push the release. Make and commit all changes
intended for this release before launching it.
Remote branch advances are allowed when they still contain the selected SHA.
Before remote tag mutations and ambiguous-push reconciliation, the wrapper checks
that ancestry in isolated Git storage without changing the caller's refs or
`FETCH_HEAD`. Remote branch deletion or a history rewrite excluding the selected
SHA blocks release, matching the workflow's tag-ancestor requirement. Remote tag
conflicts still stop release and tag pushes retain explicit force-with-lease
guards; later branch work is never silently substituted for the selected SHA.
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

They cover release selection and safety, committed snapshot isolation during
workspace edits/commits/branch switches and remote advances, exclusion of the
selected commit, remote tag races, untouched local tags, transient query failures,
ambiguous write reconciliation, read-only resume, published asset immutability,
and failed-clone cleanup that preserves pre-existing user directories.

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

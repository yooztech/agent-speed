# 远程 Agent 监控与 downstream patch 交接

## 订阅历史帧按投影版本比较（未发布）

只读审查确认的问题：`linux/collector/daemon.cpp` 每秒 tick 对每个订阅调用 `sampler.history()`
（按值返回整串）再与 `Client.lastHistory` 比较。本机真实 history 投影为 251,291 B，等于每个订阅
每秒复制并比较约 245 KB；该成本随投影（天数×源×模型×模式）线性增长，且与内容是否变化无关。

修复折入原功能补丁 0001 与 0014（队列仍 16 项）：

- `sampling.cpp` 的 `Cached` 增加 `historyGeneration`，仅当**新序列化文本与缓存不同**时赋值并自增；
  成功路径与 partial/失败回退路径同规则，时区身份变化清空历史时也自增。
- 新增 `Sampler::historyGeneration(view)`；daemon 每 tick 只比较整数，变化时才取文本、记录并发送。
  先读 generation 再取文本，并发替换最多一次冗余重发，不会漏发。
- `history_timezone` 切换把该订阅的 generation 复位为 0，保证切回同一视图仍重发当前投影。

边界（未改）：`Monitor::snapshot()` 字段与语义、`Publisher::sample` 的 ActivityKit 载荷与
idle/active 边沿输入、`widgetStatistics` 输入与 `StatisticsHistory`、`requestHistoryRefresh`
语义、`protocol.cpp` 的 live incomplete→null。ActivityKit 与 WidgetKit 都不读 socket 帧，
本改动不改变其数据来源、载荷或发送节奏。

读数：复制+比较 17.5 µs/订阅/tick（251 KB），改后为一次整数比较。该绝对值很小，问题在于它随投影
线性增长。本轮**不改变发送字节数**：1 Hz snapshot 仍为 16.4 KB/客户端（剥离 0014/0015 新增字段后
4.7 KB），history 帧仍约每 60 s 一次并与 snapshot 同流，慢链路上的秒级停顿仍存在；瘦身或分流需要
两个客户端同批改动，另案处理。

定向验证：`DaemonProcessTest.*`、`CollectorSampler.*`、`CollectorPublisher.*`、`WidgetPublisher.*`、
`WidgetStatistics.*` 全部通过，含新增 `UnchangedProjectionIsNotResentEachTick`、
`ZoneSwitchRedeliversTheCurrentProjection`、`ProjectionGenerationTracksTheProjectionText`；队列从
固定 pin 重放后 tree `bb1c154aa40f51e36512dbfc71ef70a0ddab8de7` 与开发树一致。未运行 Release
门禁，未 push、未打 tag、未发布、未部署。

## Widget statistics v2（未发布）

当前队列协商 `widget_statistics_v2`；外层 NDJSON 仍为版本 1、control 版本 2。
Widget snapshot v2 不含 sources；today 与七日行提供 tokens、requests、已定价的
`costMicroUsd`、`unpricedRequests` 和完整性。已知成本只是已定价部分；未定价
请求存在时不是完整费用。模型来自同日实际 history，可能落后实时 today，因此
`modelsComplete` 可为 false；旧缓存模型 input 未知，不伪造比例拆分。前三个已知
模型之外归入保留分量未知性的 null-model 桶。ActivityKit 边沿与 responseClock 行为不变。
尚未发布、部署或证明 Worker/APNs/设备交付；本节不改变下方既有证据。

- 实现归入原功能补丁 0016，完整队列仍为 16 项；最终源码 commit `13b4d57e6e7698eaacb44d2af25659b7965b65fe`、tree `e330093b8ed0c77329c6c1ea391c56eef3ca6990`，从固定 upstream pin 重放至 `/tmp/agent-speed-widget-v2-final-replay-1110` 后 tree 相同。模型 input 使用实际归一化响应 input，合并任一未知保持未知；持久化 positional JSON 在 index 6 追加可空 input，旧六项缓存不补零，不删除旧历史。普通 history 协议同步提供可空模型 input。
- production 本地资产目录 `artifacts/widget-statistics-v2/`；ELF 为 `linux-x86_64/agent-speed-collector-linux-x86_64`，SHA-256 `c6d4756739301d1bcb056ac19d2c7fd49416340b1b17c440e0df0e65bc65269d`，精确 identity 已校验。metadata 标签 `local-unreleased-widget-statistics-v2`，不是 GitHub Release；同目录 checksum/metadata，根目录 BUILDINFO、SHA256SUMS、source.bundle 和 verification 记录来源。旧 9593 资产保留不覆写，固定 TLS 测试 variant 未启用。
- 定向验证覆盖 WidgetStatistics、WidgetPublisher、CollectorProtocol、CollectorPublisher 与两个 History.ModelInput 回归：首轮 55 项中 54 通过，1 项错误地将缺失 sources 字段视作显式 null；修正为缺失断言后单独重跑该项通过，其余 54 项未重复执行。metadata 3 项通过。production 构建成功；最终源码较已构建 commit `1b147c847b22cfe4a9ad9c3588b6d8fdf5a04718` 仅改测试断言，runtime/core/build 源码完全一致。原始首轮输出保留失败，BUILDINFO 不隐藏此过程。真实 production SSH/TLS 联验交移动 owner 执行，本侧不宣称已通过；未 push、发布或部署。
- OMP fixture 的真实 input 为 `usage.input + cacheRead + cacheWrite`，一天与模型使用相同归一化值；唯一未知计价响应产生 requests 1、unpricedRequests 1、已定价成本 0。已定价成本 0 不代表完整零费用；不能在 UI 将未知部分伪装为总费用。七日窗口含今日及前六个日历日，今天模型来自真实当前日异步历史，不伪称实时逐 token 一致。
- 移动 owner 回报 c6d4 production 的 OMP 真链已通过：隔离 OpenSSH 上七天真实 OMP 日志进入真实 snapshot/history，经生产 Dart projection 得到 today input 366、output 416、total 782，每日 requests 1、unpricedRequests 1、costMicroUsd 0，以及真实模型 input/output 和 modelsComplete；再经生产 HTTP/SQLite relay（software-seeded P256 trust）及窄 read 返回完全相同 payload，生产 Swift v2 解码与未计价费用 nil 验证通过，sampledAt 未修改。原 SSH 认证、指纹、密钥轮换、后台缓存及静默恢复路径亦由移动侧报告通过。这是移动 owner 提供的隔离软件链路证据，不代表真实设备信任证明或 Apple/APNs/iPhone 投递。
- 独立 Claude TLS smoke 首次超时已由移动 smoke owner 定位为测试谓词 source 写成 `claude`，实际 CLI sourceId 为 `claudeCode`；只精准修正谓词，未改 collector、指标断言或等待窗口。移动 owner 随后回报第二次指定 smoke 在 29.74 秒通过：bundled c6d4 production 经 OpenSSH、固定 origin trusted TLS 到 production server/SQLite，Widget input 150、output 20、requests 1、costMicroUsd 0、unpricedRequests 1、model input 150；ACK、scoped read、cancel、revoke 通过。原 ActivityKit 边沿保持 start 834 ms、idle 976 ms、ordinary 10119 ms，优先级 `[5,10,10,5]`。身份为 software-seeded，APNs 为 double，不是 Apple/真实设备投递证据。本维护侧仅记录跨仓实际结果，未再调查或测试，未修改代码或资产，未发布、部署。


## Widget 统计只发布已扫描窗口（未发布）

真机现象：iPhone 小组件在 App 长时间后台后「近7日」只剩今天一根柱，`较昨日` 与 `总量` 均为
`—`，而同一份 relay 快照的 today 真实、`sampledAt` 新鲜。移动端后台刷新目前还会先用
`historyStale: true` 发布一份 today 真实、过去六日 null 的投影；该读取端兼容层在本发布端
规则生效后删除，因此 null 不能作为长期可接受输出。

修复前三处叠加（行号为修复前 `linux/collector` 源码）：

- `widget_publisher.cpp:208` 的时隙判断只看 `l.next>now`，`:210` 把当次 `widgetStatistics`
  结果直接写入 lease 并发送。常规 30 分钟时隙没有「历史是否扫描过这一窗口」的概念，可以把
  上一份有效快照覆盖成六天 null。
- `widget_statistics.cpp:113` 的 `matching`（同一时区且 `usageDate` 等于样本日历日）是全有或
  全无门禁：不匹配时 `days[0..5]` 保持默认 null，今天仍用实时计数，正好生成该 payload。
- `widget_statistics.cpp:134` 逐日求和把「当前 snapshot 未检测/不可用」的历史来源整行丢弃，
  一个退役来源即可让整周归零为 null；`found` 也随之不成立。
- `sampling.cpp:203` 投影的 `usageDate` 取采集进程自己的 `system_clock`，与样本 `nowMs` 无统一
  时钟；跨午夜时该门禁会持续到下一次 60 秒投影，且测试无法构造该边界。

修复（全部折入原功能补丁 0016，wire 对象与字段不变）：

- `widget_statistics.{hpp,cpp}`：`widgetStatistics` 返回 `WidgetSnapshot{payload, pastCovered}`；
  `pastCovered` 仅在时区一致且 `usageDate` 等于样本日历日时为真。逐日求和只依据已记录 history
  行（`widget_statistics.cpp:135`），来源当前是否检测/启用只决定今天；缺行仅置
  `complete=false`，已知下界照常给出，无行日期仍为 null，不补零。
- `widget_publisher.cpp`：lease 增加 `needsCoverage`/`mustPublish`/`notBefore`/`probe`。已确认
  lease 遇到未覆盖投影时不写入 payload（`:230`），保留已存快照；覆盖就绪时以一次
  `mustPublish` 立即补发（`:240`），不受 30 分钟常规时隙限制，但仍遵守 Retry-After（`:161`）；
  首次确认允许一次未覆盖投影。`views()`/`needsCoverage()`（`:254`）把等待暴露给 daemon，
  拒绝重试间隔为 2 秒（`:85`）。
- `sampling.{hpp,cpp}`：`Sampler` 接受可注入时钟；`requestHistoryRefresh()`（`:284`）立即重新
  投影（2 秒节流）并请求一次文件重扫（10 秒节流）；投影 `usageDate` 改用该时钟。
- `daemon.cpp:239`：`widgets.needsCoverage()` 时请求刷新；不再用未扫描日历覆盖已存 payload。

测试（先失败后修复，均为行为断言而不是「返回 null 也正常」）：

- `WidgetPublisher.RoutineSlotKeepsStoredPayloadWhenHistoryIsNotScanned`：修复前 30 分钟时隙
  `calls` 从 1 涨到 2、再涨到 3（未扫描窗口与 `usageDate` 落后一天的窗口都覆盖了已存 payload），
  修复后保持 1，并报告 coverage 需求；覆盖完成后 2 秒内补发。
- `WidgetPublisher.PublishesTheCorrectionAsSoonAsCoverageArrives`：修复前 1 秒内没有第二次
  POST（`eventually(calls==2)` 为 false），修复后首次确认 2 秒后即补发，六个过去日 input 为真实值。
- `WidgetPublisher.RoutineCadenceRepublishesCoveredWindows`：覆盖投影后仍按 30 分钟常规时隙。
- `WidgetStatistics.UndetectedHistoricalSourceKeepsKnownLowerBound`（修复前 `"null"` vs `"4"`）与
  `HistoricalSourceWithoutSnapshotRowKeepsItsDay`（修复前 `"null"` vs `"100"`）：来源未检测、
  不可用或不在 snapshot 时历史行仍计入已知下界，整天不为 null，只是不完整。
- `CollectorSampler.WidgetHistoryStaysCoveredAcrossMidnight`：注入时钟从 23:50 推进到次日 00:10；
  同一份投影对次日样本 `pastCovered=false`，`requestHistoryRefresh()` 后 `usageDate` 跟进，六个
  过去日仍为真实值、今天为 0。A/B：把 `usageDate` 临时换回进程时钟后该用例失败
  （`projection->usageDate` 为 `2026-11-11`、样本日历为 `2026-11-10`，六天 null），恢复后通过。

队列与树：完整队列仍为 16 项；本次只有 `0016-Add-independent-widget-statistics-feed.patch`
变化（`series`、`tests.json` 与其余 15 个补丁字节未变）。开发树应用 commit
`9aa08b06b796bee2e566103727d1dd6acf6a6b5e`、整树 `446ea456b87b347872bf75b07d9900d843c407c7`、
`linux` 子树 `24aa8b7701720170f1c3a08860241b4742bf934e`；用 `downstream/manage.py prepare`
从更新后的队列重放到 `/tmp/agent-speed-widget-replay-1111`（HEAD `7d28b8de`），整树与 `linux`
子树与开发树完全一致。

验证命令与结果（Linux，GCC 12，CMake；录制内容为该次运行的实际输出）：

```sh
cmake -S linux -B build-widget -DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=/usr/src/googletest
cmake --build build-widget -j8
ctest --test-dir build-widget --output-on-failure
# 100% tests passed, 0 tests failed out of 232
build-widget/tests/agentspeed_tests \
  --gtest_filter='Widget*:CollectorSampler.*:CollectorProtocol.*:CollectorPublisher.*'
# [  PASSED  ] 61 tests.
cmake --build build-widget --target agentspeed-collector -j8   # production target, AGENTSPEED_BUILD_SSH_SMOKE 默认关闭
# [100%] Built target agentspeed-collector
```

未覆盖：真实墙钟的跨午夜与 30 分钟时隙只由注入时钟与假 transport 的单元/集成测试覆盖，未在
真机等待真实午夜；Worker 存储、APNs/WidgetKit 投递、iPhone 真机渲染未验证；未运行完整
Release 平台门禁，未打 tag、未 push、未发布、未部署，未改移动仓库。

> 下文保留历史交接记录；最新摘要隔离行为见“按 collector 摘要隔离 daemon（未发布）”，其余段落保留各次实施时的契约与证据，不代表当前仍需全局单实例。
> 当前 downstream macOS 和 Windows 原生界面通过 SSH 标准流运行 Linux 采集器；
> 本机和已启用的远程主机同时作为标准数据源，按主机和来源分组并汇总，不切换目标。
> 不可用数据不视为零，离线历史保留缺口，导出与可见历史一致；本机诊断报告
> 不包含远程数据。fork.2 提供 Windows 便携 ZIP 和每用户安装程序；各平台更新器
> 使用 fork 发布源。实际 GUI SSH 端到端仍未验证；限制及状态见
> [fork.2 release notes](releases/v1.6.1-fork.2.md)，历史 [fork.1 notes](releases/v1.6.1-fork.1.md) 保留不变。

## ActivityKit 状态边沿瞬发（未发布）

- 约一秒采样不变；`generating` 或 `tools` 任一正数为 active，两者均为有效零才为 idle，其余为 unknown；不使用 speed。首个已知状态只建立基线，unknown 不制造 idle，也不清除已知基线。
- 每个 lease 保留最新样本及最后尝试的已知状态；已知 idle↔active 可绕过常规十秒间隔一次，在 HTTP attempt 时消费，不等待 APNs accepted。持续同态仍走十秒；HTTP in-flight 继续采样，仅保留最新状态，不补发积压或折返期间的过期边沿。
- 失败期限 `failureUntil` 与普通 `next` 分离；网络失败、指数退避、429 Retry-After 与 APNs backoff 均不可被边沿绕过。控制版本仍为 2，`minPublishIntervalMs` 仍为 10000，无新增 snapshot/priority 字段；能力协商及资产 metadata 新增 `live_activity_edges_v1`，移动刷新必须拒绝缺失该能力的旧资产。
- 实现折入原功能补丁 0001、0014、0016，完整队列仍为 16 项；源码 `/tmp/agent-speed-edge-dev-1110`，commit `ec57b387502e1e2fea4ca676d12f7b25be8b7a6d`，tree `d37c6a8a9ddc459481d40d683246c12bac961f8c`。从固定 upstream pin 全量重放至 `/tmp/agent-speed-edge-replay-1110`，tree 相同。
- 本地产物在 `artifacts/activitykit-edges/`：`linux-x86_64/agent-speed-collector-linux-x86_64` 及同目录 metadata/checksum，根目录 `BUILDINFO.json`、`SHA256SUMS`、`source.bundle`。ELF SHA-256 为 `f96982107d23b887598b1543681568eb8650a22b02e4743bdd754c8c9933c133`，`--identity` 已逐字节校验。仅为未发布本地 production 配置开发产物，metadata 标签 `local-unreleased-activitykit-edges` 不是 GitHub Release；不替换旧发布资产，不含固定 TLS 测试 variant。
- 定向验证：`CollectorPublisher.*` 19 项与资产 metadata 3 项通过；Release CMake 的 `agentspeed-collector` production target 构建成功，`AGENTSPEED_BUILD_SSH_SMOKE=OFF`，测试 runtime 独立。实际本机 Linux x86_64/glibc 2.36 loader 依赖解析通过；不宣称其他发行版兼容。构建/测试原始输出在 `verification/build-and-publisher-tests.log`，其余结果在 `verification/results.json`。跨仓真实 SSH/TLS 联验由移动 owner 执行；此处不宣称 APNs/iPhone 投递或完整 Release 门禁通过。没有 push、打 tag、发布或生产部署。
- 后续真实 production Docker 隔离 SSH/TLS 联验由移动 owner 回报：f969 资产首个 idle 与普通周期成功，两次 tools/idle 边沿均小于十秒且 priority 10，稳定五秒无额外发布；随后普通 idle 在距离上次成功仅 9987 ms 到达 relay，被实际返回 `429 rate_limited`。脱敏相对时间依次为 `0 idle200p5 / 10026 idle200p5 / 11015 tools200p10 / 12028 idle200p10 / 22015 idle429`。HTTP attempt-start 与 server request-arrival 的时钟边界差异导致下一普通请求可提前，失败保底退避十秒后超出 harness 观察窗口；不是边沿失效。
- 修正：2xx 响应完成后，普通期限取 `max(next, responseClock + max(10000, intervalMs))`，不使用任意 epsilon；边沿继续绕过普通期限，失败期限与 Retry-After 不变。普通间隔现在从成功响应完成计时，包含响应耗时；不承诺慢请求或失败时二十秒内必有成功。修正源码 commit `52b34f715922371a79e9c72aa72157e3f5eff6a7`、tree `d77712aab5ec46ad4c5eac9968c70e95fd57762b`，新十六项重放 tree 一致；旧 f969 资产证据保留，不覆写。
- 修正后本地产物为 `artifacts/activitykit-edges-completion-clock/`，ELF SHA-256 `959399b1145a800872d35b30aac67dc796419c29233b489c08a471e535de5bee`；同目录结构继续提供 metadata/checksum、BUILDINFO、source bundle、完整清单与证据。production 构建和精确 identity 验证通过；`CollectorPublisher.*` 20 项通过，含 transport 推进假时钟的响应完成期限回归，并证明该期限内边沿仍可立即发送。新资产交由移动 owner 重新执行隔离 SSH/TLS 联验；此处未宣称新资产联合场景已经通过。
- 最终联合验收由移动 owner 回报：上述 `959399b1…` production ELF 已同步移动侧六处并校验，`bash server/test/collector-smoke/run.sh` 完整通过。真实 Claude 日志经 SSH 2222、固定 origin 的可信 TLS 443 到真实 relay/SQLite；`startPublishMs=869`、`idlePublishMs=970`、`ordinaryIntervalMs=10155`，优先级序列 `[5,10,10,5]`。稳定状态无按秒发布，Activity/Widget ACK、cancel、revoke 均通过。环境使用 Docker `--network none`，CA 与 hosts 仅在容器内隔离；APNs 为可观察替身，不是 Apple/iPhone 投递证据。此为跨仓 owner 提供的实际联验结果，本维护侧未重跑测试，未 push、发布或生产部署。

## 按 collector 摘要隔离 daemon（未发布）

- 同一有效 Unix UID、同一完整 ELF SHA-256 共用 daemon；同字节不同部署路径也复用。不同摘要并行运行，不替换、不终止旧 daemon，也不连接或清理旧全局 socket/lock。
- runtime 为 passwd home 下 `.agent-speed/daemons/<sha256>/collector.{sock,lock}`；历史缓存为 `.cache/agentspeed-collector/<sha256>/history.sqlite3` 及同目录锁、WAL、SHM。旧数据库不导入，不同摘要不会重置彼此缓存。源日志只读共享，扫描与内存开销按摘要分别承担。
- 每层 runtime 目录继续校验 owner、0700、非 symlink；锁为单链接 0600 常规文件，socket 为 0600，双方检查同 UID。通过仍持有的目录 FD 的 `/proc/self/fd/<fd>/collector.sock` 绑定/连接，避免完整摘要及长 home 超过 Unix socket 路径上限；精确身份握手仍保留。
- 部署路径、无参数 bridge、`--identity`、数据 version 1 与 controlVersion 2 均不变；App 不传 namespace。每个摘要仅由自己的订阅和有效 lease 维持存活，空闲 30 秒退出。Activity/Widget relay 授权不按摘要隔离；清理授权必须由持有者定位原摘要 bridge，并独立撤销 relay，不能把一个 daemon 当作另一个的本地授权管理器。
- 完整 16 项队列保留 Widget 功能；实现归入原功能补丁，不新增纠错补丁。测试树 `/tmp/agent-speed-digest-daemons`，队列整合树 `/tmp/agent-speed-digest-queue`。本地 production ELF 为前者 `build-digest/collector/agentspeed-collector`，实际 SHA-256 `f2dca601361f46f404aea039393292f6e1f7a5115a8118e245b60758e3e73f00`；不是正式 Release 资产，也未替换当前使用中的部署。
- 整合应用 commit `4adfdc22705674e2735e24492ec5fa7d7adf5185`、完整 tree `2767eabad474bf5b1f0453a8b5f93f2fce52f401`；全 16 项已从固定 pin 重放至 `/tmp/agent-speed-digest-replay`，完整 tree 一致，Linux 子树 `f5ddc56d611fdb4f86e40e592493883a4316e356` 与已构建验证的源码一致。新构建使用 CMake 的 headless、tests、SSH smoke 开关，GCC 12.2；未复制未打补丁的根源码来构建。
- 本地验证：31 项 collector/daemon/cache/sampler/integration 回归通过；强化的双摘要并发缓存持久化回归随后单独通过；现有 WidgetPublisher/WidgetStatistics 17 项通过。
- 真实隔离 SSH/TLS 验收：`shared_collector_ssh_smoke.py --collector .../agentspeed-collector-ssh-smoke --production-collector .../agentspeed-collector --port 22491`，24 场景通过，29 次 relay 请求，schema 验证错误 0。包含同摘要复用、不同摘要同时输出、独立磁盘缓存与空闲退出、legacy 端点不变、正式二进制 canonical home 路径；syscall 观察为一个 daemon 读取受控源，三个 bridge 均未读该源。旧“异摘要必须失败”的场景已删除。
- 完整 SSH JSON 证据：`/tmp/agent-speed-digest-ssh-smoke.json`。移动协调 owner 另外报告真实 dartssh2 对旧全局 daemon 与新摘要 daemon 同时连接通过；这是移动侧验收回报，不替代上述本侧隔离 SSH 证据。
- 真实 `widget_statistics_smoke.py` 同时通过 ACK 门控、SSH EOF 后授权存活、幂等重订阅、替换/精确 lease 取消、401 拒绝与空闲退出；证据 `/tmp/agent-speed-digest-widget-smoke.json`。只验证 localhost SSH/TLS，不证明 production Worker、APNs、iPhone 或原生桌面 UI；完整 Release 平台门禁未运行。没有 push、打 tag 或发布。
- 为移动端未来正式 Release 对齐 metadata：`protocol.shared_collector.capabilities` 增加已实测的 `widget_statistics_v1`，同步生成器、发布前精确校验与文档；未改 fork.8 已发布资产。打包与 ZIP 校验共 8 项测试通过，另用上述真实 production ELF 暂存三件资产，执行发布工作流相同的 descriptor 断言及 checksum 校验通过。临时本地 tag 明确为 `local-unreleased-digest-smoke`，不是发布候选。

## 共享 collector 实施记录

### 交付位置与边界

- 维护基线仍为 upstream `1.6.1` / `384ce020cc655133e95aaad5cc085f3985f0ed99`。
- 应用实现归入现有 `downstream/patches/0001-Add-SSH-remote-agent-monitoring.patch`；共享历史/时区/指标实现归入现有 `0014-Connect-remote-performance-and-history-metrics.patch`。Mac 和 Windows 调用方也已在原功能补丁中迁移。完整队列仍是原 15 项；没有新增纠错补丁或私有移动端 collector 分叉。
- 应用树中的完整协议与运维契约是 `docs/shared-collector.md`；主要实现为 `linux/collector/{daemon,publisher,sampler}.{cpp,hpp}`、共享历史核心及相应消费者测试。按 `downstream/manage.py prepare` 从队列生成这些文件，不把维护 checkout 根源码当作应用。
- 本地未发布产物：`artifacts/shared-collector/linux-x86_64/agent-speed-collector`；同目录 `SHA256SUMS`，来源和有序队列摘要在 `artifacts/shared-collector/BUILDINFO.json`。这些本地产物不是 GitHub Release 资产。
- 实际 SHA-256：`6c3c7a29befce9be22ee5993f69a7e3af71f81ca01903f7fc207dc5a63e220b2`。仅验证本机 Linux x86_64、glibc 2.36、`libcurl.so.4`、`libcrypto.so.3` 等实际解析的运行库；不宣称 Ubuntu 22.04 通用兼容，也没有伪造 ARM64 产物。
- 应用最终开发源码 commit：`87daa138635f03f3312f426ca11f44cc529e6a1d`；最终完整树：`d7e4ed213a21f051623be76340001f5ae8e4bcac`。ELF 编译后的最后差异仅为 README/NETWORK 文档；没有二进制源代码变化。
- 没有部署 Cloudflare、接触生产 SSH 主机、改 Apple 账户、签名、push、打标签或发布；维护 checkout 改动保留待用户审阅。

### 单实例、视图、存活与升级

无参数入口是 stdin/stdout bridge。有效 UID 的 passwd home 下 `.agent-speed/collector.lock` 终身持有 `flock`，私有 `collector.sock` 双向校验 `SO_PEERCRED`；运行目录 0700，稳定单链接常规锁文件和 socket 为 0600。冷启动 readiness 握手包含协议和运行 ELF 摘要；只有取得排他生命周期锁且复核端点陈旧的进程可清理端点，连接失败不能自行 unlink 或 kill。

daemon 只有一个 live Monitor、共享扫描/解析管线和机器流量基线。每个 SSH 订阅及活动 lease 有自己的时区/视图；切换 SSH 时区不改变其他订阅或活动。完成事件只 drain 一次后扇出。有界慢读队列不能拖住采集/发布；历史、完成事件溢出以可见断流/缺口处理，不伪装成完整。持久 canonical 指标及每条 Hermes source-zone provenance 保留独立视图重建能力，不缓存或上传对话内容；缺失输入继续 partial。

单条 SSH EOF 只移除该订阅。有效 lease 可在最后一个 SSH 真正退出后继续采集/发布；无订阅且无有效 lease 30 秒后退出。`setsid` 不绕过宿主 systemd/cgroup logout 策略；本地隔离 OpenSSH 的存活不证明所有宿主支持，没有安装 root 服务或启用 linger。

新部署路径为 `~/.cache/agent-speed/collector-v2-<ELF-SHA256>`，无参数 `exec`；不覆盖旧 `collector` 路径。先计算实际 ELF SHA，再逐字节比较 `--identity` stdout：

```text
shared-collector-v2 6c3c7a29befce9be22ee5993f69a7e3af71f81ca01903f7fc207dc5a63e220b2
```

末尾恰好一个换行，exit 0；它不是 JSON。identity 在运行时读取自身 ELF 计算摘要，摘要不嵌入 ELF，不存在自引用。运行 daemon 摘要与磁盘资产不同则明确 version-conflict/非零退出，不杀旧实例、不删 socket、不降级；移除旧订阅/lease 并等待空闲退出后重连。已发布旧客户端不会被这次源码修改远程升级；同 Unix UID 运行旧二进制仍可能产生旧进程，所有参与客户端必须迁移，不能把 UID 当作隔离同账户程序的安全边界。

### 移动 owner 精确联动要求

1. 数据帧继续 `version: 1`；仅请求后返回能力。新能力为 `live_activity_v2`、`shared_collector_v1`，`controlVersion: 2`、`subscribeTimeoutMs: 75000`、`minPublishIntervalMs: 10000` 和精确 relay origin。
2. subscribe 在原字段外必须传 `controlVersion: 2`、注册返回的 `hostId`/`hostName`、固定活动视图的 `timezone`。这些值不从 opaque lease 解码，也不由主机猜测。SSH `history_timezone` 不改变活动时区。
3. 正确认仅在第一份真实新样本被 relay 成功接收后返回。collector 最多等 75 秒，移动 subscribe 响应等待改为 90 秒；控制帧写入仍最多 5 秒，capability/unsubscribe 可保留短等待。轮换不绕过 Worker 十秒窗口，不重放旧采样，不提前确认。
4. ACK 带 `controlVersion: 2`、`accepted`，负确认使用安全 `error` 类别；只匹配当前 request/activity/lease/generation，超时/迟到响应不得将新授权改成旧 token。相同连接 requestId/相同载荷可幂等重试；不同载荷冲突，同活动 replacement fence 旧 publisher。精确重复/负确认规则以应用协议文档为准。
5. 只接受精确 `https://agent-speed.yooztech.com`，可有一个尾随 `/`，二者规范化到固定 `/v1/publish`；其他路径、query、别名、非默认端口和任意 origin 均拒绝。该 production ELF 不接受环境或参数注入本地 relay/CA。
6. 用户前台创建已有活动并显式授权；手机取得 lease 后才经已校验主机指纹的 SSH 发出。后台/断开 SSH 不撤销有效 lease。停止活动还需独立 relay 撤销；活动级 DELETE 不得与新 lease 轮换竞态。
7. 移动 owner 单独负责移动代码、bundled 单个正式 ELF、manifest/SHA、安全内容寻址上传、identity 校验和移动测试；不复制上游源码树、不使用只供本地 TLS 测试的 variant。本地产物获准用于开发验收，不冒充已发布 App 或已签名安装包。

### 发布端约束与实际本地验证

publisher 是采集线程外的有界工作线程，只发送最新真实样本的最小 snapshot；`sampledAt` 使用采集时刻，未知值为 null。TLS 校验证书/主机名，禁止重定向、环境代理和 netrc；连接/DNS 3 秒、总请求 6 秒、响应 4096 字节上限。401/403/410 停止 lease；429 尊重退避；400/502 和连接失败不重发同一采样，也不补发积压。目标主机不持有 Apple provider 私钥/JWT 或统一管理密码。

本轮执行了以下隔离验证，完整输出保存在本地 `artifacts/shared-collector/verification/`：

- `collector-focused.log`：49 项 collector/daemon/publisher/shared-history/sampler 风险回归通过；包括共享扫描计数、跨日/独立时区、partial/未知、持久化与 source-zone provenance、首次确认、轮换/超时/迟到、HTTP 错误与退避等实际消费者行为。
- `ssh-smoke-final.json`：真实 OpenSSH + collector + 固定本地 TLS relay，25 个场景全部通过，真实 relay 请求 29 次、schema/identity/采样验证错误 0。不是 mocked transport，也不访问生产 relay。
- 真实 syscall 取证：只有一个 daemon 对受控源文件发生 `openat=1`、`pread64=1`，三个 SSH bridge 均为 0；syscall 本身不冒充 parser 调用计数，计数不变量另有 C++ 行为回归。
- 真实 SSH EOF 后 lease 继续发布、独立 timezone、completion 扇出、慢读者隔离、错误/残留 socket、并发安全上传和硬链接/权限拒绝、运行摘要冲突不影响活跃订阅、400/401/403/410/429/502、超时/断连恢复、旧 lease fence、到期/取消后退出均有记录。production ELF 的 canonical runtime 和 30 秒空闲退出场景实际耗时 31.419 秒，通过。
- native 上传 shell 来自编译后的 Windows `RemoteSshWorker`，不是手抄的替代命令；实际命令 SHA-256 为 `60b69281e45d50e25e3a1d16c02d6864cba7fe592abc5a0aa4a252c0f7cdf9e7`。
- 发布 HTTPS 实现通过专门测试构建固定本地 endpoint/CA 接入隔离 relay；该 variant 不分发。正式 production ELF 另作真实 SSH/生命周期验证；不能把本地 variant 的请求说成 production 向 Cloudflare 发送成功。
- 恢复后重新执行 Windows 可移植 Core 的 `FullyQualifiedName~Remote`：39/39 通过；Windows 应用在 Linux `dotnet build ... -p:EnableWindowsTargeting=true` 交叉编译为 0 警告、0 错误。这不是原生 Windows GUI 验收。
- 维护工具行为测试：`test-manage.py` 3 项、`test-release.py` 27 项、`test-publish-release.py` 8 项、`test-package-collector.py` 3 项、`test-verify-collector-zip.py` 5 项，全部通过。Release/publish 测试使用隔离 fixture/fake 服务；没有运行真实发布命令，也没有推送真实标签。
- 最终原 15 项队列已从 pin 全部重放到新目录 `/tmp/agent-speed-shared-final`，树哈希与开发树精确相等（`d7e4ed213a21f051623be76340001f5ae8e4bcac`）；全新树编译后 focused 51/51 通过，注册 Linux 全部 CTest 196/196 通过、0 失败，耗时 35.36 秒；其余注册的 `python3 tests/test_release_version.py` 为 3/3 通过。完整原始输出分别保存在 `final-queue-replay-and-focused.log`、`final-linux-ctest.log`。
- 最终 clean replay 重新编译的 production ELF 与交付文件逐字节 SHA-256 相同；其 `--identity` 也精确返回上述行。不是只检查两个同名文件或沿用旧 checksum。

可在新生成的 prepared tree 重跑针对性检查（不是完整 Release 管线）：

```sh
python3 downstream/manage.py prepare /tmp/agent-speed-shared-final
cmake -S /tmp/agent-speed-shared-final/linux -B /tmp/agent-speed-shared-final/build-remote \
  -DCMAKE_BUILD_TYPE=Release -DAGENTSPEED_BUILD_APP=OFF \
  -DFETCHCONTENT_SOURCE_DIR_GOOGLETEST=/usr/src/googletest
cmake --build /tmp/agent-speed-shared-final/build-remote \
  --target agentspeed_tests agentspeed-collector -j3
/tmp/agent-speed-shared-final/build-remote/tests/agentspeed_tests \
  --gtest_filter='DaemonProcessTest.*:CollectorPublisher.*:SharedHistory.*:CollectorSampler.*:CollectorProtocol.*:CollectorIntegration.*:Engine.TodayMeasuredTotalsUseFinalValidWidenedIntervals:Traffic.AttributesEqualStartProcessesInParentOrder'
```

prepared tree 的 `docs/shared-collector.md` 给出真实 SSH/TLS 冒烟所需 CMake target 和命令。隔离 sshd 需要本机 sudo/root；trace 需要宿主允许 ptrace，不能把 trace 禁用后的未取证状态当成单采集证明。relay 测试断网是关闭真实已建立 TLS 连接，不是关闭机器网络接口；至少 60 秒 APNs 退避由确定性 C++ 回归验证，不借真实时钟等待冒烟代替。

**仍未验证**：Cloudflare 生产部署、App Attest 真机授权、APNs provider 签名与送达、已签名 iPhone 灵动岛更新、macOS 原生构建/UI、Windows 原生 GUI，以及其他架构/发行版 runtime。后续需要相应授权、设备和平台；没有因此省略所有可达本地实现，也不声称 Apple 链路已通过。

## 本次交接范围

用户要求把已经讨论的改造思路交到本项目 workspace，并明确要求：**仿照 OmniRoute，以可重放的 patch 队列承载 fork 功能，方便持续跟随上游更新。**

本次仅交接需求、设计方向和维护约束；尚未实现远程功能、创建应用 patch、安装软件、构建或发布。接手 Agent 先阅读并形成实施计划，等待用户在本 workspace 下达开发指令，不要把交接自动扩大为完整实现。

## 项目与工作区

- Fork：https://github.com/yooztech/agent-speed
- 上游：https://github.com/zoefix/agent-speed
- 根目录：`/home/projects/agent-speed`
- 分支：`main`
- Paseo host：`Code`，server ID `srv_o1MD0un7HdBG`
- Paseo project ID：`prj_92a5d69d995ffce2`
- 主工作区：`main`，workspace ID `wks_7e3197c6e4ce609b`
- Workspace 直接使用上述根目录，不是另一个 worktree。
- 交接时 fork HEAD：`384ce020cc655133e95aaad5cc085f3985f0ed99`。这是已观察到的 checkout commit；正式建立 baseline 时仍需核实其与上游的关系，并在配置中固定完整 SHA，不能只跟随浮动 main。

## 用户目标与已排除方向

用户在 Mac mini 本地运行 Agent Speed，希望它可以连接远程服务器，观察该服务器上运行的 Agent。第一个实际场景是 **Paseo Linux 服务器上的 omp（oh-my-pi）**。

OmniRoute 是 Docker 部署，用户反馈其统计界面本身很慢。最终选择绕过 OmniRoute 的统计链路，直接读取 omp 生成的本地记录。

不要退回以下方向：

- 不把 Agent Speed 桌面 GUI 安装进 OmniRoute 容器。
- 不依赖 OmniRoute 的调用日志、管理 API 或统计页面。
- 不把需求缩成只看 Mac 本机 Agent。
- 不伪造 Codex/omp 会话记录来迁就现有界面。
- 不假设 Agent Speed 原版已经具备远程读取能力；目前确认的是本地采集核心和可选的对外统计上报，不是现成的远程数据源。
- 不假设 Paseo 管理 API 已提供与 Agent Speed 等价的 token、耗时、历史指标。

## 推荐架构（待实现前细化）

```text
Paseo Linux 服务器                         Mac mini
omp JSONL 日志 -> 无界面只读采集器 -> 安全连接 -> Agent Speed 远程数据源 -> 原生界面
```

推荐复用 Agent Speed 的 Linux `agentspeed_core` 与现有 omp 解析、去重和测速规则；增加无界面运行入口与统计传输层，而不是再写第二套统计算法。Mac 版增加远程主机配置和远程数据接入，继续保留本地数据源。

优先考虑 SSH 隧道：采集器仅监听服务器回环地址，不新增公网裸露端口，Mac 主动连接。连接认证、SSH 主机密钥校验、凭据生命周期需要明确设计；不得关闭主机密钥校验或把私钥、口令写入仓库/日志。若实现需要保存敏感凭据，使用 macOS 钥匙串，不保存明文密码。

服务器只向 Mac 发送必需的指标。不要传原始会话 JSONL、提示词、对话、工具参数/输出、绝对工作路径；允许用户明确选择需要展示的主机/Agent 标签。优先本地增量读取再传小型统计结果，不用 SSHFS/SFTP 挂载整个历史目录让 GUI 反复扫描。

这是设计方向而非已完成协议。实现前需确定协议版本、快照与完成事件的关系、重连恢复和历史归属，不能把已有可选上报协议未经评估直接当远程采集协议。

## 需要保留的行为与边界

- 首个端到端目标：Linux 采集器 + Mac mini 客户端 + 远程 omp。传输模型不应硬编码为某一台 Paseo 服务器；不要求本次扩展所有平台的远程 UI。
- 展示远程 Agent 的生成/工具执行/空闲状态，以及日志实际提供的模型、token、缓存、完成耗时、速度和历史指标；字段无法测得时明确未知。
- 复用现有统计语义，不能把未知值或断线解释为正常空闲/零用量。
- omp 的完整响应通常完成后落盘，进行中的速度可能基于近期数据估算，必须保留估算与最终实测的区别。远程传输不会凭空提供逐 token 实测吞吐量。
- 默认端到端 tok/s 包含首字等待；不要与扣除 TTFT 的生成速度混为一谈，不从不存在的日志字段推导 TTFT。
- 远程标识至少包含稳定主机标识，避免不同机器路径碰撞；复用现有父子 Agent 去重规则，防止本地+远程、重连重放和父子会话重复计费。
- 断线显示离线/数据过期，重连不得重复累计；采集器或 GUI 重启后恢复策略要有明确语义。
- 不宣称能看到 OmniRoute 内部账号冷却、路由重试等客户端日志未记录的信息。
- 远程监控必须显式启用，默认不新增后台对外连接；更新网络/隐私说明，不能沿用“所有监控完全本地”的不准确承诺。
- 采集 CPU、内存、启动扫描、常驻增量读负载需实测，不能预先承诺零开销或一定很轻。

## 已有证据与尚未验证内容

已观察：

- 本服务器存在 `~/.omp/agent/sessions`，调查时约有 7,119 个 JSONL 文件。
- 抽样 omp 会话中 provider 为 `omniroute`，assistant 记录包含 `usage`、`model`、`provider`、`api`、`timestamp`、`duration`、`completedAt` 等解析所需字段。
- 曾对实际记录进行只读计算：707 输出 token / 23.51 秒约 30.07 tok/s，571 / 20.13 秒约 28.37 tok/s，626 / 19.66 秒约 31.85 tok/s。这只是日志计算 smoke，不是完整 Agent Speed 运行证明。
- Linux 核心已独立为库，`Monitor` 提供 `start`、`poll`、`snapshot`、`takeCompletions` 等接口。

尚未验证：无界面采集器、远程协议、Mac UI 接入、构建、资源占用和 Mac mini 实机显示均未实现或验证。不得在交付时声称这些已经可用。

## 必须采用的 fork 维护方式

参考仓库：`/home/projects/OmniRoute/downstream/`。**借鉴机制，不照搬该项目的 Node/npm、Docker、镜像发布与覆盖率配置。** Agent Speed 是 macOS/Swift、Linux/C++、Windows/.NET 项目，要采用实际受影响平台的工具链。

### 基线、队列与职责分离

建议在本 fork 建立（以下均为待实现约定，交接时并不存在对应工具）：

- `downstream/config.json`：上游 URL、固定完整 commit SHA、可选版本标签。
- `downstream/patches/series`：编号 patch 的唯一应用顺序。
- `downstream/patches/0001-<objective>.patch` 等：`git format-patch` 生成、可由 `git am` 重放的 mail patches。
- `downstream/patches/tests.json`：每个队列 patch 对应的 regression / related 测试命令登记。
- `downstream/README.md` 和最小 prepare/verify 工具：准备指定基线、按 series 应用、验证和导出流程。

所有应用功能变更必须能由“上游固定基线 + 有序 patch 队列”重建。不能只把改动混在 fork 的直接源码修改/提交里而没有可重放 patch。应用源码、测试、直接相关产品文档随对应 patch 一起导出；下游维护工具、配置和交接说明留在 fork 维护层，不塞入应用 patch。

在独立临时 checkout/worktree 中开发和导出应用 patch，不对 main 执行破坏性 reset/clean。主 workspace 作为维护入口。构建、打包和验证针对应用队列后生成的源码树，不能误用未打 patch 的 fork 原始树。

### Patch 粒度与更新流程

- 每个 patch 一个明确目标，只含必要实现、受影响调用方、行为回归测试与直接相关文档。纯工具或文档变更不伪造行为测试。
- 按真实依赖拆分，不能为了数量凑 patch，也不能把与目标无关的上游修复捆进去。
- 导出方式：在固定基线上的开发 checkout 提交目标改动，再以 `git format-patch <baseline>..HEAD --output-directory <fork>/downstream/patches` 生成；文件名必须与 series 和测试注册一致。
- 准备工具必须在新的输出目录检出固定上游基线，严格按 series 执行 `git am`；遇冲突立即失败，不能跳过、忽略或自动删掉 patch。
- 验证整条队列按序干净应用，并执行队列登记的全部 regression / related 命令。
- 跟随上游时先用候选完整 SHA 在临时目录试应用、重放、解决冲突并重新导出；验证通过后再更新正式 pin。不要把直接 merge 成功当作 patch 可维护性证明。
- 上游已吸收的补丁要在确认等价行为后从 series、patch 文件和测试注册中同步移除，记录对应上游 commit/PR。
- 不在本次交接中提交或推送；未来也不要未经用户要求发布版本、推送 main、改写历史或启用自动更新上游。

### 验证与验收

- 行为 patch 必须包含真实回归测试，并登记直接相关模块测试。测试应覆盖消费者可见行为，不只比对源码或 mock 转发。
- 重点边界：跨主机身份冲突、重复/重放数据、断线与恢复、估算/实测区分、损坏/不完整 JSONL 追加、安全绑定与协议鉴权，以及本地监控不回归。按实际设计选取必要案例，不无关扩展。
- Linux：运行真实采集器读取受控日志，观察日志追加如何改变输出，确认只发送允许字段。
- Mac：必须在 macOS 构建并通过实际界面连接远程端验证；Linux 上的测试或静态检查不能替代 Mac UI smoke。若当前没有 macOS 执行环境，记录精确缺失条件，不虚报通过。
- 端到端：真实 omp 请求产生记录 -> 服务器采集 -> Mac 显示；再验证断线、重连和不重复累计。
- 性能：区分首次历史扫描和常驻增量采集，测量代表性会话量的资源开销。
- 保持本地 Agent Speed 行为；更新 `spec/NETWORK.md`、必要的 metrics/design 规格与安装使用说明。
- 使用 patch 范围验证，未经授权不照搬 OmniRoute 全项目 coverage 或 Docker release gate。若正式发布/PR另有本项目要求，应按目标仓库规则执行。

## 接手入口

Agent Speed：

- `linux/core/CMakeLists.txt`：独立 `agentspeed_core` 静态库。
- `linux/core/include/agentspeed/monitor.hpp`：采集器轮询和快照接口。
- `linux/core/src/omp_parser.cpp`：omp usage、时间与状态解析。
- `macos/Package.swift`：core、app、probe 与测试 target。
- `macos/Sources/AgentSpeedCore/LiveMonitor.swift`：本地 MonitorCore 到 SpeedStore 的现有发布通路。
- `macos/Sources/AgentSpeedCore/Monitor/TranscriptScan.swift`：现有扫描入口。
- `macos/Sources/AgentSpeedCore/IO/TranscriptDiscovery.swift`：本地会话发现。
- `macos/Tests/AgentSpeedCoreTests/LiveMonitorTests.swift`：已有监控测试入口。
- `spec/METRICS.md`、`spec/DESIGN.md`、`spec/NETWORK.md`：统计、设计和网络隐私契约。

OmniRoute 维护方式参考（不是本项目已有命令）：

- `/home/projects/OmniRoute/downstream/README.md`
- `/home/projects/OmniRoute/downstream/config.json`
- `/home/projects/OmniRoute/downstream/patches/series`
- `/home/projects/OmniRoute/downstream/patches/tests.json`
- `/home/projects/OmniRoute/downstream/prepare.mjs`

## 接手 Agent 的下一步

1. 阅读本交接及上述相关入口，复核源码实际接口，不把设计建议当已实现事实。
2. 给出可执行的 patch 分解、最小维护工具方案、协议与安全边界、平台验证路径；保持 upstream diff 小、可删除、可重放。
3. 本轮仅确认接收并提交计划；等待用户在本 workspace 继续指示，不自动开始功能开发、改动源码或发布。

## Widget 统计 feed（未发布的独立功能）

维护队列新增 `0016-Add-independent-widget-statistics-feed.patch`；旧 0001–0015 字节保持不变。
应用代码仍只来自 upstream pin `384ce020cc655133e95aaad5cc085f3985f0ed99` 加完整有序队列；
没有修改维护 checkout 根应用源码，也没有改版本、push、标签、Release、生产 Worker 或 Apple 配置。
移动/Worker/Native 由其 owner 独立实现；本节只证明维护端行为，不代替跨端或真机验收。

### 接口和数据边界

- 保留现有 `version:1`、`controlVersion:2`、LiveActivity v2/十秒行为，额外协商
  `widget_statistics_v1`、`widgetMinPublishIntervalMs:1800000`、`widgetMaxLeaseSeconds:2592000`。
- `widget_subscribe` 必填：`version`、`type`、`controlVersion`、`requestId`、`subscriptionId`、
  opaque publisher `lease`、整数 Unix 毫秒 `expiresAt`、注册的 `hostId`/`hostName`、IANA
  `timezone`、固定 `intervalMs:1800000`。不接收 URL、readToken 或 registrationToken。
- `widget_subscribe_ack` 完整回显 `version:1`、`type:widget_subscribe_ack`、`controlVersion:2`、
  `requestId`、`subscriptionId`、`hostId`、`hostName`、`timezone`、`expiresAt`，以及 Boolean
  `accepted`；负确认含安全 `error`。仅真实统计首次 POST 得 Worker HTTP200 才正确认，
  不把存储成功说成 APNs/设备送达；确认窗口最多 75 秒。
- `widget_unsubscribe` 必填外层版本、controlVersion、requestId、subscriptionId 和当前 publisher
  lease；ACK 回显 request/subscription/version/controlVersion 和 accepted。错误旧 lease 不影响替换；
  缺席订阅也记录有界取消 tombstone，阻止另一条 SSH 上迟到的相同 lease subscribe 复活。
- 新 lease/binding 首发可立即存储；同 lease 幂等重订阅不重置 30 分钟周期。确认后 SSH EOF
  不撤销；Widget 与 ActivityKit 独立，到期不续权，授权最多 30 日。Worker 独立保持跨替换 push 预算。
- 只向固定 `https://agent-speed.yooztech.com/v1/widget-publish` 发 `{snapshot:统计对象}`；TLS
  校验证书/主机名、不跟随跳转、不用环境代理或 netrc，连接/DNS 三秒，总请求十五秒，响应有界。
  除首发之外至少三十分钟一轮，429 尊重更晚 Retry-After；永久拒绝只清理匹配代次，
  5xx/断网不排队重放或密集重试。已排队样本在真正发送前再次检查新鲜度/严格递增。

统计投影来自现有唯一采集/历史管线及 immutable typed history，不从 ActivityKit 最小 payload 拼造，
也不加新扫描器。结构为 version/hostId/hostName/sampledAt/timezone/usageDate/today/days/sources/historyComplete。
七天是含今天的七个日历日，缺日/缺参与源覆盖为 null，不补零；今天 day 行三字段完全等于 today，
historyComplete 等于七个最终 day.complete 全真。来源保留不可用状态；没有使用证据的未检测 harness
不伪装成零贡献，也不毒化真实合计。已有 cached/reasoning 计数不再二次加入 input/output。
统计不能诚实表示、整数溢出、过多来源或超过 64 KiB 时拒绝，不静默截断。

### 已实际观察的隔离进程路径

`artifacts/widget-statistics/verification/widget-ssh-tls-smoke.json` 保留真实 OpenSSH + daemon +
固定 loopback TLS 测试 transport 的结果。七份实际 OMP JSONL 日期记录先通过 SSH 历史管线读取，
再验证 Widget 发布；不是注入假的统计对象或 mocked HTTP transport。观测到七日 input 为
360–366、output 为 410–416，今天 366/416，17 个规范来源，historyComplete=true。
还验证：HTTP200 前无 ACK、全部 SSH 退出后已确认授权保持 daemon、相同 lease 重订阅不重复 POST、
替换首发和旧 lease 取消隔离、401 不假启用、正确取消后空闲退出。

三十分钟完整间隔、时钟跳变、过期和旧响应竞态由确定性 C++ 时钟回归覆盖；短时 SSH 冒烟不冒充
实际等待三十分钟。固定 loopback variant 不分发，生产 ELF 没有 URL/CA 运行时覆盖能力。
运行命令需要预先创建证据目录及本地 sudo，脚本只创建隔离用户/sshd/TLS，自动清理，不访问生产主机：

```sh
mkdir -p artifacts/widget-statistics/verification
sudo -n python3 <prepared-tree>/linux/tests/widget_statistics_smoke.py \
  --collector <prepared-tree>/build-widget/collector/agentspeed-collector-ssh-smoke \
  --evidence /home/projects/agent-speed/artifacts/widget-statistics/verification/widget-ssh-tls-smoke.json
```

可复核来源保存在 `artifacts/widget-statistics/source.bundle`，含真实 Widget 功能开发 commit，
以公开 pin 为 prerequisite，而不是仅引用易失的 `/tmp` 文件。最终 ELF、全队列摘要、构建命令、
工具链与实际验证结论已写入同目录 `BUILDINFO.json` 并交付移动 owner。它们是本地未发布开发资产，
不能编造 GitHub Release URL，也不能声称已签名 iPhone/WidgetKit/APNs 或 Android 原生验收通过。

最终固定开发 commit：`c233521e0be608f00f8742761463252f3328a60b`；完整队列独立重放树为
`7e95e5825ebd04c3b481b0cb8a30889a4ad34f4f`，与开发树相同。
新增 0016 SHA-256：`f23653759341a6001b11a429cff0c99caef5230a8599b3d8ff4c8eee8bd07cab`。
最终 focused 回归 47/47 通过，含 Widget 及已有相关 daemon/ActivityKit/采样/历史行为；维护 manage 测试
3/3 通过。完整 Release/其他平台管线没有重复执行，也没有以旧测试数字替代本轮结果。

实际生产 ELF 在 `artifacts/widget-statistics/linux-x86_64/agent-speed-collector`，SHA-256：
`e71c0688f4d3336f531596c7d92e6cd1e52ecb37f1ce4dbbcaa8c219998a928f`。
其 `--identity` 精确返回 `shared-collector-v2 ` 加该摘要及单个换行，实际 exit0；本机动态 loader 检查通过。
只验证 Linux x86_64/glibc2.36/libcurl.so.4/libcrypto.so.3 及实际记录的其他依赖，不承诺 Ubuntu22.04/ARM64。
正式生产 ELF 没有向本地/生产 relay 发送这轮测试请求；真实 TLS 请求来自固定 loopback test variant。
最终 test variant 的 SHA-256 与实际 SSH 冒烟运行的字节完全一致：
`a76b01dd40163be10d19061e10944473582cce8d69221c29ca6227bd84d7e384`。不得将它纳入移动 assets。
最终跨侧 production SSH、Worker、App Attest、WidgetKit 与 Apple 真机验收由移动协调 owner 执行。

### fork.12：已知下界语义（已发布）

移动侧把小组件口径改为“缺参来源的日期保留已知 input/output 下界、`complete=false`”，relay 快照由
collector 生成，因此在原 0016 内同步：日聚合改为 `found` 即写入已知部分和；今日 input/output
始终取快照、`complete` 仅由 `partialHistory` 决定；请求/费用仍只在完整覆盖且非 partial 时发射。
stale 历史、时区不匹配或无任何行的日期仍为 unknown。没有新增字段、协议版本或能力变化。

更新后 0016 SHA-256：`6b2c0e40a3950dd41b5d6c495add1832f81045cb773cb208ef3ac9ec312d4ea8`。
维护 commit `7625e1da79ecfcb049b1ce70e304016da2a708ad`；完整队列重放树
`f9ae7094d4c55e7a2f920c8cc5a8ac44bc17a595`。本地 focused 回归 53/53 通过（含 12 个
`WidgetStatistics.*`）；Release preflight 的 Linux CTest 226/226 通过，Windows 与 macOS job 成功。

已发布 `v1.6.1-fork.12`（run 42951904524）。正式 collector asset 实际下载并重新校验：
SHA-256 `ebfcc03ba92a5f5996ba9b6f144153ae9847317f855ed5aa63671d47b7db862b`，
`--identity` 返回 `shared-collector-v2 ebfcc03b...862b` 且 exit0；metadata 的
`release_tag`、`maintenance_commit`、`upstream_commit` 与上列值一致，能力含
`widget_statistics_v2`。该资产只声明 Linux x86_64 与记录到的 ELF 依赖，不代表 Apple/Android
真机或生产 Worker 验收。

## Windows fork.9 SSH 管道提前结束：维护诊断

用户在已安装的 `v1.6.1-fork.9` Windows 客户端报告远程主机 Code 离线，界面重复显示“管道已结束”。
这是已报告的真实故障；没有重新运行生产 Windows 应用去“确认”用户现象。已发布的 fork.9 标签与资产不可变。

已检查 GitHub fork.9 独立 collector、Windows x64 ZIP 内的 collector 和此工作站 `dev` 用户
`~/.cache/agent-speed/collector-v2-7ace53bcc7aae824287e56949a9ed9b59fea882ebc691b5d892d9239deb29666`：
三个 SHA-256 均为 `7ace53bcc7aae824287e56949a9ed9b59fea882ebc691b5d892d9239deb29666`。
在此主机，`--identity` 返回同摘要，运行库解析正常；该用户 home/cache 权限、collector 700 单链接、
按 digest 区分的 runtime 目录 700 与锁文件 600 均符合当前规则，磁盘尚有 27 GiB 可用。
这些本机事实不能证明 Windows 的 SSH alias、实际 Unix UID、远端执行时的 stderr 或 SSH 网络状态。
**不要清空**采集器资产、历史缓存、锁目录或 App 设置：它们不是已确认原因；清空会破坏证据或影响其他连接。

Windows `RemoteSshWorker` 在上传 `WriteAsync`/关闭输入或最早 probe/collector 读管道时若抛
`IOException`，原实现只显示本机 Windows 的管道错误，跳过远端子进程退出码和本来已界限为
4 KiB 的 SSH stderr。`RemoteConnectionManager.Ended` 再每十秒重连、拼接相同错误，因此界面重复。
最初只确认了**错误归因丢失与重复展示**；后续已定位 Windows 上传脚本 CRLF 缺陷，见本节末。
诊断改动保留失败路径有界的子进程退出信息并显示本次失败，不绕开 SHA/identity/主机密钥验证，
不删/杀现有 daemon，不把旧 collector 当成后备。新版本须独立验证并获发布授权后才可替代已发布 fork.9。

维护实现已回收到原有 `downstream/patches/0009-Integrate-Windows-SSH-sources-and-fork-updates.patch`，
没有增加修补编号；原 0010–0016 按序重放。该补丁 SHA-256：
`249adc9b4853c8078efa99c959391d9f23bb7c47843f68250fbbbb5568264797`（包含下述 CRLF 根因修复）。
Windows 回归新增独立编译的 `ssh.exe` 测试子进程及隔离的 8 MiB 临时 collector，
覆盖早退时的上传失败、退出码及 SSH stderr，以及 probe 的主机密钥错误；
沿用 0009 已注册的 Windows.Tests 整套执行命令。没有修改共享打包的 collector。

本轮执行：`python3 downstream/manage.py prepare /tmp/agent-speed-fork9-final` 完整重放 16 个补丁；
`dotnet build /tmp/agent-speed-fork9-final/windows/tests/AgentSpeed.Windows.Tests/AgentSpeed.Windows.Tests.csproj --configuration Release -p:EnableWindowsTargeting=true`
在 Linux 交叉编译成功，测试子进程产物为 x86-64 Windows PE；重放后的 Git tree
`0eb174992bf7ea91ed1bb717574a7d92a3556cb0` 与最终导出开发树一致。
隔离 Linux 实际进程冒烟以 8 MiB 输入喂给主动退出 37 的 SSH 替身，观测
`Collector upload failed (exit code 37): Unsafe collector directory`；
它验证了客户端的错误传播，不等于在 Windows 上运行新回归或证明生产 SSH 最初为何退出。

### 已确认：Windows 发布程序把 CRLF 带入 Linux 上传脚本

直接检查保存的已发布 fork.9 Windows x64 ZIP 内 `AgentSpeed.exe`：UTF-16 字符串
`set -eu\r\n` 出现在字节偏移 `29870129`，`set -eu\n` 不存在。仓库 `.gitattributes`
只固定 fixtures，不限制 C# 源码换行；C# 多行 raw string 保留源码换行。
Windows 编译产物因此把 CRLF 上传脚本交给 Linux shell；Mac 的 LF 脚本不受此问题影响。
这是客户端部署脚本失败，不是 SSH 登录失败，也不是 collector 摘要错误。

真实 Bash 执行同一上传脚本、使用实际发布 collector 和隔离的临时 HOME：
原 Windows CRLF 版本 exit 2，出现 `set: -\r: invalid option`、`umask: 077\r: octal number out of range`
和 `syntax error: unexpected end of file`，没有安装资产；LF 版本 exit 0，资产落盘且摘要匹配。
上传脚本提前退出会关闭 SSH stdin，旧 Windows 客户端随后写入二进制时只报“管道已结束”。

实际修复：`RemoteSshWorker.UploadCommand` 在构建完脚本后执行 `.Replace("\r\n", "\n")`。
修复仍归入 0009；新增 `windows/scripts/test-remote-ssh-script.py` 并注册到 0009 Linux 回归。
该测试把实际 worker 源码转成 CRLF 后编译，调用实际生成命令，再交给真实 `bash -n`：
未修复版本 exit 2、测试失败；修复版本通过。它不是源码字符串匹配测试。
完整 16 补丁重放到 `/tmp/agent-speed-fork9-crlf-verified`、上述 CRLF 回归、Windows.Tests
Release 交叉编译均通过。未运行 Windows 原生 UI，未发布新安装包；已安装 fork.9 不会自动改变。

未经单独授权不推送、不打标签、不运行 Release，也不声称 fork.9 已修复。



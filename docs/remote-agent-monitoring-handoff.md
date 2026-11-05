# 远程 Agent 监控与 downstream patch 交接

> 历史交接记录：下文描述的是实施前的需求与建议，不代表当前实现状态。
> 当前 downstream macOS 和 Windows 原生界面通过 SSH 标准流运行 Linux 采集器；
> 本机和已启用的远程主机同时作为标准数据源，按主机和来源分组并汇总，不切换目标。
> 不可用数据不视为零，离线历史保留缺口，导出与可见历史一致；本机诊断报告
> 不包含远程数据。fork.2 提供 Windows 便携 ZIP 和每用户安装程序；各平台更新器
> 使用 fork 发布源。实际 GUI SSH 端到端仍未验证；限制及状态见
> [fork.2 release notes](releases/v1.6.1-fork.2.md)，历史 [fork.1 notes](releases/v1.6.1-fork.1.md) 保留不变。

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

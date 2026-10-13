# 架构与模块职责

2026-10-12 本机增加只读响应检查：`domain/uds_response.py` 提供纯 UDS 基础字段解析，`application/response_inspection.py` 提供显式输入类型与 DoIP 去封装，`ui/response_inspection.py` 提供实时/离线视图。沿用 DataReceivedEvent/现有唯一桥与主线程控制器，不增加 Port、事件、worker 或 timer；原收发/等待策略保持现状。实际范围与验证见手动诊断（本机资料：`local/specifications/manual-diagnostic.md`）。

2026-10-12 资料补充：收到 D08 架构全景（本机资料：`local/replication/architecture-panorama-2026-10-12.md`），细化模块、Port 和装配职责，采用摘要见第 10 节。D08 混有 v4.0/2026-10 版本线索及概述冲突；本机 import 白名单、原 11 事件、v3.8.37 目标和实际实现边界均不因此改变。

2026-10-11 本机更新：诊断 MAIN 的纯 codec、TCP worker、唯一 DoIPAdapter、ManualDiagnosticService 与异步 ProjectConfigurationAdapter 已接线，入口不创建 socket/SDK。PageContext 在原四参数后增加可空 projects/manual_diagnostic/log_export；六页与显式演示继续保留。下文 P1 清单属于历史基线，新功能及边界见 本机手动诊断（本机资料：`local/specifications/manual-diagnostic.md`） 和 覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。Socket 池、UDP、CAN、DTC/安全等没有因此完成。

本规范将 D01、D02 和 A-Q14—Q16 的明确描述整理为复刻工程的技术约束。当前已建立 P1 骨架；文中完整模块职责仍是后续目标，实际文件及边界见第 9 节。功能编号和交付状态见 [需求清单](requirements.md)。

## 1 目标与系统边界

OpenDiag 是 Windows 桌面 ECU 诊断工具，统一编排 DoIP／DoCAN 上的 UDS、刷写及自动化流程。CAN、继电器、电源、SSH、项目安全 DLL、DBC／DTC 资源和抓包工具通过适配器接入。数据采用文件存储，无数据库服务。

| 外部边界 | 适配职责 | 当前本机状态 |
| --- | --- | --- |
| ECU TCP／UDP | DoIP 连接、分帧、测试 Socket 池 | 诊断 MAIN TCP 已实现且 loopback 验证；独立池/UDP 未接线，无真实 ECU 验证 |
| ECU CAN／CAN FD | ISO-TP 传输与 CAN 硬件 | 未实现，无 SDK 或回环结果 |
| 项目安全 DLL | Seed & Key、可选 CMAC、32 位子进程桥 | 未收到 DLL／项目模块／向量 |
| DBC／DTC／E2E | 项目数据加载、信号和码表解析、保护参数 | 未收到完整数据 |
| SSH／SFTP | 远程命令、文件传输、MD5 验证 | 未实现 |
| Modbus RTU | JY-DAM0800、KPS3020D | 未实现，无台架验证 |
| TShark／PCAP | 网卡录制、用户层后备录制 | 未实现 |
| 本地文件 | 配置、脚本、固件、运行日志、报告 | 已有通用主 JSON 工具及骨架日志；原配置、脚本、固件和报告未收到 |

## 2 导入白名单

A-Q15 明确以 D01 §3.2 的白名单为准。原文箭头混合了逻辑调用与实现关系，不作为 import 检查依据。

| 层 | 规划目录 | 允许依赖 | 禁止依赖 |
| --- | --- | --- | --- |
| Domain | `src/domain/` | 标准库、自身领域模块 | Qt、其他业务层 |
| Ports | `src/ports/` | Domain、自身契约 | Qt、Adapters、Application、Core、UI |
| Core | `src/core/` | Domain、Qt、自身实现 | Ports、Adapters、Application、UI |
| Adapters | `src/adapters/` | Ports、Domain、Core、Qt、外部库 | UI |
| Application | `src/application/` | Ports、Domain、Adapters、自身模块 | Core、UI、直接 Qt 依赖，组合根例外见下文 |
| UI | `src/ui/` | Ports、Application、Qt、自身模块 | Core、Adapters、Domain |
| Security | `src/security/` | 标准库、共享纯算法模块 | Qt、其他业务层 |

仅 `AppContainer` 和 `ProtocolBootstrapper` 作为组合根可以导入 Core/UI 进行装配。这不是对整个 Application 包开放例外。允许 Application 依赖 Adapters，并不意味着服务应该到处创建具体实现；服务仍以构造注入接收 Port。

纯领域模型通过 `ports/model_types.py`、枚举通过 `ports/enum_types.py`、常量通过 `ports/constants.py` 重导出，供 UI 使用而不直接穿透 Domain。Port 使用普通基类和 `NotImplementedError`，保留 duck typing 插件适配。

## 3 规划目录

下列树包含完整后续阶段目标，不是已实现文件清单。当前 main、pyproject 和七层包已建立；真实业务及构建仍按阶段补充。

```text
main.py                         应用入口
pyproject.toml                  包元数据和依赖
src/
  app_setup.py                  根目录解析、日志初始化
  version.py                    运行版本来源
  domain/                       实体、枚举、值对象、纯协议／算法逻辑
  ports/                        契约、领域事件、类型重导出
  core/                         协议对象、接收缓冲、刷写、配置及测试基础设施
  adapters/                     Port 实现、Qt 信号桥接、硬件和外部库封装
  application/                  容器、服务、自动化纯逻辑引擎
  ui/                           窗口、页面、控件、样式、ViewModel
  security/                     共享 AES-CMAC 和 Demo 安全模块
tests/                          实际创建后按层镜像
config/<项目>/                  项目配置、插件和资源
testcase/<项目>/                同名项目的 YAML／JSON 测试数据
libs/zlgcan/                    对应 SDK 及依赖
python312-32/                   32 位安全 DLL 桥运行时
build/build_release.py          冻结与审计脚本
docs/                           当前工程规范与交付记录
logs/                           运行产出，不提交
```

## 4 关键模块

| 模块组 | 职责及接口边界 |
| --- | --- |
| DoIP | `DoIPProtocol` 负责连接收发；组包集中纯函数；接收缓冲处理 TCP 粘拆包；解析器产出结构化报文 |
| UDS | 构造与解析服务请求响应；请求关联、Pending 和业务等待分层处理，不把所有服务当有子功能 |
| ISO-TP | 纯分帧／重组逻辑与适配传输分离；物理／功能寻址和 FC 协调由传输层负责 |
| 双栈诊断适配 | DoIP 与 DoCAN 实现共同的连接／诊断契约；不假定两条链路的原始事件字节格式相同 |
| 刷写 | `FlashManager` 三阶段状态机；服务提供配置、载入、开始停止；安全结果经专用契约回注 |
| 自动化 | 纯 Python `TestEngineCore`、状态与超时管理、操作注册表；Qt shell 提供主线程调度和保活 |
| DoIP 一致性 | Socket 池、原始构包、独立执行器和匹配规则；与 UDS 自动化共享部分脚本结构，不混成一个执行器 |
| CAN | 硬件初始化、通道、DBC、周期发送；每帧 E2E 注入；默认通道限制按原版事实记录 |
| 安全插件 | 项目扫描、声明校验和能力探测；普通 security.py 与 plugins 入口规则分别处理 |
| 配置 | 全局设备基值、项目覆盖、运行快照；加载失败保留旧项目，不携带旧项目覆盖进入新项目 |
| 报告与日志 | 文件日志和实时运行日志独立于 UI 行数限制；报告分类与展示口径由对应规范约束 |

完整 Port 与事件见 接口文档（本机资料：`local/specifications/api-reference.md`）；未提供的参数声明不能根据方法名字补造。

## 5 启动和依赖装配

1. 解析应用根目录和运行产出路径，建立日志与 Qt 消息处理。
2. 创建唯一 QApplication，配置 DPI、Fusion、亮色调色板和应用样式。
3. Bootstrapper 创建协议／配置／刷写等对象；容器装配 Adapter、领域事件总线和 Service。
4. 为诊断、刷写、DTC、自动化和 DoIP 测试的 PageContext 注入端口；建立窗口与控制器。
5. 同步加载首页，其余页面由主线程逐 tick 延迟加载；初始化阶段不主动打开 CAN／串口。
6. 窗口可用后恢复上次项目和 UI 会话状态，检查版本更新说明。

原启动代码曾引用不存在的 `config/demo.json`，实际走内置默认，再由项目配置覆盖（A-Q24）。新工程应明确默认值和未加载项目态，不为模拟旧缺失路径专门造一个错误。

冷启动 ≤3 秒是原资料目标；计时和验收见 [测试规范](testing.md)，目前未测量。

## 6 数据和控制路径

| 场景 | 主要路径 |
| --- | --- |
| 手动 UDS | 页面→诊断 Port／服务→传输实现→发送工作线程→ECU；响应→接收线程→Adapter→总线→主线程页面 |
| DoCAN | UDS 请求→ISO-TP→CAN Port→SDK；CAN 接收→筛选／FC／重组→UDS 事件 |
| 自动化 | 文件解析→纯引擎→操作策略或内建 send/expect→Port；结果→shell→UI／RunLogWriter／报告 |
| 刷写 | 固件和阶段配置→FlashService→FlashPort→刷写 worker→进度／完成事件 |
| E2E 周期帧 | CAN 服务→每帧软件周期回调→E2E 更新→硬件发送；不能一次预计算后重复同一保护值 |
| 项目切换 | 异步解析→成功后应用上下文→基于全局值重算项目覆盖→按需要重建硬件及诊断端口 |

发送与接收时间戳在实际网络动作边界生成，不能改成 UI 渲染时间。对停止、重入、重连和迟到回调使用代际／执行索引防止旧任务更新新状态。

## 7 项目隔离

四项目为 项目A、项目A_DoCAN、项目B、demo。每项目差异来自配置和测试数据，通用层不得出现按项目名称判断的分支。项目A_DoCAN 引用 项目A 的 DBC，不复制整套资源做变体。

全局配置保留物理设备与会话状态；项目可覆盖 DBC、E2E、有限的接线字段以及继电器 channels。没有项目覆盖文件时回全局基值，不继承上一项目。完整规则见 配置参考（本机资料：`local/specifications/config-reference.md`）。

## 8 已知实现边界

- 原 DoCAN 诊断传输上限 4095 字节、FD 诊断帧 DLC 仍为 8；不是完整 64 字节 ISO-TP 实现。
- 原工程宣传多硬件，但 A-Q21/Q22 只明确单默认通道下的同 ID 替换与 counter 行为；多设备同 ID 尚无完整契约。
- 原版主连接路由激活只确认发送，不确认返回码；刷写错误检查 0x00。协议事实已澄清，是否保持旧可见行为见决策记录。
- 已收到一张 UDS 手动部分截图；其余原界面素材、项目资源及测试资产未落地，依赖原文件的功能仍待材料。

这些边界不自动缩减目标。范围冲突与兼容选择见 决策记录（本机资料：`local/specifications/decisions.md`），实现进度见 [实施计划](implementation-plan.md)。

## 9 P1 本机实际实现（2026-10-03 历史基线）

- [入口](../main.py)、[初始化](../src/app_setup.py)、[版本](../src/version.py) 和 [包元数据](../pyproject.toml)：未发布 `3.8.37.dev0`，版本由单一源提供；烟测 CLI 仅用于基础工程验证。
- [AppContainer](../src/application/app_container.py) 装配配置、总线、后台日志和 [PageContext](../src/application/page_context.py)，不创建协议连接、硬件或插件。PageContext 是本机最小注入契约，非原版完整声明。
- [应用路径](../src/core/app_paths.py)、[配置工具](../src/core/config_manager.py)、[配置适配](../src/adapters/config_adapter.py) 已实现；项目加载为独立同步工具，尚未接入 UI 项目切换服务。
- [领域事件](../src/domain/events.py)、[Qt 总线](../src/adapters/qt_event_bus.py) 保留 11 个事件映射；[主窗口](../src/ui/main_window.py) 同步建立首页，其余五页逐 tick 建立，并维持无项目／未连接状态。
- Security 包当前仅标明共享纯算法的位置，没有安全算法、Demo 解锁或真实 DLL。其余业务 Ports 随实际实现建立，未生成假成功适配器或推造完整签名。

2026-10-03 的 UI 预览依据一张原窗口局部截图调整主布局，采用本机无边框标题栏、六页导航、[指令编辑器](../src/ui/command_editor.py)、[次要页面](../src/ui/workspace_pages.py)、[配置弹窗](../src/ui/config_dialogs.py)及[主题/绘制图标](../src/ui/theme.py)。默认仍为无真实项目/未连接；显式 `--ui-demo` 只切换本地演示状态并通过既有 LogEvent 记录请求预览，不创建连接或发送领域事件，也不替代真实业务 Port。文本导入/导出采用粘贴和复制预览，不读写原项目文件；配置草稿仅属于当前窗口。

通信/应用日志仍经 PageContext 订阅既有事件；日志表只转换前 171 字节以展示最多 512 字符，完整 bytes 保留供用户显式复制。关闭窗口停止逐 tick 加载、toast timer/动画，关闭所有所属弹窗并取消日志订阅；事件循环结束后容器释放后台日志线程。完整控件、原图标/QSS、日志抽屉/其他动画、Windows DPI 与视觉一致性继续按 [界面规格](ui-specification.md)验证，实际测试见覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。

## 10 D08 补充的模块与装配职责

以下为收到资料的职责线索，非本机新增实现。D08 的原路径、方法名和版本冲突完整保留于接收与采用记录（本机资料：`local/replication/architecture-panorama-2026-10-12.md`）及其文本提取。原源码/API 字面兼容范围仍按 D-01/D-12 处理，不为目录一致性直接重构现有可用代码。

| 模块组 | D08 细化的职责 | 后续边界 |
| --- | --- | --- |
| 领域和模型 | DoIP/UDS 子包、不可变 EcuAddress/HexString、ExecutionContext、CAN/E2E/两类电源模型 | 字段、构造/默认与上下文作用域仍缺；死模型删除声明保留版本标记 |
| 测试契约 | ResponseParser、ScriptParser、TestExecutor、SocketPool 四个子契约及聚合入口 | “v4.0 起聚合”不自动成为 v3.8.37 签名要求；两套执行器语义仍分开 |
| CAN 诊断 | ZLG/Tscan 硬件 Adapter，IsoTpTransport 叠加 CanControlPort，诊断/连接 Adapter 负责事件与生命周期 | DoCAN 无 RA/ICMP；ISO-TP 上限、E2E 参数/硬件向量按专项规范，不由类名推定 |
| E2E 和配置装配 | Core E2eConfigLoader 读取 e2e_config_file，组合根加载后注入 CanControlService | 不将配置加载放入 UI，不生成缺失项目数据 |
| 插件和自动化 | PluginService 薄门面 → PluginLoader；纯 TestEngineCore/state/timeout/operations → Qt engine_shell | 页面不直接 import 项目插件；Shell 调度与后台 IO/保活按线程规范 |
| 窗口和公共 UI | 窗口控制、连接/导航、PageFactory、配置/日志协调、窗口状态、公共控件/样式/动画 | 可用于后续维护拆分；控件行为与视觉仍以 DS-01/界面规范和实际材料为准 |

D08 的显式白名单与第 2 节一致，箭头串中 Core → Ports 的表述不能用作 import 许可。其“仅容器知道具体 Adapter”按装配责任理解，不推翻 Application 可依赖 Adapters 或 ProtocolBootstrapper 例外。启动图的 config/demo.json 沿用 A-Q24 的缺失路径勘误；本机入口仍为根 main.py。硬件延迟初始化、首页同步/其他页逐 tick 的方向继续采用，恢复上次项目和版本弹窗的全部交互未由概览补齐。

# OpenDiag 工程协作约定

本文件适用于整个仓库，供开发者及代码代理共同遵守。当前已建立七层工程、DoIP 主连接及 UDS 手动收发／解析和本机测试；其余业务、完整项目资产与硬件 SDK 尚未落地。不要把文档中的原工程路径、行号、测试数量或版本当成本机实现证据。

## 先读这些文件

1. [README.md](README.md)：当前状态和入口。
2. [docs/publication.md](docs/publication.md)：资料目录、公开上传边界和本机资料缺失时的规则。
3. 本机存在时阅读 `local/replication/README.md` 与 `local/replication/answer-status.md`：来源与 Q01—Q32 状态。
4. 本机存在时阅读 `local/specifications/decisions.md`：已采用事实及待决行为。
5. [docs/architecture.md](docs/architecture.md)、[docs/thread-model.md](docs/thread-model.md)：分层和线程规则。
6. 开发前再读对应的协议、配置、流程、界面和测试文档，入口为 [docs/README.md](docs/README.md)。
7. 新增或修改页面、公共控件、弹窗前，必须读 [UI 设计系统 DS-01](docs/ui-design-system.md) 与 [界面规格](docs/ui-specification.md)：前者规定共用视觉与扩展流程，后者登记业务语义和来源。

公开克隆不包含 `local/`、真实项目或 SDK。缺少材料时继续不依赖它们的工作；涉及项目参数／未决行为的实现须明确材料缺口，不能补造。原始文档与完整历史仅迁移到本机资料目录，公开说明中的项目代号已匿名化。

## 需求和证据

- 用户的直接指令优先。最终目标是完整复刻确认范围内的功能、界面和交互，不自行把目标缩成 Demo 或最小版本。
- 新答复中的明确原版事实用于修正旧资料；其中“建议”“待核对”“缺失”“由用户决定”仍按原标记保留，不当作用户已确认。
- 原版行为、原版已知缺陷、复刻建议及本机验证结果分别记录。实现改进不能伪装成原版行为；不为追求一致而默默复制已知协议错误。
- 真实资源在原电脑存在，不等于本机已收到；资料中的“可以移交”不构成用户授权。`security.py` 和插件是可执行代码，不能因为位于 `config/` 就称为纯数据。
- 原始 DOCX 和问题文档保留为历史资料。收到补充说明后更新规范、答复状态和决策记录，不篡改原文造成证据丢失。
- 普通且可逆的实现选择由开发者在授权范围内完成并记录，无须逐项求批准。涉及范围取舍、用户可见行为冲突或未定义硬件恢复行为时，保留待决并继续不依赖它的工作。

## 技术基线和目录

- 目标平台 Windows 10/11 x64；目标解释器 Python 3.12.10 x64；GUI 使用 PySide6，不混用 PyQt5。
- 源码按 `src/domain/`、`src/ports/`、`src/adapters/`、`src/application/`、`src/core/`、`src/ui/`、`src/security/` 分层；入口为根目录 `main.py`。已建立骨架，不能由目录存在推定业务已完成。
- `src/` 顶层业务模块限应用初始化与版本声明；项目参数和差异不放在 `src/`。
- 持久化采用 JSON/YAML/DBC/Excel 和文件日志；没有 SQL 数据库需求。打包采用 cx_Freeze，不因原环境残留了 PyInstaller 就改换构建方案。
- 运行／测试依赖已按资料版本在项目 venv 解析安装；使用 [docs/environment.md](docs/environment.md) 中的直接依赖和本机快照，不全量安装原电脑 freeze 中的工具和历史残留。cx_Freeze 构建环境尚未建立。

## 分层规则

以 [docs/architecture.md](docs/architecture.md) 的 import 白名单为准，不能把业务调用箭头误读成 import 规则。

- Domain：标准库和自身领域模块；无 Qt，不依赖其他业务层。
- Ports：Domain 和自身契约；无 Qt；普通基类方法抛 `NotImplementedError`，不改成强制 ABC 体系。
- Core：Domain、Qt 和自身实现；不导入 Ports、Adapters、Application、UI。
- Adapters：Ports、Domain、Core、Qt 与必要外部依赖；不导入 UI。
- Application：Ports、Domain、Adapters 和自身模块；除组合根外不导入 Core、UI，不直接依赖 Qt。
- UI：Ports、Application、Qt 和自身模块；不直接导入 Core、Adapters、Domain。领域类型通过 Ports 的类型重导出使用。
- Security：共享纯算法；不依赖其余业务层和 Qt。
- 仅 `AppContainer` 与 `ProtocolBootstrapper` 是装配例外，可导入 Core/UI。服务以构造注入接收 Port；UI 经 PageContext 获得端口。
- 项目 `plugins/*.py` 的禁止导入 `src` 规则与根 `security.py` 复用共享纯算法的例外分别遵守，见 API 文档。

## 线程和事件

- 使用 `threading.Thread(daemon=True)`；不引入 QThread、线程池或 asyncio 作为替代模型。
- 工作线程不读写 UI；Qt 事件经 Adapter 和领域总线回主线程，跨线程槽使用明确 receiver 的绑定方法。
- 每个 socket 一个接收线程；接收路径不做磁盘写入、阻塞业务或 UI 更新。连接和 `sendall/sendto` 在工作线程执行。
- 停止用标志、Event、超时及自然退出，不强杀线程；重连防止旧线程或过期回调污染新会话。
- 允许的共享同步手段：结果容器＋Event、ISO-TP Condition、有界块写入队列、锁保护 E2E counter；发送锁负责串行化。其他共享可变状态须先明确归属和同步设计。
- 36 快速路径是主线程响应回调决定下一块、发送线程做 socket IO；不是允许主线程写 socket。
- 总线跨线程 publish 排队回主线程；同线程直接分发，不承诺同步订阅者执行也为 O(1)。订阅者不得做重活。
- 固定的 11 个事件映射不得随意重命名、删除或复用为不同语义；需要新增时同步补契约、桥接和验证。
- DoIP 的 DataSent 载荷为完整 DoIP 帧，DoCAN 为完整 UDS 请求；时间戳表示发送开始，不等于发送成功。不要未经决定就统一两者格式。

## 协议和业务实现

- 协议数据内部使用 `bytes`；文本边界集中校验和转换 hex。枚举和纯组包逻辑集中维护，避免散落魔法数字。
- 路由激活线上成功码为 `0x10`；`0x0004` 为车辆公告／识别响应；ResponseTooLong 为 `0x14`。原版错误行为的兼容策略见决策记录。
- 自动化通用 NRC78 静默等待并重置挂起计时；38 操作和刷写 `nrc78_wait` 有不同重发策略。不能套用单一 Pending 规则。
- UDS 自动化与 DoIP 一致性执行器的 expect 语义不同；`send/expect` 为内建步骤，27 个注册名对应专用操作。原引擎没有通用 retry。
- 原版 DoCAN ISO-TP 按 8 字节布局，即使外层是 FD 帧；最大 UDS 载荷 4095。不要默默承诺 64 字节 ISO-TP 或把 4096 字节刷写块送入该链路。
- 项目专用 DID、RoutineID、Seed & Key、DBC、E2E、接线和脚本只能来自项目配置或步骤参数。不能用项目名分支或臆造数据填补缺失资源。
- 通用 AES-CMAC Demo 不代替真实 ECU 解锁；硬件、DLL 加载失败显式报告，不能静默切到模拟器或默认型号。
- 硬件启动延迟到显式操作或测试按需初始化；停止、失败、断连后的电源／刷写恢复策略未明确前不自行假定。

## 配置和界面

- 项目位于 `config/<项目>/`，测试数据位于同名 `testcase/<项目>/`；跨项目切换不继承上一项目的覆盖值。
- 写回保留未知键和 `_comment_*`；历史死参数的兼容和新增生效行为分别记录。字段非法处理遵守专用校验规则，不能用“统一回退”掩盖型号等必须报错的输入。
- 路径从应用根目录解析；不硬编码原电脑 `d:\doip` 或当前电脑绝对路径。SSH 凭证经既定环境变量优先读取，不写入公共文档、日志或提交。
- 没有收到截图、QSS、图标和完整控件表前，只能声明结构还原进度，不能宣称原界面完全一致。
- 全部可见控件、默认值、禁用条件、快捷键、错误提示和持久化行为须在界面规范有对应记录；不擅自删掉难实现的页面。
- 当前本机 UI 采用 [DS-01](docs/ui-design-system.md)。颜色、间距、尺寸、数据字体和表格密度经公共主题定义；新增页面复用公共控件与按钮角色，新增变体先更新规范和 token。原参照事实与用户授权的本机新设计分别登记，不将新设计称为原版视觉一致。

## 开发和验证流程

1. 查对应 F 功能编号、Q 问题状态和依赖材料，明确本次改动边界。
2. 先读相关规范与已有实现，再完成改动；保留用户已有文件和未提交工作。
3. 按影响范围运行验证；公共协议、线程、事件或基础配置变更扩大到相关回归。
4. 检查功能正确性、错误路径、资源释放和分层，不以界面能打开代表业务完成。
5. 同步更新相关规范、测试覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）、变更记录（本机资料：`local/history/version_change-before-publication.md`）；实际缺陷修复再登记 [bugfix_record.md](docs/bugfix_record.md)。
6. 汇报改动、执行过的检查、仍未验证的真实硬件／视觉／性能项。

应用测试建立后，使用 `venv\Scripts\python.exe -m pytest`；Qt 测试复用 session 级 QApplication fixture；信号测试使用事件等待工具，不用固定 sleep 猜测完成。线程测试验证线程、socket、timer 和文件句柄释放。精确命令见 [docs/testing.md](docs/testing.md)。

目前已有 `venv/`、`tests/`、`main.py` 和 `pyproject.toml`；构建脚本尚未实现。代码改动运行对应实际测试，文档改动检查链接、编号、来源和矛盾。新功能需要有意义的验证，不为文案等低影响修改堆砌镜像测试。

## 版本和交付

- v3.8.37 是复刻目标版本，不代表本机已发布该软件；本机开发状态在 README 和未发布变更记录中维护。
- 未来实现后，运行版本单一来源为 `src/version.py`，包元数据同步；不得把“历史遗留 3.8.0”作为新包版本。
- 不伪造原版发布历史、2000+ 测试通过记录或真实硬件验证结果。
- 模拟验证、真机验证、界面对照和冻结包验证分别登记；缺少真实资产的功能不得标完成。
- 提交说明用中文，采用 `feat/fix/refactor/docs/test/chore: 简述`。2026-10-12 已初始化本地 Git（`master`）并配置用户指定提交身份和 `Animal279/Opendiag` 远程；2026-10-13 按用户确认范围完成整理及公开上传，敏感资料与旧 Git 历史仅留本机，最新状态见同步说明。分支和本地构建约定见 [docs/branching.md](docs/branching.md)，公司 PC 取码见 [docs/github-sync.md](docs/github-sync.md)。

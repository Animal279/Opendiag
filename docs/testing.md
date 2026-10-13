# 测试与验收策略

2026-10-12 增加 `tests/application/test_response_inspection.py` 和 `tests/ui/test_uds_response_view.py`，验证纯字段解析、错误/有界大载荷、离线入口、loopback 接线与显示生命周期、最小窗口可见区域。全量命令及最新实际结果见覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）；不以显示 ECU 时序代替客户端等待或真机测量。

2026-10-11 新增实际 loopback TCP 和 UI 手动链路集合：`tests/domain/test_doip.py`、`test_connection_settings.py`、`tests/adapters/test_project_configuration.py`、`test_log_export.py`、`tests/core/test_doip_receive_buffer.py`、`tests/application/test_manual_diagnostic_service.py`、`tests/integration/test_doip_transport.py`、`test_manual_diagnostic_workflow.py`、`test_diagnostic_logging.py`、`tests/ui/test_manual_diagnostic.py`。全部使用现有 venv；FakeDoIPServer 仅明确队列回应，不会自动给应用成功。完整命令与最终结果见 覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。公司真实 ECU、性能与冻结包继续单列待验。

更新日期：2026-10-03。当前已有 P1 应用骨架、截图布局 UI 演示、`tests/`、项目 `venv/` 和 pyproject 中的 pytest 配置；构建脚本尚未实现。本文规定完整验证方法，实际执行结果见覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。D01–D07、A-Qxx 与 S01 的含义见来源索引（本机资料：`local/replication/README.md`）；原电脑测试数量、路径与结果未在本机复现。

完整范围以[需求矩阵 F01–F21](requirements.md)为准。验证同时记录实现正确性和对原版的还原程度；已知原版缺陷不能作为新实现必须保留错误的理由，处理方式先进入决策记录（本机资料：`local/specifications/decisions.md`）。

## 1. 五类证据分别登记

| 类别 | 可证明的内容 | 不能替代的内容 | 当前状态 |
|---|---|---|---|
| 模拟与自动化 | 纯算法、协议编解码、Port 契约、配置、执行器状态、Qt 事件和模拟交互 | 厂商 ABI、设备接线、真实 ECU 时序、原界面视觉一致性 | 已建立 P1 基础覆盖，业务与完整协议尚未覆盖 |
| 真机与台架 | 实际设备、DLL、E2E/安全向量、刷写、OTA、电源和故障恢复 | 其余项目/固件/设备型号；模拟未覆盖错误分支 | 未验证；所需资源未收到 |
| 界面对照 | 页面、文案、布局、DPI、图标、颜色、交互状态和动画与参照一致 | 仅凭窗口可打开不能证明业务完成 | 已收 S01 单张部分截图，主布局开始对照；其余页/状态、QSS、图标和完整控件表未收到 |
| 性能与长稳 | 指定环境和负载下的启动、传输间隔、内存、队列、UI 响应和网络行为 | 未测机器、未定义阈值、其他负载 | 未测量 |
| 冻结包与部署 | cx_Freeze 产物的完整性、资源解析、目标机运行和关键业务路径 | 源码运行通过不能证明冻结包可用；存活不能证明业务正确 | 未构建 |

一项需求可以“模拟通过、真机待验”，但整项仍应为“待验证”。缺少材料、未执行、失败、经用户明确接受的例外分别填写，不使用“通过”统称。真实项目 项目A、项目A_DoCAN、项目B 分别登记；demo 不替代前三者。

## 2. 未来测试结构和基本规则

以下为拟建目录，不表示已收到原测试。未来按分层建立 `tests/domain/`、`tests/ports/`、`tests/core/`、`tests/adapters/`、`tests/application/`、`tests/security/`，并建立 `tests/ui/`、`tests/threads/`、`tests/integration/`、`tests/regression/`、`tests/fixtures/`。只有存在需要持续守门的真实规则时再建立 `tests/docs/`，不为单次文案变更制造镜像测试。

- 业务依赖经 Port 构造注入，可用 `create_autospec(Port)` 验证契约；真实适配器装配另有集成覆盖，不能全用 mock 掩盖接线错误。
- Qt 测试统一复用 session 级 `QApplication` fixture；信号等待采用事件等待工具及明确超时，不用固定 `sleep` 猜测异步完成。
- 线程测试验证连接/发送离开主线程、跨线程槽回到正确 receiver、停止后的线程/socket/timer/文件句柄释放，以及旧连接回调不会污染新会话。
- timeout、暂停、重试、重启计时使用可控制的时钟/调度替身验证边界；另以真实 TCP 和 Qt 事件循环验证实际装配，不把模拟时间等同于性能测量。
- 模拟器显式注入。真实设备或 DLL 加载失败必须可观察，不能自动改用模拟器让测试变绿。
- 数据文件写入使用独立临时目录，避免改动真实项目配置；测试凭证和 keyMat 不写入报告或提交。
- 原测试没有移交，本机新增测试不沿用“原 2000+ 用例通过”的宣传。将真实文件、断言和证据登记到测试覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。
- UI 演示另验证默认无项目/无连接、不创建配置或加载硬件，显式演示只产生本地请求预览而不发布 ConnectionEvent/DataSentEvent 或伪造 RX。指令非法输入、粘贴导入全量校验/不部分追加、编辑回退、勾选/排序/删除、连接预览状态和关闭 timer/订阅分别覆盖。
- 草稿弹窗验证取消不改会话、接受只改窗口草稿、非法型号/地址/端口不静默回退；二级页面验证可编辑参数与不可用业务入口、DoIP raw/hex 边界。文本复制不作为原文件导入/保存或状态持久化通过证据。

## 3. 模拟器和公共回归

A-Q30 对原 FakeDoIPServer 的描述仅包括：`127.0.0.1` 随机端口、单 TCP 连接、`queue_response` 预置响应队列、daemon 线程及结束自动停止。完整行为与断言摘要尚未收到。重建时保留这一可验证基础；下面的故障注入能力是本机测试设计，需要实际实现后才算具备：

| 场景 | 必须观察的结果 |
|---|---|
| DoIP 头/载荷被任意 TCP 分段、连续多帧粘包、非法头和超长声明 | 正确缓冲/解析或明确拒绝；残留字节不会误解析为下一会话 |
| 连接超时、拒绝、远端关闭、RA/ACK/NACK、迟到响应 | `connect()` 受理与连接完成分离；事件只桥接一次；状态和错误一致 |
| 无响应、连续 NRC78、超时前后响应 | 按具体操作的等待/重发规则处理；停止/切组后旧定时器失效 |
| 重复或错序 76、短块、整块倍数、零字节传输、写盘异常 | 依据已确定契约判定；未定义边界记录待决，不能由测试替身自行规定原版行为 |
| MAIN/TEMP/TEMP1/UDP 使用与关闭 | 主连接和池连接身份正确；完成/停止释放池资源；并行用例不会误消费别的响应 |
| 重连、反复启动停止、切换项目 | 订阅和线程不累积；旧回调失效；项目覆盖值不泄漏 |

公共回归至少包含：架构 import 白名单与精确装配例外、固定 11 个事件映射、跨信号泄漏、真实传输到 Adapter 的装配、通信状态机及线程健康。原文列出的测试文件名只是重建参考，不假定文件已存在。

## 4. 功能覆盖与关键边界

详细字节规则见协议规范（本机资料：`local/specifications/protocol-reference.md`）、流程规范（本机资料：`local/specifications/uds-workflow.md`）；本表只定义验证义务。

| 需求 | 模拟/自动化重点 | 额外验收或缺口 |
|---|---|---|
| F01 DoIP | TCP 分粘包、D-15 的完整 RA 0x0006/0x10、正常请求 11B 载荷、被动 Alive Check、NACK、ICMP 状态、断连/重连和旧事件 | 真实 ECU 报文；拒绝/超时显示及其他兼容策略另追踪（Q05/10） |
| F02 手动 UDS | 按服务构包、短帧/未知 NRC/0x14、P2/P2*、27 暂停保活及失败恢复 | 全服务控件、指令行为和 SID/DID 不匹配规则待补（Q07/11/26） |
| F03 DTC | 19 02/04/06、14FFFFFF、JSON 优先、Excel 第 0/2 列、重复覆盖/空值/未知码 | 真实码表与快照/扩展记录样例（Q26） |
| F04 刷写 | HEX 地址/长度/加载顺序、TXT 11 关键字、34/36/37、停止/重连/重试、进度 | 真 ECU 成功和失败轨迹；失败后 post、BIN/S19 范围待决（Q09） |
| F05 自动化 | 全 27 注册名与 23 策略、pre/steps/post、暂停/停止、每操作超时、配置隔离 | 字段 Schema 与样例；post 再失败、capture 作用域仍需澄清（Q08/17/18） |
| F06 一致性 | 与 UDS 分开的 expect 矩阵：exact/include/not_include/none/any、type/code、Socket 池 | count/interval/disconnect 组合及容差；车辆发现范围待决（Q06/18） |
| F07 DoCAN | SF/FF/CF/FC、序号/回绕、FC Wait/Overflow、STmin、断连唤醒、4095B 接受及 4096B 拒绝 | 真机验证 FD 外层而 ISO-TP 仍按 8B 布局；并发发送边界（Q12） |
| F08 CAN | SDK 替身的设备/通道/帧转换、软件周期替换、DBC 解析、停止释放 | ZLG 与 TOSUN 分别真实回环；同 ID 多设备/远程帧/错误帧边界（Q22） |
| F09 E2E | CRC 字节排除、DataID 顺序、偏移、多 PDU、首帧、14→0、停启续数/切项目重置、锁 | 完整 18 报文与真实向量；短载荷行为待决（Q21） |
| F10 安全插件 | calculate_key 契约、可选能力、DLL 缺失/126/193、32 位桥格式、Demo 向量 | 真实项目 DLL/依赖/ECU 解锁向量；Demo 成功不代替（Q04/14） |
| F11 OTA | 两套轮询、包装、status 优先、恢复后完整 max_wait 重算、第二次断连、旧 timer | 真实上传/安装/重启；暂停和重入轨迹（Q20） |
| F12 云端日志 | 38 04 路径、36 序号、流式落盘、NRC78、MD5、失败和临时文件清理 | LogPack/F1BB 完整布局、真实 ECU 文件（Q19） |
| F13 FBL 日志 | 35→36、短数据块结束、无 37、序号回绕、断连和清理 | 零字节/整块倍数仍须台架证据（Q19） |
| F14 SSH/签名 | SSH/SFTP 失败和超时、stdin、编码、MD5、多文件、local_command 工作目录 | 签名算法/数据缺失；取消增强待决，不编造签名（Q27） |
| F15 电源/继电器 | Modbus 组帧/回显、串口重开、动作失败、硬件延迟初始化 | 真实接线/允许电压电流、PULSE 停止及恢复决定（Q23） |
| F16 录制 | TShark 选择/启动/健康检查/停止；后备 PCAP 长度与伪头 | 用独立读取器检查实际产物；超长截断、DoCAN/轮次切分范围待决（Q29） |
| F17 UI | 页面/弹窗状态、输入校验、导航、持久化、DPI、线程与日志上限 | 逐页截图/文案/交互/动画对照，见[界面规格](ui-specification.md) |
| F18 配置 | 按配置参考（本机资料：`local/specifications/config-reference.md`）逐字段验证环境变量/项目/全局/内置优先级、未知键保留、损坏/非法字段、切换失败保旧、B 不继承 A | 完整 Schema/默认值；环境变量仅适用于已定义字段，按字段区分回退与必须报错（Q24/25） |
| F19 日志/报告 | 4 级别+TX/RX、应用面板仅 WARN/ERROR、DEBUG 开关、5000 行淘汰、自动/手动导出 | 通过/失败/阻塞/停止报告样例、精确分母、大 payload 完整复制待核对（Q28） |
| F20 构建/部署 | 版本单一来源、资源路径、延迟导入和 DLL 审计 | 冻结目录/ZIP、干净 Windows 机器与驱动环境，见第 6 节 |
| F21 验收体系 | 需求→测试→证据互链；失败和未执行显式记录 | 五类证据、真实项目覆盖和待决项均收敛才能总体验收 |

## 5. 性能与长稳口径

2026-10-12 D08（本机资料：`local/replication/architecture-panorama-2026-10-12.md`）将 ≤3s 启动/主线程非阻塞列为原维护硬指标，超标归 P0；这是新增的来源要求，不是本机测量结果。其“到 app.exec() 即首帧可交互”仍有观测点歧义，以下保留事件循环入口、首帧与交互时刻分别记录的要求；本次资料接收未运行性能或业务回归。

以下数字来自 A-Q30 的原版口径，不是本机测量或已满足承诺。应先固定可重复测量条件，再形成验收阈值；不把一次样本外推为所有机器保证。

| 指标 | 已有来源口径 | 尚需固定和记录 |
|---|---|---|
| 启动 | 冷启动、开发机 SSD，进程启动至 `app.exec()` 首帧 ≤3s | CPU/RAM/SSD/OS、源码或冻结、缓存状态、首帧的实际观测点、首页可交互时间、重复次数及统计方式；“进入 app.exec”不能自动等于已渲染 |
| 36 间隔 | FOTA 供应商要求 ≤10ms，以带时间戳报文验证 | 哪条请求/响应之间、时间戳采集位置和分辨率、transport、块长、ECU/固件、统计分位及异常样本；主线程决策与发送线程实际 IO 分开测 |
| 4h 传输稳定性 | 答复称 4h 压测无 RST，以 ECU 日志和抓包判定 | 双向 RST 数、断连/重连、失败数与业务完整性；明确流量、网卡、ECU、文件和抓包丢包情况 |
| TCP Zero Window | 答复把“零窗口”与“无 RST”并列，二者不能互证 | 单独统计零窗口出现次数、方向、持续时间、恢复及发送阻塞；允许阈值未知，不能宣称必须为 0 或已经达标 |
| 大块/大文件 | Q13 称传输块可达 8MB，确切字节数待确认；与解析上限、256 块写队列分开，没有实测峰值 | 实际块与文件大小、吞吐、RSS/峰值、磁盘速度、排队块数/字节数、复制次数、停止清理；假设每块 8MiB，则 256 块载荷约 2GiB，不据 memoryview 宣称低内存 |
| UI 响应与资源长期增长 | 尚无定量门槛 | 事件延迟、持续日志/绘表负荷、内存/线程/句柄趋势；先测量和报告，阈值另定 |

压测必须同时验证文件完整性、错误提示和资源回收。高吞吐但丢报文/丢文件不能记成功；无 RST 也不能证明无零窗口或无应用卡顿。

## 6. 冻结包、目标机与视觉验收

- 构建采用 cx_Freeze。审计 Domain、Ports、Adapters、Application、Core、UI、Security 七个子包及延迟加载页面/硬件模块；清单来自原资料，实际冻结布局仍需逐文件确认。
- 在产物中检查项目资源、DBC、所需 DLL 及二级依赖、`python312-32/`、脚本、版本记录和应用根解析。按资源清单（本机资料：`local/specifications/resource-inventory.md`）区分随包资产与目标机外部驱动。
- 5 秒存活只作为冒烟信号。本机验收还需首页渲染、连接弹窗、项目/脚本加载、报告生成、DBC/适用 DLL 实际加载和关键协议路径；这些是工程验证要求，不能反写为原版已经通过的记录。
- 干净机记录 Windows 版本、解释器是否缺省、已装运行库/驱动、权限、中文/空格路径和不同启动目录。检测开发机路径或系统 Python 的意外依赖。
- 视觉按[界面规格](ui-specification.md)逐页逐状态比较。不同 DPI/缩放/显示器、还原与最大化、长文案和错误状态均记录；Qt offscreen 交互测试不能替代真实 Windows 字体/DPI 视觉对照。

## 7. 按影响范围选择验证

| 变更类型 | 应执行范围 |
|---|---|
| 纯算法/格式化 | 对应正常、边界、错误输入；有关联报文则增加协议向量 |
| Adapter/Port | 单元、契约、真实装配；跨线程事件和资源释放 |
| 协议/事件/线程/基础配置 | 相关功能回归与公共架构、事件、线程检查，必要时全量 |
| UI | 页面状态和交互、相关业务闭环；视觉材料齐全后对照 |
| 硬件适配/刷写/恢复 | 模拟错误路径，加对应设备与 ECU 台架记录 |
| 打包/公共依赖/发版 | 全量应用测试、冻结审计、目标机冒烟及受影响关键流程 |
| 仅文档 | 链接、F/Q 编号、来源、事实/建议/状态分离和矛盾检查；无须假建 pytest |

当前可执行 `venv\Scripts\python.exe -m pytest -q` 和 `venv\Scripts\python.exe main.py --smoke-test`。下列按目录命令仅在对应集合实际建立后执行；尤其 `tests/threads/` 当前未独立建立，线程基础验证位于 adapters、integration 和 UI 测试：

```powershell
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\python.exe -m pytest tests/regression/ tests/threads/ tests/ui/ -v
venv\Scripts\python.exe -m pytest tests/core/ -v --tb=short
venv\Scripts\python.exe -m pytest tests/integration/ -v
venv\Scripts\python.exe main.py
```

只执行已建立且与改动相关的集合；首次测试建设同时记录可用命令。硬件/长稳测试明确所需环境，不通过无说明的 skip 把未验项藏进通过率。

## 8. 单次验收记录模板

| 字段 | 待填写内容 |
|---|---|
| 记录 ID / 日期 / 执行者 | 待执行后填写 |
| F 编号 / Q 来源 / 待决项 | 具体需求、来源段落与决定记录 |
| 实现版本 / 适用项目 / 传输 | 本机版本或提交、项目、DoIP/DoCAN |
| 验证类别 / 环境 | 模拟/真机/视觉/性能/冻结；OS、依赖、设备、驱动、固件、DPI |
| 输入 / 操作或命令 / 预期 | 可复现步骤、报文/数据摘要及其来源 |
| 实际结果 / 证据位置 | 日志、抓包、报告、截图、测量值；敏感值脱敏 |
| 状态 / 限制 / 下一动作 | 通过/失败/未执行/材料阻塞；未覆盖边界 |

完成后将记录关联到测试覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）、需求状态和变更记录（本机资料：`local/history/version_change-before-publication.md`）。真实缺陷修复再登记 [bugfix_record.md](bugfix_record.md)，不补造原版历史。

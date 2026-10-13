# 线程、事件与资源生命周期

2026-10-12 响应显示沿用 DataReceivedEvent→主线程 DiagnosticController，不增加 worker 或 timer。Domain/App 检查无 IO；周期回调只解析有界基础字段（DTC 列表前 16 项），显示仅格式化前 171B，不在接收订阅里全量 hex。完整 bytes 共享不可变引用；显式复制/离线输入为用户操作。断开/项目/关闭清除显示并解绑订阅；原线程、代际与保活模型不变。见手动响应记录（本机资料：`local/specifications/manual-diagnostic.md`）。

2026-10-12 D08 架构全景（本机资料：`local/replication/architecture-panorama-2026-10-12.md`）进一步说明纯 TestEngineCore 与 Qt engine_shell、协议 daemon 接收、组合根装配和硬件延迟初始化的职责。它没有提供新增共享状态/取消/销毁声明，不能补齐具体线程退出证据；原 11 事件及本机新增第 12 项仍保持，不采用其“9 个事件”概括。

2026-10-11—12 诊断 MAIN 的实际实现：`doip-connect`/`doip-send`/`doip-receive`/`doip-close` 均为 daemon Thread；一个 socket 一个 reader，接收缓冲独占。生命周期锁保护代际/socket 引用/connected/worker 登记，持锁不做 IO 或事件分发；发送锁只串行化写操作。关闭接纳与线程登记使用同一生命周期锁，停止与 close-worker 登记原子完成；已关闭/停止的会话不再启动接收或发送 worker。最终 join 使用统一 2s 截止时间并检查全部所属线程和 socket，不仅检查一次快照。Core 信号带 generation 与源时间戳，经唯一 QObject 绑定槽 QueuedConnection 过滤后发布领域事件；半帧关闭的完整残留另经绑定槽作为 WARN LogEvent，不冒充完整报文。线程停止通过 Event、有限 socket timeout 和后台 shutdown/close；UI 关闭只提交取消，最终 join 在容器清理。新增同步属本机设计，非原版事实。

项目文件任务由一个 worker 操作候选 manager，Event 交付结果、owner poll 安装，失败保旧且拒绝重入。保活 worker 只使用启动时捕获的参数/generation/停止 Event，不读取 UI 或应用状态。日志 bytes 的完整转换在文件 worker；导出使用独立文件 worker/结果 Event，容器统一清理。状态事件追加为第 12 项，原 11 项保持。相关实际验证见 覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。下文尚未实现模块的目标约束继续保留。

更新日期：2026-10-02。状态：完整复刻约束；P1 已建立总线与日志线程基础验证，协议、刷写与硬件线程尚未实现。本文依据 D01 §7、D02 §5、D03 和 A-Q12—Q16、Q17、Q19—Q24；来源编号见资料索引（本机资料：`local/replication/README.md`）。来源中的线程名不代表本机已全部创建。

分层见[架构](architecture.md)，事件和 Port 见 API 契约（本机资料：`local/specifications/api-reference.md`），操作级超时与恢复见 UDS 工作流（本机资料：`local/specifications/uds-workflow.md`）。本文不替未决的电源、刷写和项目切换策略作决定，相关状态见决策记录（本机资料：`local/specifications/decisions.md`）。

## 1. 执行规则

- 工作线程统一使用 `threading.Thread(daemon=True)`；不替换为 QThread、线程池或 asyncio。
- UI 对象的创建、读取和更新只在 Qt 主线程。工作线程通过 Qt 信号、Adapter 和领域事件总线报告结果，不直接操作控件或弹窗。
- 一个 socket 对应一个接收线程。接收线程只做有界的接收、粘拆包、必要的协议处理和事件投递，不写磁盘、不运行阻塞业务、不渲染 UI。
- TCP 连接、`sendall`、`sendto` 在工作线程。调用发送 Port 的主线程只提交动作；返回布尔值和发送事件均不等于 ECU 已接受请求。
- 停止依靠运行标志、Event、超时、关闭资源和自然退出，不强杀 Python 线程。`daemon=True` 不替代资源清理。
- 跨线程 Qt 槽连接使用有明确 receiver 的绑定方法，不能把匿名 lambda／闭包作为主线程调度保障。纯 Python 工作线程没有 Qt 事件循环，不在其中创建期待自行触发的 QTimer。

以上来自 D01/D02 和 A-Q16。旧 D02 的“禁止共享 mutable”由下文同步白名单细化；旧材料的“publish O(1)”也不能解释为同步订阅者始终常数耗时。

## 2. 线程职责与资源所有者

| 执行位置 / 原版名字 | 所有者与工作 | 返回主线程 / 同步方式 | 退出和边界 |
| --- | --- | --- | --- |
| Qt 主线程 | QApplication、页面、事件订阅者、引擎调度和响应决策 | 消费领域事件；QTimer 调度和轮询完成结果 | 不等待慢 IO；停止相关 timer，解绑失效页面订阅 |
| `_connect_worker` | DoIPProtocol 建立 TCP、配置 socket | 连接信号经 Adapter 转 `ConnectionEvent` | 连接超时或取消后收尾；过期连接结果不可替换新会话 |
| `_send_worker` | DoIPProtocol 的实际 socket 写入 | TX 源头时间戳、发送/错误信号；`_send_lock` 串行化 | 发送失败按错误路径报告；避免旧 socket 的 worker 写入新连接 |
| `_receive_loop` | DoIPProtocol 的 TCP 读取与 DoIPReceiveBuffer | 完整报文和 UDS 事件；RX 时间戳在完整报文到达时保留 | 每连接独立；socket 超时、断开或运行标志退出 |
| `_tcp_receive_loop / _udp_receive_loop` | SocketManager 的池连接 | 各 socket 消息上报；发送另用 daemon worker 和 per-socket RLock | 一 socket 一接收线程；池结束统一关闭，MAIN 的共享归属须区分 |
| `_flash_worker` | FlashManager 三阶段步骤、诊断等待 | 进度/完成事件；结果容器＋Event 接收安全计算结果 | 停止时退出等待、释放本任务资源；失败后 post 策略待决 |
| CAN 接收线程 | ZLG/TOSUN Adapter 的 SDK FIFO 读取 | `CanMessageReceivedEvent`，随后 ISO-TP 流控／重组 | 按硬件 shutdown 收尾；初始化失败显式报告 |
| CAN 周期线程 | Adapter 周期发送、逐帧 E2E 保护 | 计数器锁；状态和错误上报 | 周期停止后自然退出；组切换/测试结束调用 stop_all |
| `isotp-tx` | IsoTpTransport 每次诊断发送的分帧和 FC 等待 | Condition 协调 FC | disconnect 时 notify_all 唤醒；并发重入的仲裁仍需核验 |
| `keep-alive` | engine_shell 独立保活循环 | `threading.Event.wait(interval)`；提交 `3E 80` 发送 | Event 可唤醒退出；暂停步骤调度不停止保活 |
| `block-writer` | transfer_data 的 `_BlockWriter`、目标文件句柄 | 有界队列传递块；写入错误与完成状态需回传 | 关闭/flush/失败/停止的精确顺序待完整实现材料；不能把已入队当成已落盘 |
| SSH / 外部命令 worker | 操作或对应 Adapter 的阻塞调用 | 结果容器＋Event，主线程定时轮询 | SSH 原版运行中不能取消；本地进程超时与线程停止分开处理 |
| 配置加载、文件解析、预读、网卡检测等 IO | 对应操作／服务持有任务及句柄 | 工作线程完成结果回主线程，主线程应用结果 | 原资料未完整给出全部 worker 名称与取消协议；实现时登记，不杜撰原版线程列表 |

表中末行的“工作线程 IO”是本机执行约束；不能据此声称已核对原版所有文件读取位置。特别是上传预读、日志落盘和写队列入队的实际线程仍需补充证据。（D01 §7、D02 §5、D03 §1/3—7、A-Q13/Q16/Q27）

## 3. 允许的共享协调

A-Q16 列出的四类共享状态限定如下，不能由某处用了锁就扩大为可任意共享对象。

| 机制 | 允许用途 | 归属约束 |
| --- | --- | --- |
| 结果容器＋`threading.Event` | 异步操作完成回传、安全计算结果交付 | worker 写完结果再 set；消费者确认完成后读取；结果属于一次任务，不跨执行轮次复用 |
| `threading.Condition` | ISO-TP FC 的等待与唤醒 | 流控状态在对应同步区域更新；断开通知全部等待者，不在持有同步锁时执行慢 IO |
| 有界块队列 | `_BlockWriter` 流式写盘和背压 | 消费者拥有文件写操作；生产者交付后不得修改仍被 memoryview 引用的底层数据 |
| 锁保护 E2E counter | 每帧保护时读取、递增及回填所需计数器状态 | 按 `(can_id, pdu)` 管理；切项目新引擎重置，周期停启不重置 |

发送另有 D02 明确规定的 `_send_lock` / per-socket RLock，用来串行化 socket 写入。运行标志、取消 Event、执行索引和代际计数器仅用于生命周期控制，不构成共享任意业务对象的例外。其他跨线程可变状态应先写清所有者、写入者、同步与退出规则。

`ExecutionContext`、测试状态和页面状态不能被任意 worker 同时修改。经结果容器回传后由对应控制线程应用；业务上下文作用域仍按接口及操作契约核对，不能靠全局字典绕过边界。

## 4. 总线调度与源头时间戳

Core Qt 信号 → 唯一负责桥接的 Adapter → `QtDomainEventBus.publish(event)` → 主线程订阅者。每个原生信号只桥接一次；`error_occurred` 归 ConnectionAdapter，避免重复日志与弹窗。（D02 §5.1）

- 非总线所属线程 publish：经 `_relay` Signal 排队到主线程，不在接收线程执行订阅者。
- 同线程 publish：直接分发，订阅者同步执行；总耗时包含订阅者耗时，不承诺 O(1)。
- 订阅者只作轻量状态推进或安排后续任务，慢解析、磁盘、网络、硬件等待不塞进订阅回调。
- `event.timestamp` 缺省来自 `time.time()`；已有 TX/RX 源头时间戳必须保留，不能替换成桥接或 UI 显示时间。
- DoIP `DataSentEvent.data` 是含 8B 头的完整 DoIP 帧，在 `sendall` 前发出；DoCAN 是未分帧的完整 UDS 请求。两者都记录发送开始，不能用来证明发送完成、ACK 或诊断成功。

固定 11 个事件的逐项映射只在 API 契约（本机资料：`local/specifications/api-reference.md`）维护。新增必须同时补事件、Signal(object)、映射、唯一桥接、订阅和完整性验证；不能重命名或移用旧事件表示新含义。

## 5. 36 连续块路径与背压

PC → ECU：接收线程收到完整 `76` → Adapter／总线排队 → 主线程 `handle_response` 判断是否推进 → 直接调用 `send_diagnostic_message` → `_send_worker` 在发送锁下写 socket。原资料的“同线程直发”只表示响应决策不绕回普通步骤调度；它不允许主线程 `sendall`。（A-Q16）

上传使用文件流和下一块预读，不能整文件加载；预读的具体执行线程和句柄所有权尚未完整导出。实现须满足主线程非阻塞及每个文件句柄明确归属，不能为缩短块间隔引入竞态。（D03 §6.1、A-Q13/Q19）

ECU → PC：块交给 `_BlockWriter` 有界队列，由写线程流式落盘。原版容量为 **256 块**，满时阻塞；因此入队仅在未满的常见路径轻量，不能无条件声称 O(1)／永不阻塞。块为 8MiB 时，仅排队载荷就可能约 2GiB，memoryview 不消除其对底层缓冲的持有。（A-Q13）

**未验证点：** 现有资料没有完整解释队列饱和时，哪一个生产线程阻塞、主线程如何保持可响应、取消如何解开阻塞。不得让 socket 接收线程承担满队列等待，也不能宣称现有“主线程回调＋阻塞 put”已经满足全部约束。实施前应核对入队调用链并确定符合本规范的交付方式，记录与原行为的差异；饱和、磁盘故障和停止必须纳入验证。

写入完成必须独立于收到末块或入队完成确认。MD5、37、完成报告与文件关闭的次序按相应流程契约；A-Q19 只确认 NRC78 超时关闭并删除不完整文件，不能扩成所有停止/异常都会如此清理。

## 6. 停止、重连和迟到结果

1. 停止新的步骤调度，设置本任务取消/运行状态；重置该执行的等待与定时器。
2. 以单调 `exec_index`／代际编号使旧 timer、迟到响应、旧 worker 结果失效；检查当前所属任务后才应用结果。
3. 唤醒可唤醒等待者，关闭本任务拥有的 socket／文件／硬件句柄；等待线程自然退出。不得把“停止 UI 动画”视为后台结束。
4. 重连必须隔离旧 socket 与新 socket。原版重连前 `join(timeout=2.0)` 等旧接收线程，目的是防止旧异常处理器 disconnect 新连接；等待应位于后台，且有限 join 本身不能证明旧线程已经退出。（D03 §1.2）
5. 关闭是幂等资源操作。关闭串口不等于断电，结束刷写线程不等于 ECU 已恢复；这些用户可见恢复动作依决策记录（本机资料：`local/specifications/decisions.md`）处理。

上述是生命周期约束，不声明每个旧操作已实现完整取消。SSH 原版没有执行中取消；用户停止是否跑完整 post、刷写失败是否跑 post_flash、电源 PULSE 中途最终状态都仍待确认。（A-Q09/Q17/Q23/Q27）

暂停只挂起步骤调度，保活线程继续；迟到响应按执行索引过滤。OTA 有自己的重启代际与一次重启保护，不把普通断连规则套在其预期重启区间；详情见 UDS 工作流（本机资料：`local/specifications/uds-workflow.md`）。（A-Q17/Q20）

## 7. 项目切换与订阅清理

项目加载失败保留旧上下文。成功后 PageContext 重新注入端口并清理旧订阅，B 项目从全局基值重新计算覆盖，不能继承 A 的覆盖。（A-Q24）

原版未硬锁运行中切项目，旧任务依赖自身停止；这是已知行为，不能写成已经具备全局互斥。是否禁止运行时切换待决。在此之前，无关基础工作可继续，但切换实现须明确旧任务/端口/订阅的归属，不能让旧回调更新新项目页面。E2E 引擎切换会重置 counter，也须与旧周期任务分离。

## 8. 验证要求与尚缺证据

| 验证 | 必须观察的内容 | 关联 |
| --- | --- | --- |
| 信号线程与完整性 | 11 映射、唯一桥接、非主线程 publish 回主线程、同步订阅阻塞可被发现 | Q14—Q16 |
| 连接与发送 | connect True 只是受理；慢连接/慢发送不冻结 UI；两传输的 DataSent 内容和时间点 | Q14/Q16 |
| 重连与停止 | 旧接收线程、socket、timer、迟到回调不污染新代际；多次 close 无额外副作用 | Q12/Q16/Q17/Q20 |
| 大块与慢盘 | 时间戳、队列深度、内存峰值、饱和入队线程、UI 响应、停止解除阻塞、文件关闭 | Q13/Q16/Q19 |
| CAN 与 ISO-TP | FC Wait/断连唤醒、周期取消、E2E counter 并发和项目切换；真硬件分别回环 | Q12/Q21/Q22 |
| 保活与暂停 | 自动化保活独立；手动保活互斥；27 配对暂停；间隔变化下次启动生效 | Q17/Q26 |
| 进程与文件 | SSH/local command/TShark 超时、退出和结果丢弃；日志刷新与文件句柄释放 | Q27—Q30 |

原 FOTA 连续 36 间隔 ≤10ms 是待验指标，须按带时间戳报文定义口径，不能凭调用路径直接判通过。长稳抓包应分别观察 TCP Zero Window 与 RST，不能用“4 小时无 RST”代替无 Zero Window 的证据。（A-Q30）

P1 已运行基础 pytest，覆盖 Qt 总线线程归属、晚到事件、日志线程和测试服务端的退出；协议／硬件压力测试尚未执行，见覆盖索引（本机资料：`local/history/test-coverage-before-publication.md`）。Qt 总线使用 QThread.currentThread() 仅查询 QObject 所属线程，没有创建 QThread 工作线程或改变 daemon 模型。

## 9 P1 本机新增同步设计

- [后台日志](../src/adapters/file_logging.py) 用容量 2048 的有界 Queue 交付 LogRecord。调用方入队后不再修改记录；唯一 daemon 消费者拥有文件打开、轮转、写入和关闭。closing／ready／stopped 使用 Event，error 只在 ready／stopped 建立同步后读取。满队列采用非阻塞拒收并明确 stderr 提示；此为本机内部骨架策略，原日志格式、通信与实时日志仍待恢复。
- 日志磁盘初始化／写入失败记录 error、提示并停止写线程。窗口启动失败或正常退出都会清理容器；drain 和有限 join 放在 Qt 事件循环结束后，不在页面回调中等待写盘。
- [FakeDoIPServer](../tests/fixtures/fake_doip_server.py) 仅测试显式创建，Condition 保护响应队列、接收快照及连接／错误状态，Event 和 socket 超时用于退出；worker 独占接收缓冲与网络 IO。这是测试专用同步设计，不向应用增加任意共享状态的通行规则。
- 主 JSON 配置工具同步且由调用者串行持有，返回副本；P1 UI 未调用其文件 IO 或项目切换。后续接入 UI 时须在 worker 预读并经主线程应用结果，不能把同一 manager 交给两线程同时改。

2026-10-03 UI 演示没有新增工作线程或网络 IO。指令/配置草稿仅主线程拥有；演示预览使用现有 LogEvent(INFO)，不伪造连接/发送/接收事件。通信日志表在事件回调里仅转换前 171 字节为最多 512 字符，避免先格式化完整大载荷；完整 bytes 由不可变事件持有，用户复制时才转换。文本导入/导出/日志保存当前仅粘贴与复制，无磁盘 IO；大日志全文导出性能尚未验收，未来文件导出接入必须迁往 Port/工作线程。页面 timer、toast timer/动画和所有子对话框由窗口关闭时停止/关闭，随后取消订阅，再由容器在事件循环结束后排空日志。

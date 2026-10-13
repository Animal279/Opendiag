# 测试覆盖索引

2026-10-13 测试／预览从 `examples/projects/LoopbackDemo/config.json` 读取独立合成数据，不依赖被忽略的真实项目。整理前完整验证记录在 `local/history/test-coverage-before-publication.md`。

本轮完整回归实际 **291 passed in 8.93s**。仅含公开暂存文件的独立目录再次执行完整回归，实际 **291 passed in 9.45s**；没有本机资料或真实项目配置，仍复用本机已安装依赖的 Python 解释器，不代表公司 PC 环境已安装。

原时序用例 `test_peer_fragmentation_and_success_then_close_same_delivery` 在初次全量与单测重复中均观察到失败：服务端停止后，客户端尚未读到 EOF，`qtbot.waitUntil` 提前处理 RA。增加直接信号设置的 Event，先等客户端关闭，再处理 Qt 回调；同一用例连续 10 次通过，不改协议或会话实现。另将预览子进程改用当前 `sys.executable`，独立取码无需依赖源仓库的 venv 路径。

| 测试目录 | 覆盖 |
| --- | --- |
| [domain](../../tests/domain/) | 设置、hex／DoIP、事件 |
| [core](../../tests/core/) | 应用根、配置与接收缓冲 |
| [adapters](../../tests/adapters/) | 项目异步加载／保存、事件桥、日志与导出 |
| [application](../../tests/application/) | RA／手动会话与响应检查 |
| [integration](../../tests/integration/) | 显式 loopback TCP、完整 UI TX／RX、日志与释放 |
| [ui](../../tests/ui/) | 控件、配置 guard、演示、响应、预览和关闭 |
| [regression](../../tests/regression/) | import 白名单与版本来源 |

上传前另验证暂存树、来源迁移大小／SHA-256、公开文件独立目录的完整回归及普通／演示 smoke、文档链接和 Git 空白。模拟不代替 ECU、SDK／接线、安全算法、完整视觉／DPI、性能或冻结包验收。Q01—Q32 与完整 F01—F21 状态在本机继续维护，不因上传而关闭。

本轮普通／演示 smoke 均退出码 0，六页、`hardware_initialized=false`。暂存树为 111 个公开文件，12 项原始来源哈希一致；文档本地链接及暂存空白检查通过，私有路径／已知项目标识与凭证模式未见匹配。扫描结果只表示本轮检查范围，不替代真实资产的来源或授权。

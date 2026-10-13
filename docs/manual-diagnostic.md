# UDS 手动诊断操作

当前接线范围为诊断 MAIN 的 DoIP TCP／路由激活与 UDS 手动收发。独立 socket／UDP、DoCAN、刷写、安全与自动化仍待实现；普通启动不自动连接或选择模拟器。

1. 本机准备 `config/<项目>/config.json`，启动 `main.py` 后点击“项目…”加载。公开虚构样例见 [examples](../examples/README.md)。
2. 在“连接配置”核对地址、逻辑地址、版本、RA 和超时。应用影响下次连接快照，保存异步写本机 JSON；连接／释放期间配置锁定。
3. 点击“连接”。完整 RA 响应结果码为 `0x10` 才显示已激活；失败原因保留在状态栏和日志。释放完成后可修改或重连。
4. 输入合法 UDS hex，点击发送或 Ctrl+Enter。完整 TX／RX 保留；“UDS 响应”显示服务、NRC、标识、DTC 状态和有效会话响应声明的时序。时序只读，不改变客户端等待。
5. “报文解析”可离线检查 UDS 或完整 DoIP 诊断帧，显式选择输入类型，不发送请求。需要时启用保持会话；断开或关闭停止其线程。
6. “保存日志”异步导出当前界面快照，完整文件日志在 `logs/`。现场日志和截图只留本机。

本机验证使用显式 loopback 服务端，见[测试覆盖](test-coverage/README.md)。实际项目参数和详细历史记录在 `local/specifications/manual-diagnostic.md`，不随克隆取得；ECU、DPI、性能和冻结包仍待实测。

# 公开虚构样例

[LoopbackDemo/config.json](projects/LoopbackDemo/config.json) 是独立构造的 DoIP 样例，使用 `127.0.0.1` 和通用演示逻辑地址，不含真实项目名称、网段、凭证或安全算法，不代表原完整项目。

测试创建临时项目并显式启动预置应答的 FakeDoIPServer。普通启动不加载样例、不启动模拟器，也不会在连接失败时切换到它。

需要在界面检查加载时，可手动复制到本机 `config/LoopbackDemo/config.json`。真实 ECU 操作应准备实际配置，公开样例不能作为真实项目参数。

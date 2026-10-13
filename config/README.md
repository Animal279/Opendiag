# 本机项目配置

应用枚举 `config/<项目>/config.json`。真实配置、插件、DBC、安全算法和密钥只留本机；本目录除这份说明外均被 Git 忽略。

公开虚构样例见 [LoopbackDemo](../examples/projects/LoopbackDemo/config.json)。手动复制到 `config/LoopbackDemo/config.json` 后可检查项目加载；其 loopback 地址不会连接公司 ECU，也不会自动启动模拟器。

真实参数来自项目资料或明确提供的配置。跨项目切换不继承旧覆盖值，保存保留未知键和 `_comment_*`。凭证通过既定环境变量或本机配置提供，不写入公开说明或提交。

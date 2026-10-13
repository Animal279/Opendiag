# OpenDiag

Windows 桌面 ECU 诊断工具的重建工程，目标覆盖 DoIP／DoCAN、UDS、自动化、刷写、OTA、CAN／E2E、安全插件、电源和报告。目标版本 v3.8.37；当前运行版本 `3.8.37.dev0`，尚未正式发布。

已实现项目加载、DoIP 主连接与路由激活、UDS 手动收发、基础响应解析、后台日志和六页界面。本机验证使用显式 loopback 服务端；真实 ECU、SDK、完整视觉、性能及冻结包仍待验收。DoIP 手动独立 socket／UDP 和其余执行器尚未接线。

## 目录

| 路径 | 用途 | 是否上传 |
| --- | --- | --- |
| `main.py`、`pyproject.toml` | 入口、依赖和包元数据 | 是 |
| `src/` | Domain、Ports、Core、Adapters、Application、UI、Security 七层源码 | 是 |
| `tests/`、`tools/` | 测试与本机预览工具 | 是 |
| `examples/` | 独立虚构配置 | 是 |
| `docs/`、`requirements/` | 通用说明和依赖快照 | 是 |
| `config/`、`testcase/` | 实际项目配置／测试数据；配置目录仅说明文件公开 | 否 |
| `local/` | 原始资料、证据、项目规格、答复和历史备份 | 否 |
| `venv/`、`logs/` | 本机环境和运行产物 | 否 |

原始 DOCX 和历史问题的原字节保留在 `local/reference-documents/`。详细资料不随公开克隆分发；目录和上传边界见[资料与上传约定](docs/publication.md)。

## 启动

使用 Windows 10/11 x64 与 Python 3.12.10 x64，直接调用项目环境：

```powershell
venv\Scripts\python.exe main.py
venv\Scripts\python.exe main.py --ui-demo
venv\Scripts\python.exe main.py --smoke-test
venv\Scripts\python.exe -m pytest -q
```

普通启动保持未加载／未连接，真实配置须在本机准备。`--ui-demo` 只预览界面和请求，不连接网络／硬件或生成 ECU 应答。公开样例使用 loopback 地址，没有自动启动或切换模拟器的行为。

新电脑取码与环境安装见[GitHub 同步与公司 PC](docs/github-sync.md)，诊断操作见[手动说明](docs/manual-diagnostic.md)。

## 开发入口

- [协作约定](AGENTS.md)与[文档导航](docs/README.md)
- [架构](docs/architecture.md)、[线程与事件](docs/thread-model.md)
- [DS-01](docs/ui-design-system.md)与[界面规格](docs/ui-specification.md)
- [测试覆盖](docs/test-coverage/README.md)、[环境](docs/environment.md)、[未发布变更](docs/version_change.md)

公开说明中的项目代号已匿名化。缺少本机资料时，不能推断 ECU 参数、安全算法或未确认行为；完整复刻范围不因资料未上传而缩减。

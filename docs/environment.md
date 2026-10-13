# 环境与构建基线

本文记录 D04/D05 与 A-Q30/Q31 的环境资料和本机验证边界。2026-10-02 已确认 `E:\Python\python.exe` 为 Python 3.12.10 x64，并创建项目 `venv/`、按下表版本安装运行与测试依赖，`pip check` 通过。cx_Freeze 构建环境、SDK、驱动和真实硬件兼容性尚未验证；环境可安装不等于全部业务可用。

## 1 运行基线

| 项目 | 目标／来源描述 |
| --- | --- |
| 系统 | Windows 10/11 x64 |
| Python | 3.12.10 x64；主进程不可用 32 位解释器 |
| 应用标识 | opendiag；复刻目标 v3.8.37 |
| GUI | PySide6，Fusion 亮色，禁止混用 PyQt5 |
| 构建 | cx_Freeze，目录形式免安装包和 ZIP |
| 测试 | pytest、pytest-qt、pytest-cov；按项目 venv 执行 |

旧 `requires-python >=3.7`、包版本 3.8.0 和 doip-tool 3.1.0 是来源中已澄清的历史残留，不作为新工程的兼容承诺。

## 2 直接依赖参考

以下直接依赖取自资料，运行／开发项已在本机解析安装。声明见 [pyproject.toml](../pyproject.toml)，实际解析快照见 [Windows Python 3.12 开发依赖](../requirements/windows-py312-dev.txt)，快照包含相应传递依赖，未包含构建 extra。它适用于本次 Windows x64 环境，不是所有平台的统一锁。

| 分组 | 包 | 原环境版本 | 用途 |
| --- | --- | --- | --- |
| 运行 | PySide6 | 6.11.1 | Qt GUI |
| 运行 | PyYAML | 6.0.3 | 测试脚本 |
| 运行 | openpyxl | 3.1.5 | xlsx DTC 表 |
| 运行 | xlrd | 2.0.2 | xls 后备 |
| 运行 | pyserial | 3.5 | Modbus 串口 |
| 运行 | cantools | 42.0.1 | DBC |
| 运行 | paramiko | 5.0.0 | SSH／SFTP |
| 开发 | pytest | 9.0.3 | 测试 |
| 开发 | pytest-qt | 4.5.0 | Qt 测试 |
| 开发 | pytest-cov | 7.1.0 | 覆盖率 |
| 构建 | cx_Freeze | 8.6.4 | Windows 冻结 |

PySide6_Addons、PySide6_Essentials、shiboken6 的原快照均为 6.11.1，应与 PySide6 保持匹配。cryptography、PyNaCl、bcrypt 等由实际依赖解析和项目安全模块需求确认；pycryptodome 虽在快照中，不自动成为纯 Python AES-CMAC 的必要依赖。

原电脑完整 freeze 保存于 原环境快照（本机资料：`local/replication/original-environment-freeze.txt`），包含 PyQt5、PyInstaller、文档转换工具及其他环境残留，**不能直接把整份快照当本项目安装清单**。快照只是 A 附录 A 的资料转录，无本机验证含义。

## 3 外部运行资源

| 资源 | 用途及来源描述 | 本机状态 |
| --- | --- | --- |
| ZLG x64 SDK | zlgcan.dll、kerneldlls、VC++2013 等依赖 | 未收到；需版本和 ABI |
| TSMaster x64 | TOSUN DLL、对应设备驱动，原版从注册表定位 | 未验证安装 |
| 项目安全 DLL | ADC 双 DLL、项目B DLL及其依赖 | 未收到；不凭原文件名判断可加载 |
| python312-32 | 仅用于 32 位安全 DLL 子进程桥 | 未收到；主应用仍 x64 |
| VC++2015—2022 x64 运行库 | 原资料要求的部分 DLL 前置 | 本轮未检查／安装 |
| CH340／继电器串口驱动 | 对应电源设备 | 未检查／安装 |
| Wireshark／TShark | 网卡报文录制 | 可选；未检查；实际抓包还需验证可用接口和采集组件 |
| DBC／DTC／E2E／用例／固件 | 四项目完整联调 | 见资源清单，尚未到齐 |
| 图标／QSS／更新说明 | 原界面与冻结资源 | 原素材未收到，本机仅有新的未发布记录 |

不安装硬件工具来弥补缺少 SDK 说明，也不把 DLL 存在等同于硬件回环成功。错误 126／193 的用户提示与释放路径需在实现后验证。

## 4 后续搭建步骤

目前已经完成目标解释器确认、虚拟环境、运行／测试依赖、入口、版本、最小窗口与基础测试。后续仍按以下顺序维护；其中全功能和冻结环境尚未完成：

1. 验证目标 Python 的确切版本和 64 位位数，创建根目录 `venv/`。
2. 用该 venv 安装已定义的运行／开发依赖；依赖解析失败时记录具体冲突，不静默升级技术基线。
3. 核对导入路径与包发现，建立 pytest 配置、session 级 QApplication 和 FakeDoIPServer。
4. 验证未连接硬件也能打开最小主窗口、配置加载和日志路径；随后逐模块实现。
5. 根据实际成功解析与运行结果生成可复现依赖清单，注明解释器、平台、SDK／驱动和验证日期。

已可执行的源码与测试命令：

```powershell
venv\Scripts\python.exe -m pip install -e ".[dev]"
venv\Scripts\python.exe -m pytest tests/ -v
venv\Scripts\python.exe main.py
venv\Scripts\python.exe main.py --smoke-test
```

新环境先由 Python 3.12.10 x64 创建 venv，再安装本机依赖快照和上述 editable 项目。冻结阶段才安装 `.[build]` 并建立／运行 `build/build_release.py`；当前没有该脚本，也未执行 cx_Freeze。

不复建原电脑不存在的 `config/demo.json` 作为无声错误来源；启动默认值与项目覆盖按配置规范设计。

## 5 路径与凭证

`DOIP_APP_DIR` 用于应用数据根目录解析；应用根、进程 cwd 和冻结 exe 目录在实现时须明确，并测试从其他工作目录启动。不要在代码中硬编码任一电脑路径。

SSH 凭证通过 `DOIP_SSH_USERNAME`／`DOIP_SSH_PASSWORD` 优先注入；项目允许的文件字段作为回退。真实密码、私钥、keyMat 等不进入通用文档、日志和提交；本轮没有索取或写入这些值。

## 6 冻结与发布目标

构建脚本未来负责：读取运行版本；生成临时 cx_Freeze 配置；冻结；按明确清单补 DLL；审计七个源子包、延迟导入、图标、DBC 加载、安全桥及厂商 DLL；启动冒烟；压缩并清理临时配置。

随包资源按适用项目核对 `src/`、`config/`、`testcase/`、`libs/`、32 位桥及用户更新说明。原资料中的“build_release.py 566 行”只是原工程描述，不要求通过凑行数复刻。

产物目标为 `OpenDiag.exe`、`OpenDiag_<版本>/` 和对应 ZIP。默认分支及分支后缀见 [分支规范](branching.md)。当前没有构建脚本或产物，不编造安装包链接。

冻结验收不仅是进程存活 5 秒，还包括首页渲染、延迟页、连接设置、YAML 加载、报告生成和适用 DLL 加载；对应证据见 [测试规范](testing.md)。配置迁移与回滚需保留用户现场数据，不用整包覆盖替代配置兼容验证。

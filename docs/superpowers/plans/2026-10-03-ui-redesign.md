# OpenDiag UI 设计系统与界面重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 先建立可扩展的 UI 规范，再按同一设计系统重设计现有六页与弹窗。

**Architecture:** 保留 PySide6 四区布局与现有 PageContext/事件边界。主题集中定义 token，公共 UI 控件实现寻址分段和 bool 开关，页面只接入视觉公共接口；不增加诊断或硬件业务。

**Tech Stack:** Windows 10/11 x64、Python 3.12.10、PySide6 6.11.1、pytest/pytest-qt。

**Spec:** [UI 设计系统 DS-01](../../ui-design-system.md)。

## Global Constraints

- 默认/最小窗口为 1440×860 / 1080×680；保留六页导航和四区布局。
- 颜色 `#263C50/#F2F5F7/#FFFFFF/#2458D5/#627488/#D8E1E8`；尺寸为 Qt 逻辑像素。
- 主线程 UI、daemon 模型、11 个既定事件及 import 白名单不改变。
- 真实硬件/项目/诊断仍未接入；无 IO、伪造响应或状态持久化。
- 用户明确要求“先文档，再动手修改”，文档保存后继续执行；不另加交付审批。
- 当前仓库未初始化 Git：先检查实际状态，不为视觉改动擅自初始化仓库、提交或创建工作树。

## Review Focus

- 鼠标/Space 和禁用状态：bool 开关在禁用时不得变化或发信号。
- 寻址切换：两项保持互斥；重复点当前项不重复发状态事件，新指令和请求仍携正确 bool。
- 大 hex 与编辑：字体/列显示变化不能丢失原始 bytes 或改变日志完整复制。
- 最小窗口/折叠导航：主操作和参数不相互覆盖，页面可切换，弹窗底部操作可见。
- 关闭/晚到结果：新控件不创建 worker/timer，已有全部弹窗与 toast 收尾规则保持。

---

### Task 1: 先固定规则与扩展入口

**Files:** Create `docs/ui-design-system.md`；Modify `docs/README.md`、`AGENTS.md`、`docs/decisions.md`、`docs/ui-specification.md`。

**Interfaces:** 规范定义 `COLORS/SPACE/METRICS`、`data_font(size=13)`、`apply_table_style(table, data_columns=())`、`AddressingSelector.functional_button` 和 `ToggleSwitch`。

- [x] 写 DS-01 的布局、token、字体、密度、角色、状态、键盘/错误和新增页面流程。
- [x] 文档导航/协作约定链接规范，D-10 登记本次用户指令；保留原截图事实与当前新设计的区分。
- [x] 检查本地链接与规则内部一致性；没有代码变更前不写测试通过记录。

### Task 2: 公共主题与两类交互控件

**Files:** Modify `src/ui/theme.py`；Create `src/ui/controls.py`、`tests/ui/test_design_controls.py`。

**Interfaces:** `data_font(size: int = 13) -> QFont`；`apply_table_style(table: QTableWidget, data_columns: tuple[int, ...] = ()) -> None`；`AddressingSelector.functional_button` 是 checkable QPushButton，`physical_button` 与之互斥；`ToggleSwitch` 继承 QAbstractButton，保留 `toggled(bool)/isChecked()/setChecked()/click()`。

- [x] 先验证分段/开关的鼠标、Space、禁用、互斥和重复动作状态测试出现预期失败。
- [x] 实现只读 token、集中 QSS/图标、数据字体 delegate、两个公共控件。
- [x] 执行 `venv\Scripts\python.exe -m pytest -q tests/ui/test_design_controls.py`；确认状态契约与可访问名称。

### Task 3: 主窗口和指令/日志区

**Files:** Modify `src/ui/main_window.py`、`src/ui/command_editor.py`、`src/app_setup.py`；extend `tests/ui/test_ui_demo.py` 如有交互新边界。

**Interfaces:** 保持 `preview_requested(bytes,bool)`、PageContext、已有事件语义；`addressing_button` 指向公共分段中的功能按钮以保持已有 bool 查询。

- [x] 应用深侧栏、固定连接条、按钮分组、数据字体、32px 表格密度与统一焦点。
- [x] 接入寻址分段和会话开关，保留默认/禁用/预览和日志边界。
- [x] 执行 `tests/ui/test_ui_demo.py`、现有窗口/启动清理、架构守门检查。

### Task 4: 五个次页与配置/文本弹窗

**Files:** Modify `src/ui/workspace_pages.py`、`src/ui/config_dialogs.py`、`tools/render_ui_preview.py`。

**Interfaces:** 沿用 `create_workspace_page(index,parent=None)`、配置 `.values` 与非阻塞 `.open()`，不修改原参数契约。

- [x] 使用公共字体/尺寸/表格接口；参数组对齐，弱化重复卡片，保留未接业务的禁用态。
- [x] 渲染工具允许命名独立输出目录，加载微软雅黑与 Consolas 做 offscreen 预览，不覆盖 S01。
- [x] 执行次页/弹窗测试，检查全部页面最小尺寸和长字段，不增加无意义的色值镜像测试。

### Task 5: 回归、视觉审查与交付记录

**Files:** Modify `docs/test-coverage/README.md`、`docs/version_change.md`、README；Generate `local/evidence/ds-01/*.png`。

- [x] 全量 `venv\Scripts\python.exe -m pytest -q` 与普通/演示烟测。
- [x] 渲染并查看主界面、全部页、最小窗口、折叠侧栏、配置弹窗、开关/错误状态；新预览与原资料分别保存。
- [x] 独立审查可用性、状态/IO边界、token复用与生命周期，修复实际问题并验证。
- [x] 更新文档/测试/变更；真实 Windows DPI、原完整视觉、硬件和冻结包未验证项明确保留。

## 本机执行证据

DS-01 与本计划先于本轮代码保存。公共交互七项先验证缺失 API 的预期失败，再实现通过；实际布局、折叠导航可访问名称和预览失败退出补充三项回归。最终全量 `pytest -q` 为 132 passed（4.14s）；普通及演示烟测均加载六页并报告 `hardware_initialized=false`。

独立复核发现的折叠导航名称缺失和最后一张截图保存失败的退出问题已修复，并分别以 QAccessible 树、子进程故障注入再次验证。最小窗口的中部内容滚动及日志完整数据行亦已检查。新预览共 21 张保存在 `local/evidence/ds-01/` 并逐张查看，原 S01 与旧预览保留。

颜色检查新增灰底文字和深侧栏焦点两个集中 token，11 组实际前景/背景计算达到规定目标：普通文字最低 4.58:1，侧栏焦点对选中背景 4.00:1。本机界面演示已启动；未进行真实 ECU、完整原版视觉、Windows DPI 和冻结包验收。


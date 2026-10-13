# OpenDiag 缺陷修复记录

本文件只登记本机实现中实际完成并验证的修复。以下条目来自本机 P1 和 UI 初始实现的代码复核，不是原工程的发布缺陷历史。

原版路由激活校验、错误枚举等问题是收到的资料描述，见 答复状态（本机资料：`local/replication/answer-status.md`） 和 决策记录（本机资料：`local/specifications/decisions.md`）。本轮修正文档口径不等于已经修复原版或本机软件。

## 2026-10-02 · 3.8.37.dev0

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-001；F18/Q24/Q25 | 配置继承默认／全局值后 save 写整个有效视图，将继承值固化为项目覆盖；以后全局变化不再生效 | [ConfigManager](../src/core/config_manager.py) 分离项目原文档和有效视图，只保存原键及显式修改，保留明确同值覆盖 | [配置回归](../tests/core/test_config_manager.py) 新增 5 项，含继承不落盘、同值覆盖、稀疏子键和失败事务；tests/core 全 39 项通过 |
| BF-002；F17/F21 | 窗口创建／显示在资源清理 try/finally 之前，启动异常会留下日志线程 | [启动初始化](../src/app_setup.py) 将全部窗口启动纳入清理，关闭窗口异常也保证容器 shutdown | [启动失败回归](../tests/ui/test_startup_cleanup.py) 注入 create/show 两种错误，验证日志线程退出，两项通过 |
| BF-003；F19/F21 | RotatingFileHandler 内部处理磁盘写异常，外层未获得错误，error 留空 | [后台日志](../src/adapters/file_logging.py) 将写盘异常传到拥有者，记录错误、提示并关闭写线程和文件 | [日志回归](../tests/adapters/test_file_logging.py) 注入磁盘写失败并验证 error/停止/关闭；该文件三项通过 |

修复后执行 `venv\Scripts\python.exe -m pytest -q`：69 passed；`main.py --smoke-test` 通过。上述验证为本机基础与错误注入，不涉及真实 ECU、硬件、原视觉或冻结包。

## 2026-10-03 · 3.8.37.dev0 UI 复核

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-004；F17/F21/Q16 | 打开指令导入/导出或日志文本弹窗后关闭主窗口，子组件创建的对话框未在主窗口登记集合内，仍保持可见，可能阻止进程结束 | [主窗口](../src/ui/main_window.py) 关闭时遍历全部所属 QDialog 并 reject，同时停止加载/toast timer/动画及取消日志订阅；弹窗退出后删除 | [UI 演示回归](../tests/ui/test_ui_demo.py) 中 `test_window_close_releases_timers_animation_all_child_dialogs_and_late_logs` 同时打开八类弹窗，等待实际销毁、检查计时器/动画停止、晚到日志被忽略及日志线程退出 |
| BF-005；F19/F21/Q13/Q16/Q28 | 日志表把完整大 payload 转为 hex 后再截短，事件订阅回调仍为短预览分配大量文本 | [通信日志](../src/ui/main_window.py) 先截取前 171 字节再转换，至多 512 个 hex 展示字符，省略标记单独追加；完整 bytes 继续保存供显式复制/导出 | 同一[回归文件](../tests/ui/test_ui_demo.py) 以 1MiB bytes 和禁止调用完整 `.hex()` 的守卫验证展示长度、原 bytes 保留、复制/文本导出完整性及源时间戳；未测真实吞吐或长稳性能 |

修复后执行 `venv\Scripts\python.exe -m pytest -q`：122 passed（其中 UI 演示回归 19 项）；默认和 `--ui-demo` 的 `main.py --smoke-test` 均通过。offscreen 预览仅检查本机布局，不替代真实 ECU、Windows DPI、原视觉或冻结包验收。

## 2026-10-03 · 3.8.37.dev0 DS-01 复核

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-006；F17/F19/F21/Q02/Q28 | 1080×680 首页出现 hex 错误时，输入/工具条占用增大，日志仅能显示半行；次页中部内容压缩后参数/表格裁切 | [主窗口](../src/ui/main_window.py) 日志最小高度 192、通信区内边距 8；[指令表](../src/ui/command_editor.py) 最小高度 96；[次页](../src/ui/workspace_pages.py) 自动化/DoIP 手动中部滚动、页头/底部操作固定，payload 保持可读高度 | [设计回归](../tests/ui/test_design_controls.py) 的 `test_minimum_window_keeps_error_actions_and_complete_data_rows_visible` 检查首页错误状态主操作不被祖先裁切、两张表保留完整数据行；五个次页另经独立几何检查和最小尺寸预览目视审查 |
| BF-007；F17/F21/Q02 | 折叠导航把显示文字置空，可访问树中的导航项名称随之为空 | [导航](../src/ui/main_window.py) 为条目设置 `AccessibleTextRole`，折叠仍保留六页名称 | 同一[设计回归](../tests/ui/test_design_controls.py) 的 `test_collapsed_navigation_retains_names_in_qt_accessibility_tree` 使用实际 QAccessible 接口检查六个名称；未验真实 Windows 屏幕阅读器 |
| BF-008；F17/F19/F21/Q16 | 最后生成普通启动截图时若保存失败，该新增窗口不在原演示窗口收尾路径，事件循环可能继续等待，后台日志资源也不能退出 | [渲染工具](../tools/render_ui_preview.py) 追踪普通/演示窗口，finally 统一关闭并退出事件循环，报告失败；容器随后 shutdown | [故障回归](../tests/ui/test_preview_rendering.py) 的 `test_final_preview_save_failure_closes_windows_and_logging_thread` 在 subprocess 注入最终保存失败，验证退出码 1、全部窗口关闭、日志线程停止；独立故障复核另确认 handler 解绑 |

本轮最终全量测试 **132 passed in 4.17s**；普通/演示烟测均退出码 0、6 页、硬件未初始化。上述是本机 Qt offscreen 和故障注入结果，不证明真实 Windows DPI、原完整视觉、真实设备或冻结包通过。

## 2026-10-11 · 3.8.37.dev0

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-009；F02/F17/F21 | Ctrl 修饰键有效时，上移通过 selectRow 累加旧行与目标行选中；随后的下移因两行选中被拒绝 | [指令编辑器](../src/ui/command_editor.py) 使用 ClearAndSelect/Rows 明确把当前选中替换为移动后的单行 | [手动 UI 回归](../tests/ui/test_manual_diagnostic.py) 的 test_move_preserves_single_selection_while_control_is_held 已观察 RED（两行）→GREEN（单行），全量 240 passed in 7.52s；未涉及 ECU/视觉验收 |
| BF-010；F17/F18/F21 | 异步保存期间取消配置弹窗，Qt 已删除弹窗后控制器仍访问 isVisible，导致 RuntimeError | [诊断控制器](../src/ui/diagnostic_controller.py) 在 finished 时清除保存弹窗引用，文件任务完成后只安装有效结果，不访问已销毁 QObject | 同一[手动 UI 回归](../tests/ui/test_manual_diagnostic.py) 的 test_cancel_save_dialog_during_worker_does_not_use_destroyed_qobject 已观察 RED（Internal C++ object already deleted）→GREEN；2026-10-12 全量复查 244 passed in 8.00s |

## 2026-10-12 · 3.8.37.dev0 手动诊断审查

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-011；F01/F21/Q16 | connect worker 已确认 active，但 shutdown 获取线程快照后才登记接收 worker；遗漏 join 导致错误报告清理失败 | [DoIPProtocol](../src/core/doip_protocol.py) 同一生命周期锁管理关闭接纳与线程登记；停止与 close-worker 登记原子完成；关闭后不接纳接收/发送线程，最终用统一 2s 截止等待全部所属线程/socket | [传输回归](../tests/integration/test_doip_transport.py) 的 test_shutdown_cannot_start_receiver_after_join_snapshot 用 Event/受控 join 确定性交错，RED（workers did not stop）→GREEN，验证无迟到 reader、socket 关闭 |
| BF-012；F19/F21/Q16/Q28 | 半帧 EOF 仅留下前 171B 的错误文本，LogEvent.data=None，异常尾部无法复制或落盘 | [Core](../src/core/doip_protocol.py) 传递完整残留 bytes 与源时间；[唯一桥](../src/adapters/doip_adapter.py) 单独发 WARN/未完成帧日志，不发布有效 UDS/RA | [日志集成](../tests/integration/test_diagnostic_logging.py) 的 test_incomplete_frame_keeps_all_bytes_in_log_without_uds_or_ra_success 输入 279B 半帧，RED（零条完整残留）→GREEN，验证全文入文件且无成功事件 |
| BF-013；F19/F21/Q28 | 原子替换失败后临时文件清理再次失败，异常越过 done.set，worker 已退出但 UI 永远等任务 | [日志导出](../src/adapters/log_export.py) 最内层 finally 必定置完成，原错误与清理错误同时保留；替换成功后无需再次清理 | [导出回归](../tests/adapters/test_log_export.py) 的 test_export_cleanup_failure_still_completes_and_preserves_both_errors 注入两次权限错误，RED（done 未置位）→GREEN，旧文件保持且两错误可见 |
| BF-014；F17/F19/Q28 | 导出期间新增日志调用 update_count，按行数重新启用保存；第二次选择路径被静默忽略 | [通信面板](../src/ui/main_window.py) 保存按钮同时检查导出任务；两个入口拒绝重入并提示等待，完成后恢复 | [UI 回归](../tests/ui/test_manual_diagnostic.py) 的 test_log_export_stays_locked_while_new_records_arrive 模拟持续 RX，RED（按钮重启）→GREEN，验证仅首次快照导出、无重入文件弹窗、完成显示路径 |

四项来自独立只读整体审查，分级 Important，经作者核对后统一修复；无 Critical/Minor。最终 `venv\Scripts\python.exe -m pytest -q`：**248 passed in 8.04s**。普通/演示 smoke 均退出码 0，重新生成的 6 张 offscreen 图已检查；没有真实 ECU/硬件、DPI、性能或冻结包验收。

## 2026-10-12 · 3.8.37.dev0 响应解析复核

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-015；F02/F17/Q07/Q26 | 50 响应长度正确但会话编号为保留值时，初版仅检查长度，错误地生成并覆盖有效时序 | [纯解析器](../src/domain/uds_response.py)验证标准 01—04、自定义 40—7E；保留/不支持值报错且不生成时序，UI 保留上次有效值 | [响应检查](../tests/application/test_response_inspection.py)的六个保留值和四个自定义边界、[实际 UI 链路](../tests/ui/test_uds_response_view.py)的错误不覆盖均 RED→GREEN |
| BF-016；F17/F21/Q02 | 1080×680 第三个页签只剩半行，详情最小尺寸按未继承 QSS 的字体/padding 测量；增高后底部复制/源时间越过父 tab 被裁切 | [响应视图](../src/ui/response_inspection.py)显示时按最终样式测量两行最小高度；时序/源时间和复制按钮置于紧凑 header，保证详情与操作的可见区域 | 同一[UI 回归](../tests/ui/test_uds_response_view.py)的 test_minimum_window_response_view_has_complete_text_lines 先验证 viewport，再验证重叠及父区域包含，观察 RED→GREEN；重生成最小窗口图目视检查，独立复核 4 项 UI 通过 |

最终全量 **291 passed in 9.06s**；普通/演示 smoke 均退出码 0、6 页、硬件未初始化。修复与验证均为本机，未声明公司 ECU、原视觉、真实 DPI、性能或冻结包通过。

## 2026-10-13 · 上传前测试整理

| ID / 关联 | 触发与根因 | 已完成修复 | 本机验证 |
| --- | --- | --- | --- |
| BF-017；F01/F21/Q16；测试同步缺陷 | 断连同批回调用例仅等待服务端停止，客户端可能尚未消费 EOF；等待 quiescent 时 Qt 提前处理 RA，违反测试预设时序，产生偶发失败 | [传输测试](../tests/integration/test_doip_transport.py)通过 DirectConnection 只设置 Event，先等客户端断连再泵 Qt 队列；保持原断言与生产代码 | 初次全量与重复单测均观察失败，修改后同一用例连续 10 次通过；完整回归 291 passed，独立公开目录 291 passed。属于测试同步修正，不声明生产协议缺陷或硬件验证 |

## 后续记录格式

每次实际修复记录日期、版本／提交、关联 F/Q、触发步骤与现象、根因、实际修改、验证命令及结果、剩余限制。涉及硬件时补设备、固件和接线条件；没有运行的测试明确写未运行及原因。

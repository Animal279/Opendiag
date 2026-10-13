# 工程文档导航

`docs/` 保存通用开发说明；原始证据和含项目参数的记录集中到本机 `local/`，不随 GitHub 克隆分发。公开文档中的项目代号已匿名化，原始材料未被覆盖。

| 文档 | 内容 |
| --- | --- |
| [架构](architecture.md)、[线程与事件](thread-model.md) | 七层白名单、装配、主线程和资源释放 |
| [需求](requirements.md)、[实施阶段](implementation-plan.md) | F01—F21 范围与后续验收；资料缺口不表示删除需求 |
| [DS-01](ui-design-system.md)、[界面规格](ui-specification.md) | 共用视觉与控件登记 |
| [手动诊断](manual-diagnostic.md) | 配置、连接、发送和只读解析 |
| [环境](environment.md) | Python、依赖及冻结环境 |
| [测试约定](testing.md)、[覆盖索引](test-coverage/README.md) | 实际验证及证据边界 |
| [同步与公司 PC](github-sync.md)、[资料与上传](publication.md) | 取码、目录、忽略和安全历史 |
| [分支](branching.md)、[变更](version_change.md)、[缺陷记录](bugfix_record.md) | 开发维护 |

有本机资料时继续阅读 `local/replication/README.md`、`answer-status.md`、`local/specifications/decisions.md` 及对应协议／配置／流程／接口规格。来源、Q01—Q32、D 决策编号和哈希均保留在本机。缺少资料时继续不依赖它们的工作，需要项目事实的任务应明确记录缺口。

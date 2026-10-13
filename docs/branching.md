# 本地开发与发布约定

本地工作主线沿用 `master`，远程为 [Animal279/Opendiag](https://github.com/Animal279/Opendiag)。2026-10-13 首次公开上传采用不含敏感资料的新历史；旧的两次本地提交只留在忽略的历史 bundle，见[上传边界](publication.md)。尚无发布包。

## 分支与提交

- 普通功能分支按实际工作命名；Codex 分支默认使用 `codex/` 前缀。不要为文档整理建立额外工作树。
- 提交说明用中文：`feat/fix/refactor/docs/test/chore: 简述`。
- 不覆盖用户未提交改动，不提交本机配置、日志、环境、原资料或安全资产。
- 文本 LF、Windows 脚本 CRLF、二进制原字节由 `.gitattributes` 管理。
- 只推送明确的安全分支；不使用 `--all`、`--mirror` 或强推发布旧备份。
- GitHub 默认分支 `main` 与公司取码分支 `master` 初次交付指向同一安全内容；未来开发沿用 `master`，同步默认分支时核对远端头，避免覆盖他人改动。

## 版本与发布

目标 v3.8.37；当前未发布 `3.8.37.dev0`，版本单一来源为 [src/version.py](../src/version.py)。包元数据动态读取，变更见[未发布记录](version_change.md)。

未来发布先核对实现范围、测试、线程／分层、真机／视觉／性能和冻结包，再由 cx_Freeze 构建。当前没有构建脚本或产物，不建立虚构发布 tag，也不把源码运行通过写成部署验收。

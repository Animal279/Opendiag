# GitHub 同步与公司 PC

2026-10-13 用户已授权排除敏感资料后上传其余文件，并要求先整理目录。目标仓库为 [Animal279/Opendiag](https://github.com/Animal279/Opendiag)，核对仍为公开状态。上传前旧本地历史已备份，采用安全新历史；范围见[资料与上传](publication.md)。首次上传结果在远程验证后登记。

## 两台电脑

开发电脑保存源码并提交；公司 PC 只克隆／拉取，不需要推送权限。真实配置、资料、SDK、安全资产、日志和环境只留本机，不随取码分发。公开合成样例与真实项目区分，现场参数通过获准的内部方式准备。

## 公司 PC 首次取码

使用可用的 Git 与 Python 3.12.10 x64：

```powershell
git clone --branch master https://github.com/Animal279/Opendiag.git OpenDiag
Set-Location OpenDiag
py -3.12 -c "import sys, struct; print(sys.version); print(struct.calcsize('P') * 8)"
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements/windows-py312-dev.txt
venv\Scripts\python.exe -m pip install -e ".[dev]"
venv\Scripts\python.exe -m pip check
venv\Scripts\python.exe main.py --smoke-test
venv\Scripts\python.exe main.py
```

直接调用 venv，无需激活脚本。源码读取成功不代表 PyPI 安装或公司 ECU 可用；公司网络、依赖源、SDK 和真实参数仍需现场检查。

普通启动会保持未加载。先在本机准备 `config/<项目>/config.json` 才能选择真实项目；样例操作见[手动诊断](manual-diagnostic.md)。不要把真实资产或公司数据补回公开提交。

## 后续更新

关闭应用，在公司 PC 仓库目录执行：

```powershell
git status --short
git pull --ff-only
```

先保存现场改动；冲突时不使用 `reset --hard` 或 `clean` 丢弃数据。依赖快照／pyproject 有变化时再安装依赖并执行 `pip check`。

本机 Git 的直连没有使用 Windows 系统代理；显式使用系统已有代理后读取远程成功。代理只用于当前操作，不写入工程文件或公共文档，也不改全局 Git 设置。GitHub 插件认证与本机 Git 写入认证独立；若通过已连接插件完成上传，不应宣称 Git Credential Manager 已登录。

公司 PC 的现场验证和任何需要回传的改动，仍通过公司允许的方式处理；本流程仅安排 GitHub 到公司 PC 的单向取码。

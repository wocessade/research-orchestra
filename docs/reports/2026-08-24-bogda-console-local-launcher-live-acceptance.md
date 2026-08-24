# Bogda Console 本地启动器真实验收

日期：2026-08-24

范围：Windows 本机 `127.0.0.1:3101` 的 `mock-all` Bogda Console。没有连接
Pi 或真实 Prefect，没有修改、停止或代理旧控制台 3100。

## 结果

- 手动启动的旧 3101 进程已退出，并切换为
  `bogda-console/scripts/local-console.ps1` 托管。
- 真实执行 `start → status → stop → start → status` 通过。
- `status` 最终为 `healthy`；能力接口返回 `profile=mock-all`，并允许修改科研
  自主模式。
- `stop` 后 3101 listener 消失；再次 `start` 后恢复。
- 整个停止与重启周期中，3100 listener 的归属未变化。
- 最终状态是 3101 继续运行，并由启动器的 `%LOCALAPPDATA%\BogdaConsole`
  状态文件管理。

PID 属于易失运行状态，不在本报告记录。

## 真实验收发现并修复的问题

1. PowerShell 7 在能力接口不可达时可能抛出没有 `Response` 属性的
   `TaskCanceledException`。StrictMode 下直接读取该属性会让 `start` 在启动前
   失败。修复为先检查异常对象是否存在该属性。
2. Windows venv 的 `python.exe` 会拉起基础解释器子进程；前者是启动进程，后者
   才拥有 3101 listener。启动就绪现在以 listener 与 `mock-all` 能力接口为准，
   随后记录真实 listener PID 和启动时间。
3. PowerShell 7 的 `ConvertFrom-Json` 会把 ISO 启动时间自动解析为 `DateTime`；
   默认字符串转换会丢失原格式，导致进程归属误判。状态读取现在统一恢复为
   round-trip ISO 格式，同时保持 PowerShell 5.1 兼容。

三个问题均先增加失败回归测试，再做最小修复。新增测试包含 PowerShell 7 的
真实只读探测和临时 dummy 进程，不会启停真实 3101。

## 边界

- 此验收只证明 Windows 本机 `mock-all` 启动器闭环可用。
- 它不证明真实 Prefect、Pi shadow、Power Agent、开机自启或 Windows 服务可用。
- 启动器仍不隐式安装依赖；`.venv` 或 `frontend/dist` 缺失时按 README 手动重建。

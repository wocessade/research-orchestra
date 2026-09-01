# Bogda runner handshake（线上已备，线下接 worker）

日期：2026-09-02  
适用：owner 在线下把 runner 拉起来之后，把 3101 接到**同一套文件**，而不是再写一层调度。

**不是 3100 切换。不是 Wake Bridge。不是把研究任务丢进现网 `pi-service`。**

现网 Orchestra 雷达已停，见 [`2026-09-02-orchestra-pre-runner-freeze.md`](2026-09-02-orchestra-pre-runner-freeze.md)。broker / exam-watch / backup 仍在。

## 已经在线上准备好的

- Gate 7 联合 work-pool 白名单（submit/cancel/review/checkpoint）
- 本机角色：`BOGDA_CONSOLE_ROLE` = owner | observer | operator
- 受控日志：`GET /api/v1/runs/{id}/logs`
- 产物清理：`POST /api/v1/runs/{id}/artifacts/cleanup`，确认词 `delete-content`（删 stdout/stderr，留 tombstone 与 events）
- >20 CNY 签发：`POST /api/v1/runs/{id}/approvals`；MAC 不回显；worker 用同一 SQLite `get_open` / `consume_open`
- usage-unknown：`BOGDA_USAGE_UNKNOWN_DB` 指向 worker 的同一库
- 峰谷 dispatcher 内核已测，**不**调用 Prefect

## 你接上 runner 之后要填的（值不入库）

3101 用 `allowlisted-test`。把 runner 的 **deployment / queue / work pool** 精确 ID 写进环境，禁止 `*`，禁止把生产 `pi-service` 填进研究白名单。

```
BOGDA_CONSOLE_PROFILE=allowlisted-test
BOGDA_CONSOLE_ROLE=owner
BOGDA_CONSOLE_ACTOR=local-owner
PREFECT_API_URL=http://10.77.0.1:4200/api
BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS=<runner-deployment-id>
BOGDA_CONSOLE_ALLOWED_QUEUE_IDS=<runner-queue-id>
BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES=<runner-pool-name>
```

共享文件（console 与 worker 必须是同一路径，建议 NAS）：

```
BOGDA_ARTIFACT_ROOT=<worker-artifact-root>
BOGDA_USAGE_UNKNOWN_DB=<worker-usage-unknown.sqlite>
BOGDA_APPROVAL_DB=<shared-approval.sqlite>
BOGDA_APPROVAL_HMAC_KEY=<32-byte-hex>
```

生成 HMAC（只在本机跑，不要提交、不要贴进聊天）：

```
python -c "import secrets; print(secrets.token_hex(32))"
```

模板见 `bogda-console/env.allowlisted-test.example`。

## 接上后怎么验收（短）

1. 3101 基础设施页能看到 runner 的 pool/queue/worker heartbeat。
2. 只读打开一条 runner 的 run：日志区能读 stdout/stderr（根目录对上才会存在）。
3. 需要 >20 CNY 时，运行详情签发凭证；worker 侧 `consume_open` 成功一次，重放失败。
4. 清理按钮只删内容，events.jsonl 还在。
5. **开放 checkpoint**：worker 真正挂起后才会出现裁决控件。没有 worker 就不要当作 DEF-03 已过。

## 仍不要做

- 改 3100 入口
- 研究 Flow 进 `pi-service`
- 未开口就删盒子上 S2 验收资源 `bogda-s2-acceptance-20260901-...`
- 把 HMAC、API key、Prefect auth 写进仓库或对话

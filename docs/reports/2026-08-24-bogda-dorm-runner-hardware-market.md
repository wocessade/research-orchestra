# Bogda 宿舍 Runner 硬件行情与采购决策

日期：2026-08-24

状态：当前市场快照；价格会变化，采购前应重新核价。

## 1. 结论

2026 年 8 月的内存、SSD、HDD 和消费级 GPU 均处于异常价格周期。Bogda 宿舍 runner 不应一次性购买高配整机。当前最合理的路径是先组装无独显、低内存的基础平台，复用 owner 已有 SSD；显卡、NAS 扩容盘和大容量内存延后采购。

推荐当前配置：二手 i5-8500、B360/H310、16GB DDR4、正规 500–550W 电源和普通机箱，先使用核显。目标总价约 1050–1550 元；若直接配置 32GB，约 1450–1950 元。Windows 10 作为宿舍机系统，不为游戏额外增加预算。

## 2. 已确定的使用条件

- owner 的笔记本需要在宿舍和实验室之间搬运，不能承担 7×24 常驻 runner。
- 宿舍 runner 允许 DIY，噪声不是硬约束，价格优先。
- owner 已有多块可用 SSD，本轮无需采购消费级 SSD。
- runner 要兼顾 Prefect worker、CPU 科研任务和普通游戏，但不得为了游戏提高预算。
- 需要大型 GPU 实验时优先向课题组借卡；本地 GPU 不注入 4B Broker，待第二阶段另行设计。
- Pi 继续承担常开 Broker/NAS；宿舍机可休眠，由后续 Wake Bridge 按需唤醒。

## 3. 市场异常

### 3.1 内存与 SSD

TrendForce 在 2026 年第一季度把传统 DRAM 合约价环比涨幅预测上调到 90%–95%，NAND Flash 上调到 55%–60%，主要原因是 AI 数据中心和企业 SSD 采购挤占产能。[TrendForce 供需报告](https://www.trendforce.com/presscenter/news/20260202-12911.html)

中国二手 16GB DDR4 模组已从 2026 年初超过 700 元的高点回落到约 450 元，但内存和存储仍显著高于一年前。主流 1TB SSD 零售价已从约 410 元升到 950–1000 元。[TrendForce 中国市场观察](https://www.trendforce.com/news/2026/07/21/news-china-memory-prices-show-early-signs-of-easing-second-hand-16gb-ddr4-reportedly-falls-over-30-from-peak/)

决策：现阶段只买满足启动需求的 16GB DDR4；若 owner 库存中已有 DDR4，则直接复用。不要购买消费级 SSD，不因担心继续涨价而囤货。

### 3.2 HDD

2026 年 8 月国内行情中，8TB 机械盘约 1600 元，大容量盘和二手企业盘也出现明显溢价。[8 月硬盘行情](https://post.smzdm.com/p/anvxpo3p/) 16TB 新盘报价分化严重，部分 NAS 型号每 TB 成本高于 8TB，当前 8TB 只是相对甜点位，并不代表价格合理。[容量价格比较](https://post.smzdm.com/p/az8xe2zn/)

决策：Pi 当前 `/mnt/nas` 的约 232GB SSD 足以支撑 Bogda 第一阶段和 72 小时 shadow 证据；本轮不扩 NAS，不买 HDD。真正需要容量时先清点 owner 的闲置 SSD，再重新核价。

### 3.3 GPU

RTX 5060 Ti 16GB 中国大陆建议零售价为 3599 元。[NVIDIA 首发定价](https://www.nvidia.cn/geforce/news/rtx-5060-desktop-family-laptop-5060-coming-soon/) 2026 年 8 月国内市场价格已约 4800–4900 元，较此前价格上涨超过 1000 元。[中国市场涨价情况](https://www.yicaiglobal.com/news/consumer-gpu-prices-in-china-jump-again-as-ai-boom-squeezes-supply)

RX 9060 XT 16GB 官方定价为 2899 元，但市场同样出现溢价；它适合游戏价格比较，却不能替代 Bogda 科研任务所需的 CUDA 软件兼容性。[AMD 官方定价](https://www.amd.com/zh-cn/newsroom/press-releases/2025-5-20-amd-introduces-new-radeon-graphics-cards-and-ryzen.html)

决策：宿舍 runner 第一阶段不买独显。后续优先观察来源可靠的二手 RTX 3060 12GB，采购阈值约 1500–1700 元；RTX 5060 Ti 16GB 只有回落到约 3600–3900 元才重新评估。阈值不是报价承诺，购买前必须检查实时成交价、保修、显存压力测试和矿卡风险。

## 4. 最低价基础配置

| 部件 | 当前建议 | 目标价格 |
|---|---|---:|
| CPU | 二手 i5-8500，6 核，带 UHD 630 | 250–300 元 |
| 主板 | 二手 B360/H310；优先 4 内存槽和标准供电接口 | 150–250 元 |
| 内存 | 先装 16GB DDR4；有库存则复用 | 350–450 元 |
| 电源 | 正规 500–550W，预留独显 8-pin | 200–300 元 |
| 机箱与散热 | 普通二手 ATX 机箱和基础塔式散热 | 150–250 元 |
| SSD | 使用 owner 库存 | 0 元 |
| GPU | 暂不购买，使用核显 | 0 元 |

二手八代平台行情中，i5-8500 约 280 元，是六核低价甜点；同代 i7 的价格、功耗和散热收益不适合本项目当前阶段。[二手八代平台参考](https://post.smzdm.com/p/a82r08l7/)

选择 OEM 准系统时必须核查电源、主板和机箱是否使用私有接口，以及是否有全高双槽 GPU 空间。若未来确定安装独显，标准 ATX DIY 平台通常比私有规格整机更容易升级。

## 5. 显卡路线

### 默认路线：暂不购买

先用核显完成 Windows 10、Bogda worker、休眠/唤醒和 CPU 任务验收。显卡不会阻塞第一阶段，也不应在当前溢价中提前购买。

### 通用低价路线：二手 RTX 3060 12GB

价格落入约 1500–1700 元、来源和压力测试可靠时再购买。它能兼顾 1080p 游戏、CUDA 小实验和 12GB 显存任务。超过阈值则继续等待或向组里借卡。

### 噪声不受限的特殊路线：Tesla P40 24GB

P40 的优势是低成本 24GB 显存；缺点是 Pascal 架构、无 Tensor Core、FP16 弱、被动散热、需要风道改造和特殊供电，而且没有视频输出，不能承担游戏显卡职责。[P40 二手价值与限制](https://siliconcomps.com/gpu/tesla-p40/)

只有在任务明确要求廉价 24GB 推理显存、且 owner 接受 DIY 风道与低效率时才重新评估。P40 不是宿舍 runner 的默认采购项。

## 6. 采购与复核规则

现在购买：CPU、主板、最低 16GB 内存、电源、机箱。

现在不买：SSD、HDD、RTX 5060 Ti、RTX 5070/5070 Ti、RTX 3090/4090/5090，以及仅为游戏准备的显卡。

采购前重新核查：

1. 至少比较新品含保修价、同城二手成交价和平台历史低价，不使用单个促销标题作为行情。
2. 内存运行 MemTest；SSD 检查 SMART、通电时间和写入量；GPU 检查显存压力、热点温度和拆修痕迹。
3. 电源优先可靠性，不购买来源不明或虚标型号。
4. 先验收无显卡基础平台的 Windows 10、休眠、远程恢复和 Bogda CPU worker，再决定 GPU。
5. 所有价格均为 2026-08-24 的决策阈值，不得在未来采购文档中当作固定报价。

## 7. 调研限制

本次原计划通过 Agent Reach 的 Exa 后端获取多源结果，但本机 Agent Reach 入口出现 `uv trampoline failed to canonicalize script path`，且 Exa MCP 未注册。因此改用实时网页搜索，优先采用 TrendForce、NVIDIA、AMD 等一手来源，并用中文市场文章补充零售快照。二手平台无法获得完整的已成交订单样本，二手价格只能作为谈价阈值，不能视为可立即成交的保证。

# ESP32-C3 Pro 每日天气挂件 — 设计

日期：2026-08-24  
状态：approved（实现中；含子集中文）

## 1. 目标

点亮一块带 **0.96" OLED** 的 **ESP32-C3 Pro**，用 **MicroPython** 拉取并显示 **南京** 当日/当前天气。  
屏显以**有限中文**为主（子集点阵字库，仅含用到的汉字），数字与单位可用 ASCII。  
v1 以「USB 插上就能跑」为准；省电深睡眠、全量中文字库、多城市、Orchestra 接入均不做。

## 2. 硬件与按键

| 部件 | 假定 |
|------|------|
| MCU | ESP32-C3 |
| 屏 | 0.96" OLED，I2C，多为 SSD1306，128×64 |
| 供电 | USB 常供电（先通再优化） |

### BOOT 与 RST（板载按键）

多数 ESP32-C3 开发板有两个键：

| 键 | 作用 |
|----|------|
| **RST** | 硬件复位：相当于重启芯片，重新跑 `boot.py` / `main.py`。日常「卡住了重启一下」用这个。 |
| **BOOT** | 主要管**启动模式**。上电或按 RST 的瞬间若按住 BOOT，芯片进入下载/烧录模式，方便用 esptool / Thonny / mpremote 刷固件或传文件。正常运行时不要按住它开机。 |

补充：

- 刷好 MicroPython 之后，日常开发多半只需 RST 重启；BOOT 只在「进不了下载」「要重刷固件」时用。
- 部分板子把 BOOT 接到某个 GPIO，固件里也可当普通按键用（例如「立刻刷新天气」）。**v1 不占用**；需要时再加。
- 具体「按住 BOOT + 点一下 RST」的组合以你板子说明书为准，逻辑都是：复位时采样 BOOT 决定是否进下载。

I2C 的 SDA/SCL GPIO 因厂家丝印而异，集中写在 `config.py`，烧录后不对就改引脚。

## 3. 架构

```
boot
  → 连接 WiFi（凭据仅存 secrets.py）
  → OLED 显示 Connecting...
  → HTTPS 请求 Open-Meteo（南京 lat/lon）
  → 解析 temperature / weather_code / humidity
  → 中文子集 + ASCII 绘制到 OLED
  → 每隔 N 分钟重复（默认 20）
```

失败时屏显短错误并重试，进程不退出空转。

独立工程，**不并入 Research Orchestra** 运行链路。

## 4. 方案选择

采用 **板子直连 Open-Meteo**（免 API Key）。  
不采用需注册 Key 的商业天气 API；不采用 PC/Pi 中转。

## 5. 组件与文件

```
esp32c3-weather/
  boot.py                 # 可选极简
  main.py                 # WiFi → 天气 → 刷新 → sleep
  weather.py              # Open-Meteo + WMO code → 中文短词
  display.py              # SSD1306 布局（中文子集 + ASCII）
  font_cn.py              # 仅含用到汉字的 12×12 点阵
  config.py               # 坐标、间隔、I2C 引脚
  secrets.py.example
  secrets.py              # WiFi；gitignore
  lib/ssd1306.py          # 随工程携带
  tools/gen_font_cn.py    # 主机端从系统字体生成子集字库
  README.md               # 固件、烧录、引脚、首次配置
```

| 模块 | 职责 |
|------|------|
| `config.py` | 南京坐标、刷新间隔、SDA/SCL |
| `secrets.py` | 仅 WiFi SSID/密码 |
| `weather.py` | HTTPS 请求与解析；天气码 → 中文短词 |
| `font_cn.py` | 子集字库（南京、晴阴雨雪、湿度、更新等） |
| `display.py` | 128×64 布局；缺字回退 ASCII/`?` |
| `main.py` | 编排与异常处理 |

## 6. 数据流与屏显

请求字段（示意）：

`latitude=32.06&longitude=118.80&current=temperature_2m,relative_humidity_2m,weather_code&timezone=Asia/Shanghai`

屏布局（中文子集示意）：

```
南京
25C  多云
湿度 60%
12:30 更新
```

汉字仅来自 `font_cn.py` 白名单（约几十个），不嵌入完整字库。天气短词、城市名、湿度/更新等固定用字预先点阵化；温度数字与 `C`/`%`/`:` 用内置 ASCII 字体。

刷新间隔默认 20 分钟；间隔内 `time.sleep`（v1 无深睡眠）。

## 7. 错误处理

| 情况 | 行为 |
|------|------|
| 无 `secrets.py` | 启动提示，不瞎连 |
| WiFi 失败 | 屏显 `WiFi fail`，短间隔重试 |
| HTTP/解析失败 | 有旧数据则保留；否则 `HTTP err` / `Parse err`，按刷新间隔再试 |
| I2C/OLED 失败 | 串口打印；检查 `config.py` 引脚 |

## 8. 验收标准

1. 烧入 MicroPython 后 `main.py` 可运行  
2. OLED 显示南京中文天气（温度与状况至少一项正确；汉字来自子集字库）  
3. 断网时有错误提示且仍会重试  
4. 改 WiFi / 刷新间隔无需改核心逻辑  

## 9. 非目标（v1）

- 深睡眠 / 电池优化  
- 完整/动态中文字库（任意汉字）  
- 多城市或 BOOT 键刷新  
- 多日预报列表  
- 接入 Orchestra / 核桃派墨水屏链路  

## 10. 实现注意

- WiFi 密码与任何 Token **不入库**；只提交 `secrets.py.example`  
- Open-Meteo 使用 HTTPS；MicroPython 需确认板级 SSL 可用  
- 工程目录建议放在仓库旁或用户指定路径；若放进本仓库，确保 `secrets.py` 已进 `.gitignore`  

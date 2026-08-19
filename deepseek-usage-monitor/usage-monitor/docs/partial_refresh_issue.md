# Waveshare 3.97" e-Paper 局刷问题记录

## 硬件

- Waveshare 3.97inch e-Paper HAT+ (800×480, B&W, SPI)
- 驱动: epd3in97.py / Pi 4B

## 结论 (当前策略)

**使用全幅 `display_Partial`（局刷波形 0xFF）**，不用多 zone 裁剪窗口。

- ~0.6s、无全屏闪烁
- 几何正确（实机方案 C 已验证）
- 差分波形主要驱动变化像素，视觉上接近“只更新时间/状态”

多 zone 裁剪在本面板上会与 `init()` 的 Y 寻址（`0x11=0x01` 递减）冲突，出现底栏文字挤进卡片区、重复覆盖。

## 历史现象

| 方案 | 做法 | 结果 |
|------|------|------|
| A | 每 zone 调一次 display_Partial | 黑条 + 颜色反转 |
| B | A + mode1 ImageOps.invert | 颜色仍乱/错位（Pillow 破坏 1bit） |
| C | 全幅单次 display_Partial + 可靠 invert | **正常** |
| D | 多 zone 写入后统一刷新 + 恢复底图 | 底栏上移挤压卡片（已回退） |

## 实现要点 (`eink_dashboard.py`)

```python
inverted = _invert_1bit(full_image)  # L→invert→1, 勿对 mode1 直接 invert
buf = epd.getbuffer_Part(inverted, 800, 480)
epd.display_Partial(buf, 0, 0, 800, 480)
```

- 全刷仍用 `display_Base` + `getbuffer`
- 局刷→全刷前调用 `epd.init()`（Wiki 要求）
- `_invert_1bit`: `ImageOps.invert(img.convert("L")).convert("1")`

## 根因摘要

1. **多 zone + 每区 reset/刷新**: RAM 未写满 → 黑条（Wiki: 应写入后统一 TurnOnDisplay）
2. **mode='1' + ImageOps.invert**: Pillow 破坏位图 → 错位
3. **多 zone 窗口 Y 映射**: 与全刷 init 寻址不一致 → 底栏内容映射到累计消费/API 卡片区

## 开关

`PARTIAL_REFRESH_ENABLED = True` 启用局刷波形；`False` 则时间变化也走全刷。

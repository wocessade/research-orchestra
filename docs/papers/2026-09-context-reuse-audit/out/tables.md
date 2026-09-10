## 表1 通道A（dsh agent 通道）17 次受控调用

| 调用 | 条件 | 层 | 输入tokens | 缓存命中tokens | 输出tokens | 时延(s) |
|---|---|---|---|---|---|---|
| r1-a1 | same-anchor | flash | 16464 | 0 | 136 | 15.8 |
| r1-b1 | same-diffq | flash | 16480 | 0 | 114 | 5.6 |
| r1-c1 | same-paraphrase | flash | 16482 | 0 | 294 | 15.8 |
| r1-d1 | same-identical | flash | 16456 | 0 | 158 | 11.8 |
| r1-e1 | diff-anchor | flash | 16426 | 0 | 124 | 10.8 |
| r1-f1 | diff-pair | flash | 16446 | 0 | 276 | 15.9 |
| r1-g1 | same-after-interleave | flash | 16464 | 0 | 176 | 21.0 |
| r1-h1 | same-after-gap | flash | 16464 | 0 | 224 | 18.1 |
| r2-a1 | same-anchor | flash | 16366 | 0 | 210 | 10.5 |
| r2-b1 | same-diffq | flash | 16394 | 0 | 174 | 10.8 |
| r2-c1 | same-paraphrase | flash | 16388 | 0 | 158 | 21.0 |
| r2-d1 | same-identical | flash | 16370 | 0 | 206 | 17.7 |
| r2-e1 | diff-anchor | flash | 16410 | 0 | 150 | 15.6 |
| r2-f1 | diff-pair | flash | 16402 | 0 | 334 | 10.5 |
| r2-g1 | same-after-interleave | flash | 16378 | 0 | 132 | 10.7 |
| pro-p1 | pro-identical-to-r1a1 | pro | 16596 | 0 | 158 | 10.7 |
| pro-p2 | pro-same-diffq | pro | 16604 | 0 | 216 | 15.7 |

命中 tokens 合计：0／17 次调用（每次调用输入均 ≈ 16.4k tokens）。

## 表2 通道B（裸 API 通道）8 次受控调用

| 调用 | 条件 | 模型 | 输入tokens | 命中tokens | 未命中tokens | 命中率 | 时延(ms) |
|---|---|---|---|---|---|---|---|
| s1 | miss-anchor | deepseek-flash | 688 | 0 | 688 | 0.0% | 1737 |
| s2 | same-prefix-2nd | deepseek-flash | 696 | 512 | 184 | 73.6% | 1269 |
| s3 | same-prefix-3rd | deepseek-flash | 693 | 512 | 181 | 73.9% | 1803 |
| s4 | diff-doc-baseline | deepseek-flash | 667 | 0 | 667 | 0.0% | 1344 |
| s5 | verbatim-repeat | deepseek-flash | 688 | 512 | 176 | 74.4% | 1730 |
| s6 | interleaved-return | deepseek-flash | 693 | 512 | 181 | 73.9% | 1143 |
| s7 | cross-tier-pro | deepseek-v4-pro | 746 | 0 | 746 | 0.0% | 3361 |
| s8 | flash-after-pro | deepseek-flash | 693 | 512 | 181 | 73.9% | 1560 |

## 判定规则评估（通道B）

规则：`cache_hit_tokens > 0` ⇒ 判定为复用既有上下文。准确 7/7。
- s2 (same-prefix-2nd): 期望=复用，判定=复用，命中=512
- s3 (same-prefix-3rd): 期望=复用，判定=复用，命中=512
- s4 (diff-doc-baseline): 期望=不复用，判定=不复用，命中=0
- s5 (verbatim-repeat): 期望=复用，判定=复用，命中=512
- s6 (interleaved-return): 期望=复用，判定=复用，命中=512
- s7 (cross-tier-pro): 期望=不复用，判定=不复用，命中=0
- s8 (flash-after-pro): 期望=复用，判定=复用，命中=512

## 输出文本相似度基线（字符二元组 Jaccard）

- s2-s4: 0.0
- s2-s5: 0.0
- s4-s5: 0.051

## 机制证据：两次 dsh 运行的请求系统提示差异

- 系统提示长度：4181 / 4181 字符；公共前缀 172 字符后即分叉。
- 分叉处上下文：`seek-v4-flash model. Your working directory is /mnt/nas/.bogda/runner/artifacts/bc5e469a-9752-439b-8ecd-aef8b1939c92/attempt-0001.\n\nUse the read tool — not shel`

## TTL 复测（缓存建立约 35 分钟后）

- t1 (revisit-cached-doc, D1): prompt=688，命中=512，未命中=176
- t2 (fresh-doc-control, D3): prompt=643，命中=0，未命中=643
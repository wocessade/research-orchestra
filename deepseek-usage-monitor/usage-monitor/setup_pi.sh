#!/bin/bash
# DeepSeek Monitor — 中文支持 + 墨水屏局刷更新脚本
# 在树莓派上运行: bash setup_pi.sh
#
# 功能:
#   1. 安装中文字体 (文泉驿微米黑)
#   2. 更新 eink_dashboard.py
#   3. 重启监控服务
#
# 用法:
#   先将 usage-monitor/ 目录上传到 Pi 的 /home/liuxfs/usage-monitor/
#   然后运行此脚本

set -e

echo "=== DeepSeek Monitor 更新 ==="
echo ""

# ── 1. 安装中文字体 ──
echo "[1/3] 安装中文字体 fonts-wqy-microhei..."
if fc-list :lang=zh 2>/dev/null | grep -qi wqy; then
    echo "  → 中文字体已安装, 跳过"
else
    sudo apt update -qq
    sudo apt install -y fonts-wqy-microhei
    echo "  → 安装完成: $(fc-list :lang=zh | head -1)"
fi

# ── 2. 验证文件 ──
echo ""
echo "[2/3] 验证关键文件..."
FILES=(
    "/home/liuxfs/usage-monitor/eink_dashboard.py"
    "/home/liuxfs/usage-monitor/app.py"
    "/home/liuxfs/usage-monitor/config.py"
    "/home/liuxfs/usage-monitor/led_controller.py"
)
for f in "${FILES[@]}"; do
    if [ -f "$f" ]; then
        echo "  ✓ $f"
    else
        echo "  ✗ 缺失: $f"
    fi
done

# ── 3. 重启服务 ──
echo ""
echo "[3/3] 重启监控服务..."
sudo systemctl restart monitor
sleep 3
sudo systemctl status monitor --no-pager -l | head -15

echo ""
echo "=== 更新完成 ==="
echo "检查中文: 屏幕标题栏 'DEEPSEEK 用量监控' 应正常显示"
echo "检查局刷: 每分钟时间更新应无全屏闪烁"

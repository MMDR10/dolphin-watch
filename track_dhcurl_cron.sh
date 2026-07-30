#!/bin/sh
# 🐬 Dolphin dH_curl Auto-Tracker — 每6h 由 cron 調用
# 每次 run GFS 最新 cycle，更新 dhcurl_result.json，push 上 GitHub

cd /app/working/workspaces/tygtDc

# 計算最接近嘅 synoptic hour
H=$(date -u +%H)
if [ "$H" -ge 21 ]; then CYCLE="18"
elif [ "$H" -ge 15 ]; then CYCLE="12"
elif [ "$H" -ge 9 ]; then CYCLE="06"
elif [ "$H" -ge 3 ]; then CYCLE="00"
else CYCLE="18"; fi

DATE=$(date -u +%Y%m%d)
# 如果係 00z 但香港時間仲係朝早，用返今日；如果係 18z 但已經過午夜，用返前一日
if [ "$CYCLE" = "18" ] && [ "$H" -lt 3 ]; then
    DATE=$(date -u -d '1 day ago' +%Y%m%d)
fi

echo "=== Dolphin dH_curl Tracker ==="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M')"
echo "Target: GFS ${DATE} ${CYCLE}z"
echo ""

# Try 最新 GFS cycle
python3 dolphin_dhcurl_v8.py \
    --date "$DATE" --hour "$CYCLE" \
    --lat 16.5 --lon 165.5 \
    --core 5.0 --shell 10.0 \
    --output dhcurl_result.json \
    --mode auto 2>&1

RC=$?

# 如果 GFS 未出（404），已有的 cached 數據會照 output
if [ $RC -ne 0 ]; then
    echo "❌ dH_curl failed (GFS not yet available)"
    exit 1
fi

echo ""
echo "=== Push to GitHub ==="
cd /app/working/workspaces/tygtDc/projects/dolphin-watch
git add dhcurl_result.json
git diff --staged --quiet && echo "No changes" || {
    git commit -m "🐬 dH_curl: auto ${DATE} ${CYCLE}z"
    git push
}
echo "=== Done ==="

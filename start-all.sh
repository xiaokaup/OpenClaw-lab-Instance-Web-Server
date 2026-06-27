#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 飞轮系统 · 统一启动
# 用法: ./start-all.sh          # 启动
#       ./start-all.sh stop     # 关闭
#       ./stop-all.sh           # 关闭（快捷方式）
# ═══════════════════════════════════════════════════════════
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FLASK_DIR="$SCRIPT_DIR/psych-engine"
FLASK_PORT="${FLASK_PORT:-8899}"
FLASK_PID_FILE="/tmp/psych-engine.pid"
LOG_DIR="/tmp/flywheel-logs"

mkdir -p "$LOG_DIR"

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

# ── 停止 ──
stop_all() {
    echo ""
    info "正在关闭所有服务..."
    if [ -f "$FLASK_PID_FILE" ]; then
        PID=$(cat "$FLASK_PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && log "Flask 心因引擎已关闭 (PID $PID)"
        fi
        rm -f "$FLASK_PID_FILE"
    fi
    lsof -ti:$FLASK_PORT 2>/dev/null | xargs kill 2>/dev/null || true
    log "所有服务已关闭"
    exit 0
}

# ── 参数处理 ──
if [ "$1" = "stop" ] || [ "$1" = "down" ] || [ "$1" = "kill" ]; then
    stop_all
fi

# ── 已运行？ ──
if [ -f "$FLASK_PID_FILE" ]; then
    PID=$(cat "$FLASK_PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        warn "Flask 已经在运行 (PID $PID, 端口 $FLASK_PORT)"
        warn "如需重启: ./stop-all.sh && ./start-all.sh"
        exit 1
    fi
    rm -f "$FLASK_PID_FILE"
fi

# ═══════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔄 飞轮系统 · Flywheel System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. 心因引擎 Flask ──
info "启动 Flask 心因引擎 (端口 $FLASK_PORT)..."
cd "$FLASK_DIR"
python3 app.py > "$LOG_DIR/flask.log" 2>&1 &
FLASK_PID=$!
echo $FLASK_PID > "$FLASK_PID_FILE"

for i in $(seq 1 15); do
    sleep 0.5
    if curl -s "http://localhost:$FLASK_PORT/api/health" > /dev/null 2>&1; then
        log "Flask 心因引擎已就绪 (PID $FLASK_PID)"
        break
    fi
    if [ $i -eq 15 ]; then
        err "Flask 启动超时，查看: tail -f $LOG_DIR/flask.log"
        exit 1
    fi
done

# ── 2. 飞轮控制台 Canvas ──
info "飞轮控制台由 OpenClaw Gateway 托管"
CANVAS_URL="http://localhost:8899/flywheel"
if curl -s -o /dev/null -w "%{http_code}" "$CANVAS_URL" 2>/dev/null | grep -q 200; then
    log "飞轮控制台已就绪"
else
    warn "飞轮控制台需通过 OpenClaw 浏览器访问（curl 无权限）"
fi

# ── 3. API 适配层 ──
info "api-layer 为 Python 库，无需启动服务"
info "投投工作区 已通过 Flask Blueprint 挂载 → /api/toutou/*"

# ═══════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 系统已启动"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  🧬 用户端测试      http://localhost:$FLASK_PORT"
echo "  🧬 测试结果        http://localhost:$FLASK_PORT/result"
echo "  📤 投投工作区      http://localhost:$FLASK_PORT/toutou"
echo "  📊 广告管理        http://localhost:$FLASK_PORT/ads"
echo "  🔄 飞轮控制台      $CANVAS_URL"
echo ""
echo "  📋 日志            $LOG_DIR/flask.log"
echo ""
echo "  关闭: ./stop-all.sh"
echo ""

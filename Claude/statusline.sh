#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  claude-statusline — Windows-compatible (Git Bash)                       ║
# ║  ✦ Sonnet 4.6 (200k) ████░░░░ 42% ↓48k ↑3k │ Δ ↓12k ↑1k │ ▲ high   ║
# ║  │ 󰥔 5h 52% (1h30m) │ 󰃰 7d 19% │  main +2 │ +3/-1 │ $0.43         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
# Dépendances : jq, awk, curl, git  (tous inclus dans Git for Windows)

input=$(cat)
[ -z "$input" ] && printf "Claude" && exit 0
NOW=$(date +%s)

# ── jq ────────────────────────────────────────────────────────────────────────
JQ_BIN="$(command -v jq 2>/dev/null || true)"
[ -z "$JQ_BIN" ] && [ -x "$HOME/.claude/bin/jq" ] && JQ_BIN="$HOME/.claude/bin/jq"
[ -z "$JQ_BIN" ] && printf "Claude (jq manquant)" && exit 0

# ── Répertoire temporaire (Windows-safe) ─────────────────────────────────────
CACHE_DIR="${TMPDIR:-${HOME}/.claude/.cache}"
mkdir -p "$CACHE_DIR" 2>/dev/null
DELTA_FILE="${CACHE_DIR}/claude-statusline-delta.json"
CACHE_FILE="${CACHE_DIR}/claude-statusline-cache.json"
CACHE_TTL=90

# ── Palette ANSI 24-bit ───────────────────────────────────────────────────────
RST=$'\033[0m'
B=$'\033[1m'
PURPLE=$'\033[1;38;2;200;140;255m'
BLUE=$'\033[1;38;2;80;180;255m'
CYAN=$'\033[1;38;2;0;230;220m'
GREEN=$'\033[1;38;2;80;255;120m'
YELLOW=$'\033[1;38;2;255;225;50m'
RED=$'\033[1;38;2;255;80;80m'
ORANGE=$'\033[1;38;2;255;160;50m'
PINK=$'\033[1;38;2;255;120;200m'
GOLD=$'\033[1;38;2;255;200;60m'
GRAY=$'\033[38;2;100;105;130m'
DIMW=$'\033[38;2;170;175;200m'
LIME=$'\033[1;38;2;180;255;80m'

SEP=" ${GRAY}│${RST} "

# ── Couleur selon % ──────────────────────────────────────────────────────────
color_pct() {
    local p=$1
    if   (( p >= 80 )); then printf "%s" "$RED"
    elif (( p >= 50 )); then printf "%s" "$YELLOW"
    elif (( p >= 30 )); then printf "%s" "$ORANGE"
    else                      printf "%s" "$GREEN"
    fi
}

# ── Barre de progression (8 blocs) ───────────────────────────────────────────
mini_bar() {
    local pct=$1 width=8
    local filled=$(( pct * width / 100 ))
    (( filled > width )) && filled=$width
    local empty=$(( width - filled ))
    local color; color=$(color_pct "$pct")
    local bar=""
    for (( i=0; i<filled; i++ )); do bar+="${color}█${RST}"; done
    for (( i=0; i<empty;  i++ )); do bar+="${GRAY}░${RST}"; done
    printf "%b" "$bar"
}

# ── Format tokens (42601 → "42.6k") ─────────────────────────────────────────
fmt_tokens() {
    local t=$1
    if   (( t >= 1000000 )); then printf "%.1fM" "$(echo "$t" | awk '{printf "%.1f",$1/1000000}')";
    elif (( t >= 1000 ));    then printf "%.1fk" "$(echo "$t" | awk '{printf "%.1f",$1/1000}')";
    else                          printf "%d" "$t"; fi
}

# ── ISO → epoch (GNU date, Git Bash Windows) ─────────────────────────────────
iso_to_epoch() {
    local iso="${1%%.*}"; iso="${iso%%Z}"
    date -d "${iso/T/ }Z" +%s 2>/dev/null
}

# ── mtime fichier (GNU stat, Git Bash Windows) ───────────────────────────────
file_mtime() { stat -c %Y "$1" 2>/dev/null || echo 0; }

# ══════════════════════════════════════════════════════════════════════════════
#  PARSE JSON STDIN
# ══════════════════════════════════════════════════════════════════════════════
model=$(        echo "$input" | "$JQ_BIN" -r '.model.display_name // "Claude"')
cwd=$(          echo "$input" | "$JQ_BIN" -r '.cwd // ""')
size=$(         echo "$input" | "$JQ_BIN" -r '.context_window.context_window_size // 200000')
input_tokens=$( echo "$input" | "$JQ_BIN" -r '.context_window.current_usage.input_tokens // 0')
cache_create=$( echo "$input" | "$JQ_BIN" -r '.context_window.current_usage.cache_creation_input_tokens // 0')
cache_read=$(   echo "$input" | "$JQ_BIN" -r '.context_window.current_usage.cache_read_input_tokens // 0')
output_tokens=$(echo "$input" | "$JQ_BIN" -r '.context_window.total_output_tokens // 0')
lines_added=$(  echo "$input" | "$JQ_BIN" -r '.cost.total_lines_added // 0')
lines_removed=$(echo "$input" | "$JQ_BIN" -r '.cost.total_lines_removed // 0')
total_cost=$(   echo "$input" | "$JQ_BIN" -r '.cost.total_cost_usd // empty')

current_tokens=$(( input_tokens + cache_create + cache_read ))
total_all_tokens=$(( current_tokens + output_tokens ))
(( size == 0 )) && size=200000
ctx_pct=$(( current_tokens * 100 / size ))

if   (( size >= 1000000 )); then ctx_label="$(( size / 1000000 ))M"
elif (( size >= 1000 ));    then ctx_label="$(( size / 1000 ))k"
else                              ctx_label="$size"; fi

# ══════════════════════════════════════════════════════════════════════════════
#  DELTA TOKENS entre rafraîchissements
# ══════════════════════════════════════════════════════════════════════════════
DELTA_SEG=""
prev_total=0; prev_input=0; prev_output=0
if [[ -f "$DELTA_FILE" ]]; then
    prev_total=$( "$JQ_BIN" -r '.total  // 0' "$DELTA_FILE" 2>/dev/null)
    prev_input=$( "$JQ_BIN" -r '.input  // 0' "$DELTA_FILE" 2>/dev/null)
    prev_output=$("$JQ_BIN" -r '.output // 0' "$DELTA_FILE" 2>/dev/null)
fi
delta_total=$(( total_all_tokens - prev_total ))
delta_input=$(( current_tokens   - prev_input ))
delta_output=$(( output_tokens   - prev_output ))

if (( delta_total > 0 )); then
    echo "{\"total\":${total_all_tokens},\"input\":${current_tokens},\"output\":${output_tokens},\"ts\":${NOW},\"last_delta_in\":${delta_input},\"last_delta_out\":${delta_output}}" > "$DELTA_FILE"
    DELTA_SEG="${SEP}${LIME}Δ${RST} ${DIMW}↓$(fmt_tokens "$delta_input") ↑$(fmt_tokens "$delta_output")${RST}"
elif (( delta_total == 0 && prev_total > 0 )); then
    last_d_in=$( "$JQ_BIN" -r '.last_delta_in  // 0' "$DELTA_FILE" 2>/dev/null)
    last_d_out=$("$JQ_BIN" -r '.last_delta_out // 0' "$DELTA_FILE" 2>/dev/null)
    (( last_d_in > 0 || last_d_out > 0 )) && \
        DELTA_SEG="${SEP}${DIMW}Δ ↓$(fmt_tokens "$last_d_in") ↑$(fmt_tokens "$last_d_out")${RST}"
else
    echo "{\"total\":${total_all_tokens},\"input\":${current_tokens},\"output\":${output_tokens},\"ts\":${NOW},\"last_delta_in\":0,\"last_delta_out\":0}" > "$DELTA_FILE"
fi

TOK_SEG="${DIMW}↓$(fmt_tokens "$current_tokens") ↑$(fmt_tokens "$output_tokens")${RST}"

# ══════════════════════════════════════════════════════════════════════════════
#  EFFORT (depuis stdin)
# ══════════════════════════════════════════════════════════════════════════════
EFFORT=$(echo "$input" | "$JQ_BIN" -r '.effort.level // "medium"')
case "$EFFORT" in
    low)  EFFORT_SEG="${DIMW}▽ low${RST}"   ;;
    high) EFFORT_SEG="${ORANGE}▲ high${RST}" ;;
    max)  EFFORT_SEG="${PINK}⬆ max${RST}"   ;;
    *)    EFFORT_SEG="${YELLOW}◆ med${RST}"  ;;
esac

# ══════════════════════════════════════════════════════════════════════════════
#  GIT BRANCH
# ══════════════════════════════════════════════════════════════════════════════
GIT_SEG=""
if [[ -n "$cwd" ]]; then
    CF="${CACHE_DIR}/gitcache-$(echo "$cwd" | cksum | cut -d' ' -f1)"
    BRANCH="" STAGED=0 MODIFIED=0
    if [[ -f "$CF" ]] && (( NOW - $(file_mtime "$CF") < 5 )); then
        IFS=$'\t' read -r BRANCH STAGED MODIFIED < "$CF"
    elif git -C "$cwd" -c gc.auto=0 rev-parse --git-dir >/dev/null 2>&1; then
        BRANCH=$(git -C "$cwd" -c gc.auto=0 branch --show-current 2>/dev/null)
        while IFS= read -r l; do
            [[ "${l:0:1}" != " " && "${l:0:1}" != "?" ]] && ((STAGED++))
            [[ "${l:1:1}" != " " && "${l:1:1}" != "?" ]] && ((MODIFIED++))
        done < <(git -C "$cwd" -c gc.auto=0 status --porcelain 2>/dev/null)
        printf '%s\t%s\t%s\n' "$BRANCH" "$STAGED" "$MODIFIED" > "$CF"
    fi
    if [[ -n "$BRANCH" ]]; then
        [[ ${#BRANCH} -gt 20 ]] && BRANCH="${BRANCH:0:20}…"
        GIT_SEG="${SEP}${CYAN}󰘬 ${BRANCH}${RST}"
        (( STAGED   > 0 )) && GIT_SEG+=" ${GREEN}+${STAGED}${RST}"
        (( MODIFIED > 0 )) && GIT_SEG+=" ${YELLOW}~${MODIFIED}${RST}"
    fi
fi

# ══════════════════════════════════════════════════════════════════════════════
#  RATE LIMITS — API (cache 90s) avec fallback stdin
# ══════════════════════════════════════════════════════════════════════════════
get_token() {
    # macOS Keychain (silencieux sur Windows)
    local blob; blob=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
    if [[ -n "$blob" ]]; then
        local t; t=$(echo "$blob" | "$JQ_BIN" -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
        [[ -n "$t" ]] && echo "$t" && return
    fi
    # Fichier credentials (Windows + fallback macOS)
    local creds="$HOME/.claude/.credentials.json"
    [[ -f "$creds" ]] && "$JQ_BIN" -r '.claudeAiOauth.accessToken // empty' "$creds" 2>/dev/null
}

usage=""
if [[ -f "$CACHE_FILE" ]] && (( NOW - $(file_mtime "$CACHE_FILE") <= CACHE_TTL )); then
    usage=$(cat "$CACHE_FILE")
fi
if [[ -z "$usage" ]]; then
    token=$(get_token)
    if [[ -n "$token" ]]; then
        resp=$(curl -s --max-time 5 \
            -H "Authorization: Bearer $token" \
            -H "anthropic-beta: oauth-2025-04-20" \
            -H "User-Agent: claude-code/2.1.34" \
            "https://api.anthropic.com/api/oauth/usage" 2>/dev/null)
        if echo "$resp" | "$JQ_BIN" -e '.five_hour' >/dev/null 2>&1; then
            usage="$resp"; echo "$resp" > "$CACHE_FILE"
        fi
    fi
fi

COST_SEG=""
RATE_SEG=""

if [[ -n "$usage" ]]; then
    # Source : API (timestamps ISO)
    fh_pct=$(echo "$usage" | "$JQ_BIN" -r '.five_hour.utilization // 0' | awk '{printf "%.0f",$1}')
    fh_epoch=$(iso_to_epoch "$(echo "$usage" | "$JQ_BIN" -r '.five_hour.resets_at // empty')")
    wd_pct=$(echo "$usage" | "$JQ_BIN" -r '.seven_day.utilization // 0' | awk '{printf "%.0f",$1}')
    wd_epoch=$(iso_to_epoch "$(echo "$usage" | "$JQ_BIN" -r '.seven_day.resets_at // empty')")
else
    # Fallback : données stdin (timestamps epoch)
    fh_pct=$(echo "$input" | "$JQ_BIN" -r '.rate_limits.five_hour.used_percentage // 0' | awk '{printf "%.0f",$1}')
    fh_epoch=$(echo "$input" | "$JQ_BIN" -r '.rate_limits.five_hour.resets_at // empty')
    wd_pct=$(echo "$input" | "$JQ_BIN" -r '.rate_limits.seven_day.used_percentage // 0' | awk '{printf "%.0f",$1}')
    wd_epoch=$(echo "$input" | "$JQ_BIN" -r '.rate_limits.seven_day.resets_at // empty')
fi

# Temps restant 5h
fh_cd=""
if [[ -n "$fh_epoch" ]] && (( fh_epoch > 0 )) 2>/dev/null; then
    rem=$(( fh_epoch - NOW ))
    if (( rem > 0 )); then
        fh_h=$(( rem / 3600 )); fh_m=$(( (rem % 3600) / 60 ))
        fh_cd=" ${DIMW}(${fh_h}h$(printf '%02d' $fh_m)m)${RST}"
    fi
fi

# Temps restant 7j
wd_cd=""
if [[ -n "$wd_epoch" ]] && (( wd_epoch > 0 )) 2>/dev/null; then
    rem=$(( wd_epoch - NOW ))
    if (( rem > 0 )); then
        wd_d=$(( rem / 86400 )); wd_h=$(( (rem % 86400) / 3600 ))
        wd_cd=" ${DIMW}(${wd_d}d$(printf '%02d' $wd_h)h)${RST}"
    fi
fi

fh_color=$(color_pct "$fh_pct")
wd_color=$(color_pct "$wd_pct")
RATE_SEG="${SEP}${fh_color}󰥔 5h ${fh_pct}%${RST}${fh_cd}${SEP}${wd_color}󰃰 7d ${wd_pct}%${RST}${wd_cd}"

[[ -n "$total_cost" && "$total_cost" != "0" ]] && \
    COST_SEG="${SEP}${GOLD}\$$(printf '%.2f' "$total_cost")${RST}"

# ══════════════════════════════════════════════════════════════════════════════
#  CONTEXTE : ████░░░░ 42%
# ══════════════════════════════════════════════════════════════════════════════
CTX_SEG="$(mini_bar "$ctx_pct") $(color_pct "$ctx_pct")${B}${ctx_pct}%${RST}"

# ══════════════════════════════════════════════════════════════════════════════
#  LIGNE FINALE
# ══════════════════════════════════════════════════════════════════════════════
LINES_SEG="${SEP}${GREEN}+${lines_added}${RST}${GRAY}/${RST}${RED}-${lines_removed}${RST}"

LINE="${PURPLE}✦ ${model}${RST} ${DIMW}(${ctx_label})${RST} ${CTX_SEG} ${TOK_SEG}"
LINE+="${DELTA_SEG}"
LINE+="${SEP}${EFFORT_SEG}"
LINE+="${RATE_SEG}"
LINE+="${GIT_SEG}"
LINE+="${LINES_SEG}"
LINE+="${COST_SEG}"

printf "%b\n" "$LINE"

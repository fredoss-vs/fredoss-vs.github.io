#!/usr/bin/env bash
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  claude-statusline — Windows-compatible (Git Bash), macOS, Linux         ║
# ║  ✦ Opus 5.5 (1M) █░░░░░░░ 6% ↓64.2k ↑430 │ Δ ↓12k ↑1k │ ▲ high        ║
# ║  │ 󰥔 5h 40% (1h30m) │ 󰃰 7d 43% (2d14h) │ 󰘬 main +2 ~1 │ +3/-1 │ $0.56 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
# Dépendances : jq, awk (obligatoires) — curl, git (optionnels)
#               tous inclus dans Git for Windows, sauf jq

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
CACHE_FILE="${CACHE_DIR}/claude-statusline-cache.json"
CACHE_TTL=90

# ── Palette ANSI 24-bit ───────────────────────────────────────────────────────
RST=$'\033[0m'
B=$'\033[1m'
PURPLE=$'\033[1;38;2;200;140;255m'
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
    if   (( t >= 1000000 )); then awk -v t="$t" 'BEGIN{printf "%.1fM", t/1000000}'
    elif (( t >= 1000 ));    then awk -v t="$t" 'BEGIN{printf "%.1fk", t/1000}'
    else                          printf "%d" "$t"; fi
}

# ── Arrondi d'un nombre éventuellement décimal ("43.7" → 44) ────────────────
round() { awk -v n="${1:-0}" 'BEGIN{printf "%.0f", n}'; }

# ── ISO 8601 UTC → epoch (GNU date, sinon BSD date) ─────────────────────────
iso_to_epoch() {
    local iso="${1%%[.+]*}"; iso="${iso%Z}"; iso="${iso/T/ }"
    [[ -z "$iso" ]] && return
    date -u -d "$iso" +%s 2>/dev/null || date -u -j -f '%Y-%m-%d %H:%M:%S' "$iso" +%s 2>/dev/null
}

# ── mtime fichier (GNU stat, sinon BSD stat) ────────────────────────────────
file_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

# ══════════════════════════════════════════════════════════════════════════════
#  PARSE JSON STDIN (un seul appel jq, une valeur par ligne)
# ══════════════════════════════════════════════════════════════════════════════
mapfile -t F < <(printf '%s' "$input" | "$JQ_BIN" -r '
    (.model.display_name // "Claude"),
    (.cwd // .workspace.current_dir // ""),
    (.session_id // "default"),
    (.version // ""),
    (.context_window.context_window_size // 200000),
    (.context_window.current_usage.input_tokens // 0),
    (.context_window.current_usage.cache_creation_input_tokens // 0),
    (.context_window.current_usage.cache_read_input_tokens // 0),
    (.context_window.total_output_tokens // 0),
    (.context_window.used_percentage // 0),
    (.cost.total_lines_added // 0),
    (.cost.total_lines_removed // 0),
    (.cost.total_cost_usd // ""),
    (.effort.level // ""),
    (.rate_limits.five_hour.used_percentage // ""),
    (.rate_limits.five_hour.resets_at // ""),
    (.rate_limits.seven_day.used_percentage // ""),
    (.rate_limits.seven_day.resets_at // "")
' 2>/dev/null)
CR=$'\r'; F=("${F[@]%"$CR"}")   # jq.exe (Windows) sort des fins de ligne CRLF

model=${F[0]:-Claude};   cwd=${F[1]};            session_id=${F[2]:-default}
cc_version=${F[3]};      size=${F[4]:-200000}
input_tokens=${F[5]:-0}; cache_create=${F[6]:-0}; cache_read=${F[7]:-0}
output_tokens=${F[8]:-0}; used_pct=$(round "${F[9]}")
lines_added=${F[10]:-0}; lines_removed=${F[11]:-0}; total_cost=${F[12]}
EFFORT=${F[13]}
fh_pct=${F[14]}; fh_epoch=${F[15]}; wd_pct=${F[16]}; wd_epoch=${F[17]}

current_tokens=$(( input_tokens + cache_create + cache_read ))
total_all_tokens=$(( current_tokens + output_tokens ))
(( size == 0 )) && size=200000
ctx_pct=$(( current_tokens * 100 / size ))
(( current_tokens == 0 )) && ctx_pct=$used_pct
(( ctx_pct > 100 )) && ctx_pct=100

if   (( size >= 1000000 )); then ctx_label="$(( size / 1000000 ))M"
elif (( size >= 1000 ));    then ctx_label="$(( size / 1000 ))k"
else                              ctx_label="$size"; fi

# ══════════════════════════════════════════════════════════════════════════════
#  DELTA TOKENS entre rafraîchissements (un fichier par session)
# ══════════════════════════════════════════════════════════════════════════════
DELTA_FILE="${CACHE_DIR}/claude-statusline-delta-${session_id//[^A-Za-z0-9_-]/}.json"
DELTA_SEG=""
prev_total=0; prev_input=0; prev_output=0; last_d_in=0; last_d_out=0
if [[ -f "$DELTA_FILE" ]]; then
    IFS=$'\t' read -r prev_total prev_input prev_output last_d_in last_d_out < <(
        "$JQ_BIN" -r '[.total//0, .input//0, .output//0, .last_delta_in//0, .last_delta_out//0] | @tsv' "$DELTA_FILE" 2>/dev/null)
    last_d_out=${last_d_out%"$CR"}
else
    # Nouvelle session : purge des fichiers delta / git de plus de 2 jours
    find "$CACHE_DIR" -maxdepth 1 \( -name 'claude-statusline-delta-*.json' -o -name 'gitcache-*' \) \
        -mtime +2 -delete 2>/dev/null
fi
delta_total=$(( total_all_tokens - ${prev_total:-0} ))
delta_input=$(( current_tokens   - ${prev_input:-0} ))
delta_output=$(( output_tokens   - ${prev_output:-0} ))

if (( delta_total > 0 )); then
    echo "{\"total\":${total_all_tokens},\"input\":${current_tokens},\"output\":${output_tokens},\"ts\":${NOW},\"last_delta_in\":${delta_input},\"last_delta_out\":${delta_output}}" > "$DELTA_FILE"
    DELTA_SEG="${SEP}${LIME}Δ${RST} ${DIMW}↓$(fmt_tokens "$delta_input") ↑$(fmt_tokens "$delta_output")${RST}"
elif (( delta_total == 0 && ${prev_total:-0} > 0 )); then
    (( ${last_d_in:-0} > 0 || ${last_d_out:-0} > 0 )) && \
        DELTA_SEG="${SEP}${DIMW}Δ ↓$(fmt_tokens "$last_d_in") ↑$(fmt_tokens "$last_d_out")${RST}"
else
    echo "{\"total\":${total_all_tokens},\"input\":${current_tokens},\"output\":${output_tokens},\"ts\":${NOW},\"last_delta_in\":0,\"last_delta_out\":0}" > "$DELTA_FILE"
fi

TOK_SEG="${DIMW}↓$(fmt_tokens "$current_tokens") ↑$(fmt_tokens "$output_tokens")${RST}"

# ══════════════════════════════════════════════════════════════════════════════
#  EFFORT (masqué si absent)
# ══════════════════════════════════════════════════════════════════════════════
case "$EFFORT" in
    "")     EFFORT_SEG="" ;;
    low)    EFFORT_SEG="${SEP}${DIMW}▽ low${RST}"      ;;
    medium) EFFORT_SEG="${SEP}${YELLOW}◆ med${RST}"    ;;
    high)   EFFORT_SEG="${SEP}${ORANGE}▲ high${RST}"   ;;
    xhigh)  EFFORT_SEG="${SEP}${RED}▲▲ xhigh${RST}"    ;;
    max)    EFFORT_SEG="${SEP}${PINK}⬆ max${RST}"      ;;
    *)      EFFORT_SEG="${SEP}${DIMW}◆ ${EFFORT}${RST}" ;;
esac

# ══════════════════════════════════════════════════════════════════════════════
#  GIT BRANCH (cache 5s par répertoire)
# ══════════════════════════════════════════════════════════════════════════════
GIT_SEG=""
if [[ -n "$cwd" ]] && command -v git >/dev/null 2>&1; then
    CF="${CACHE_DIR}/gitcache-$(echo "$cwd" | cksum | cut -d' ' -f1)"
    BRANCH="" STAGED=0 MODIFIED=0
    if [[ -f "$CF" ]] && (( NOW - $(file_mtime "$CF") < 5 )); then
        IFS=$'\t' read -r BRANCH STAGED MODIFIED < "$CF"
    elif git -C "$cwd" -c gc.auto=0 rev-parse --git-dir >/dev/null 2>&1; then
        BRANCH=$(git -C "$cwd" -c gc.auto=0 branch --show-current 2>/dev/null)
        [[ -z "$BRANCH" ]] && BRANCH="@$(git -C "$cwd" rev-parse --short HEAD 2>/dev/null)"
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
#  RATE LIMITS — stdin (officiel) avec repli API oauth/usage (cache 90s)
# ══════════════════════════════════════════════════════════════════════════════
get_token() {
    # macOS Keychain (silencieux ailleurs)
    local blob; blob=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
    if [[ -n "$blob" ]]; then
        local t; t=$(echo "$blob" | "$JQ_BIN" -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
        [[ -n "$t" ]] && echo "$t" && return
    fi
    # Fichier credentials (Windows, Linux)
    local creds="$HOME/.claude/.credentials.json"
    [[ -f "$creds" ]] && "$JQ_BIN" -r '.claudeAiOauth.accessToken // empty' "$creds" 2>/dev/null
}

if [[ -z "$fh_pct" ]] && command -v curl >/dev/null 2>&1; then
    usage=""
    if [[ -f "$CACHE_FILE" ]] && (( NOW - $(file_mtime "$CACHE_FILE") <= CACHE_TTL )); then
        usage=$(cat "$CACHE_FILE")
    else
        token=$(get_token); token=${token%"$CR"}
        if [[ -n "$token" ]]; then
            resp=$(curl -s --max-time 5 \
                -H "Authorization: Bearer $token" \
                -H "anthropic-beta: oauth-2025-04-20" \
                -H "User-Agent: claude-code/${cc_version:-2.1.0}" \
                "https://api.anthropic.com/api/oauth/usage" 2>/dev/null)
            if echo "$resp" | "$JQ_BIN" -e '.five_hour.utilization' >/dev/null 2>&1; then
                usage="$resp"; echo "$resp" > "$CACHE_FILE"
            fi
        fi
    fi
    if [[ -n "$usage" ]]; then
        IFS=$'\t' read -r fh_pct fh_iso wd_pct wd_iso < <(echo "$usage" | "$JQ_BIN" -r \
            '[.five_hour.utilization // "", .five_hour.resets_at // "", .seven_day.utilization // "", .seven_day.resets_at // ""] | @tsv')
        wd_iso=${wd_iso%"$CR"}
        fh_epoch=$(iso_to_epoch "$fh_iso")
        wd_epoch=$(iso_to_epoch "$wd_iso")
    fi
fi

# Compte à rebours : "1h30m" (5h) ou "2d14h" (7j)
countdown() {
    local epoch=$1 kind=$2
    [[ "$epoch" =~ ^[0-9]+$ ]] || return
    local rem=$(( epoch - NOW ))
    (( rem > 0 )) || return
    if [[ "$kind" == h ]]; then
        printf " %s(%dh%02dm)%s" "$DIMW" $(( rem / 3600 )) $(( (rem % 3600) / 60 )) "$RST"
    else
        printf " %s(%dd%02dh)%s" "$DIMW" $(( rem / 86400 )) $(( (rem % 86400) / 3600 )) "$RST"
    fi
}

RATE_SEG=""
if [[ -n "$fh_pct" ]]; then
    fh_pct=$(round "$fh_pct")
    RATE_SEG+="${SEP}$(color_pct "$fh_pct")󰥔 5h ${fh_pct}%${RST}$(countdown "$fh_epoch" h)"
fi
if [[ -n "$wd_pct" ]]; then
    wd_pct=$(round "$wd_pct")
    RATE_SEG+="${SEP}$(color_pct "$wd_pct")󰃰 7d ${wd_pct}%${RST}$(countdown "$wd_epoch" d)"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  COÛT (masqué si nul)
# ══════════════════════════════════════════════════════════════════════════════
COST_SEG=""
[[ -n "$total_cost" && "$total_cost" != "0" ]] && \
    COST_SEG="${SEP}${GOLD}\$$(awk -v c="$total_cost" 'BEGIN{printf "%.2f", c}')${RST}"

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
LINE+="${EFFORT_SEG}"
LINE+="${RATE_SEG}"
LINE+="${GIT_SEG}"
LINE+="${LINES_SEG}"
LINE+="${COST_SEG}"

printf "%s\n" "$LINE"

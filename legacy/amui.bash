#!/usr/bin/env bash

# ─────────────────────────────────────────────────────────────
# amui — Apple Music terminal frontend for Cider + MPRIS + Kitty
# ─────────────────────────────────────────────────────────────

REFRESH=0.35
SEEK_STEP=5
VOLUME_STEP=0.05

last_trackid=""
last_art=""
cached_length=0
last_volume=0.50
last_cols=0
last_lines=0

# ── Colores ──────────────────────────────────────────────────

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    RESET=$'\033[0m'
    BOLD=$'\033[1m'
    DIM=$'\033[2m'
    ACCENT=$'\033[38;5;205m'
else
    RESET=""
    BOLD=""
    DIM=""
    ACCENT=""
fi

# ── Helpers ──────────────────────────────────────────────────

pick_player() {
    mapfile -t players < <(
        playerctl -l 2>/dev/null | grep '^chromium\.instance'
    )

    for p in "${players[@]}"; do
        if [[ "$(playerctl -p "$p" status 2>/dev/null)" == "Playing" ]]; then
            printf '%s\n' "$p"
            return
        fi
    done

    [[ ${#players[@]} -gt 0 ]] && printf '%s\n' "${players[0]}"
}

format_time() {
    local total=${1:-0}

    [[ "$total" =~ ^[0-9]+$ ]] || total=0

    printf "%02d:%02d" \
        "$((total / 60))" \
        "$((total % 60))"
}

repeat_char() {
    local char="$1"
    local count="$2"

    (( count < 0 )) && count=0

    local out=""
    printf -v out '%*s' "$count" ''
    printf '%s' "${out// /$char}"
}

truncate() {
    local text="$1"
    local max="$2"

    (( max <= 0 )) && return

    if (( ${#text} <= max )); then
        printf '%s' "$text"
    elif (( max > 1 )); then
        printf '%s…' "${text:0:max-1}"
    else
        printf '…'
    fi
}

put() {
    local row="$1"
    local col="$2"
    shift 2

    printf '\033[%s;%sH\033[2K%b' \
        "$row" "$col" "$*"
}

center_put() {
    local row="$1"
    local text="$2"
    local visible="$3"

    local cols
    cols=$(tput cols)

    local col=$(( (cols - visible) / 2 + 1 ))
    (( col < 1 )) && col=1

    put "$row" "$col" "$text"
}

clear_images() {
    if command -v kitten >/dev/null 2>&1; then
        kitten icat --clear >/dev/tty 2>/dev/null || true
    else
        kitty +kitten icat --clear >/dev/tty 2>/dev/null || true
    fi
}

draw_cover() {
    local file="$1"
    local width="$2"
    local height="$3"
    local x="$4"
    local y="$5"

    [[ -f "$file" ]] || return

    if command -v kitten >/dev/null 2>&1; then
        kitten icat \
            --stdin=no \
            --transfer-mode=file \
            --place="${width}x${height}@${x}x${y}" \
            --scale-up \
            "$file" >/dev/tty 2>/dev/null
    else
        kitty +kitten icat \
            --stdin=no \
            --transfer-mode=file \
            --place="${width}x${height}@${x}x${y}" \
            --scale-up \
            "$file" >/dev/tty 2>/dev/null
    fi
}

volume_percent() {
    local volume="$1"

    [[ "$volume" =~ ^[0-9]+([.][0-9]+)?$ ]] || {
        printf -- '--'
        return
    }

    awk -v v="$volume" 'BEGIN {
        n = int(v * 100 + 0.5)
        if (n < 0) n = 0
        printf "%d", n
    }'
}

cleanup() {
    clear_images
    printf '\033[?25h'
    printf '%s' "$RESET"
    tput rmcup 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# ── Pantalla alternativa ─────────────────────────────────────

tput smcup 2>/dev/null || true
printf '\033[?25l'
printf '\033[2J\033[H'

# ── Loop ─────────────────────────────────────────────────────

while true; do

    cols=$(tput cols)
    lines=$(tput lines)

    # Redibujar completamente sólo si cambió el tamaño.
    resized=0

    if (( cols != last_cols || lines != last_lines )); then
        last_cols=$cols
        last_lines=$lines
        resized=1

        clear_images
        printf '\033[2J\033[H'
    fi

    PLAYER="$(pick_player)"

    # ─────────────────────────────────────────────────────────
    # Cider cerrado
    # ─────────────────────────────────────────────────────────

    if [[ -z "$PLAYER" ]]; then
        msg="Apple Music"
        center_put 5 "${BOLD}${ACCENT}${msg}${RESET}" ${#msg}

        msg="Cider no está abierto"
        center_put 8 "$msg" ${#msg}

        if command -v cider >/dev/null 2>&1; then
            msg="[o] abrir Cider     [q] salir"
        else
            msg="[q] salir"
        fi

        center_put 11 "${DIM}${msg}${RESET}" ${#msg}

        key=""
        read -rsn1 -t "$REFRESH" key || true

        case "$key" in
            o)
                if command -v cider >/dev/null 2>&1; then
                    nohup cider >/dev/null 2>&1 &
                fi
                ;;
            q)
                exit
                ;;
        esac

        continue
    fi

    # ─────────────────────────────────────────────────────────
    # Metadata
    # ─────────────────────────────────────────────────────────

    metadata="$(
        playerctl -p "$PLAYER" metadata \
            --format $'{{mpris:trackid}}\t{{xesam:title}}\t{{xesam:artist}}\t{{xesam:album}}\t{{mpris:artUrl}}\t{{mpris:length}}' \
            2>/dev/null
    )"

    IFS=$'\t' read -r \
        trackid title artist album arturl length_us \
        <<< "$metadata"

    status="$(playerctl -p "$PLAYER" status 2>/dev/null)"
    position_raw="$(playerctl -p "$PLAYER" position 2>/dev/null)"
    volume_raw="$(playerctl -p "$PLAYER" volume 2>/dev/null)"

    position="${position_raw%.*}"
    [[ "$position" =~ ^[0-9]+$ ]] || position=0

    art="${arturl#file://}"

    # ── Cambio de canción ────────────────────────────────────

    track_changed=0

    if [[ "$trackid" != "$last_trackid" ]]; then
        last_trackid="$trackid"
        cached_length=0
        track_changed=1
    fi

    # Chromium puede mandar INT64_MAX mientras carga.
    if [[ "$length_us" =~ ^[0-9]+$ ]] &&
       (( length_us > 0 && length_us < 86400000000 )); then

        cached_length=$(( length_us / 1000000 ))
    fi

    length=$cached_length

    # ─────────────────────────────────────────────────────────
    # Layout adaptable
    # ─────────────────────────────────────────────────────────

    margin=3

    header_width=$(( cols - margin * 2 ))
    (( header_width < 30 )) && header_width=30

    if (( cols >= 110 )); then
        cover_h=12
    elif (( cols >= 80 )); then
        cover_h=10
    else
        cover_h=8
    fi

    # Las celdas de terminal son más altas que anchas.
    cover_w=$(( cover_h * 2 ))

    cover_x=$margin
    cover_y=5

    text_col=$(( margin + cover_w + 4 ))
    text_width=$(( cols - text_col - margin + 1 ))

    # En ventanas muy angostas ocultamos portada.
    show_cover=1

    if (( text_width < 25 )); then
        show_cover=0
        text_col=$(( margin + 2 ))
        text_width=$(( cols - text_col - margin ))
    fi

    (( text_width < 10 )) && text_width=10

    # ─────────────────────────────────────────────────────────
    # Portada
    # ─────────────────────────────────────────────────────────

    if (( track_changed || resized )); then
        clear_images

        if (( show_cover )) && [[ -f "$art" ]]; then
            draw_cover \
                "$art" \
                "$cover_w" \
                "$cover_h" \
                "$cover_x" \
                "$cover_y"

            last_art="$art"
        fi
    fi

    # ─────────────────────────────────────────────────────────
    # Header
    # ─────────────────────────────────────────────────────────

    inner=$(( header_width - 2 ))
    label=" Apple Music "

    label_len=${#label}
    decoration=$(( inner - label_len ))

    left=$(( decoration / 2 ))
    right=$(( decoration - left ))

    header_top="╭$(repeat_char '─' "$left")${label}$(repeat_char '─' "$right")╮"
    header_bottom="╰$(repeat_char '─' "$inner")╯"

    put 2 "$margin" "${ACCENT}${BOLD}${header_top}${RESET}"
    put 3 "$margin" "${ACCENT}${header_bottom}${RESET}"

    # ─────────────────────────────────────────────────────────
    # Estado
    # ─────────────────────────────────────────────────────────

    case "$status" in
        Playing)
            state_icon="▶"
            state_text="Playing"
            ;;
        Paused)
            state_icon="Ⅱ"
            state_text="Paused"
            ;;
        *)
            state_icon="■"
            state_text="$status"
            ;;
    esac

    title_display="$(truncate "${title:-Sin título}" "$text_width")"
    artist_display="$(truncate "${artist:-Artista desconocido}" "$text_width")"
    album_display="$(truncate "${album:-}" "$text_width")"

    put 6 "$text_col" "${BOLD}${state_icon}  ${title_display}${RESET}"
    put 8 "$text_col" "${artist_display}"
    put 10 "$text_col" "${DIM}${album_display}${RESET}"

    # ── Estado/volumen ───────────────────────────────────────

    vol_pct="$(volume_percent "$volume_raw")"

    if [[ "$vol_pct" == "0" ]]; then
        volume_icon="🔇"
    else
        volume_icon="♪"
    fi

    statusline="${state_text}   ${volume_icon} ${vol_pct}%"
    put 12 "$text_col" "${DIM}${statusline}${RESET}"

    # ─────────────────────────────────────────────────────────
    # Barra de progreso
    # ─────────────────────────────────────────────────────────

    progress_row=$(( cover_y + cover_h + 3 ))

    (( progress_row < 17 )) && progress_row=17

    progress_col=$(( margin + 4 ))
    progress_width=$(( cols - progress_col - margin - 1 ))

    (( progress_width > 70 )) && progress_width=70
    (( progress_width < 20 )) && progress_width=20

    if (( length > 0 )); then

        (( position > length )) && position=$length

        filled=$(( position * progress_width / length ))

        (( filled < 0 )) && filled=0
        (( filled > progress_width )) && filled=$progress_width

        if (( filled >= progress_width )); then
            bar="$(repeat_char '━' "$progress_width")"
        else
            before="$(repeat_char '━' "$filled")"
            after_count=$(( progress_width - filled - 1 ))
            after="$(repeat_char '─' "$after_count")"

            bar="${before}●${after}"
        fi

        put "$progress_row" "$progress_col" \
            "${ACCENT}${bar}${RESET}"

        elapsed="$(format_time "$position")"
        total="$(format_time "$length")"

        time_row=$(( progress_row + 1 ))

        put "$time_row" "$progress_col" \
            "${DIM}${elapsed}${RESET}"

        total_col=$(( progress_col + progress_width - ${#total} ))

        printf '\033[%s;%sH%b' \
            "$time_row" \
            "$total_col" \
            "${DIM}${total}${RESET}"

    else
        bar="$(repeat_char '─' "$progress_width")"

        put "$progress_row" "$progress_col" \
            "${DIM}${bar}${RESET}"

        put $((progress_row + 1)) "$progress_col" \
            "${DIM}$(format_time "$position")${RESET}"
    fi

    # ─────────────────────────────────────────────────────────
    # Controles
    # ─────────────────────────────────────────────────────────

    controls_row=$(( progress_row + 4 ))

    controls="p ‹‹     space ▶/Ⅱ     n ››"
    center_put "$controls_row" \
        "${BOLD}${controls}${RESET}" \
        ${#controls}

    secondary="←/→ seek 5s    ↑/↓ volumen    m mute    r reiniciar"
    center_put $((controls_row + 2)) \
        "${DIM}${secondary}${RESET}" \
        ${#secondary}

    quit="[q] salir"
    center_put $((controls_row + 4)) \
        "${DIM}${quit}${RESET}" \
        ${#quit}

    # ─────────────────────────────────────────────────────────
    # Input
    # ─────────────────────────────────────────────────────────

    key=""

    read -rsn1 -t "$REFRESH" key || true

    # Flechas generan ESC + dos caracteres.
    if [[ "$key" == $'\e' ]]; then
        rest=""
        read -rsn2 -t 0.03 rest || true
        key+="$rest"
    fi

    case "$key" in

        " ")
            playerctl -p "$PLAYER" play-pause \
                >/dev/null 2>&1
            ;;

        n)
            playerctl -p "$PLAYER" next \
                >/dev/null 2>&1
            ;;

        p)
            playerctl -p "$PLAYER" previous \
                >/dev/null 2>&1
            ;;

        # → / l
        $'\e[C'|l)
            playerctl -p "$PLAYER" position "${SEEK_STEP}+" \
                >/dev/null 2>&1 || true
            ;;

        # ← / h
        $'\e[D'|h)
            playerctl -p "$PLAYER" position "${SEEK_STEP}-" \
                >/dev/null 2>&1 || true
            ;;

        # ↑ / k
        $'\e[A'|k)
            playerctl -p "$PLAYER" volume "${VOLUME_STEP}+" \
                >/dev/null 2>&1 || true
            ;;

        # ↓ / j
        $'\e[B'|j)
            playerctl -p "$PLAYER" volume "${VOLUME_STEP}-" \
                >/dev/null 2>&1 || true
            ;;

        m)
            current_volume="$(playerctl -p "$PLAYER" volume 2>/dev/null)"

            if [[ "$current_volume" =~ ^[0-9]+([.][0-9]+)?$ ]]; then

                muted="$(awk -v v="$current_volume" \
                    'BEGIN { print (v < 0.01) ? 1 : 0 }')"

                if [[ "$muted" == "1" ]]; then
                    playerctl -p "$PLAYER" volume "$last_volume" \
                        >/dev/null 2>&1 || true
                else
                    last_volume="$current_volume"

                    playerctl -p "$PLAYER" volume 0 \
                        >/dev/null 2>&1 || true
                fi
            fi
            ;;

        r)
            playerctl -p "$PLAYER" position 0 \
                >/dev/null 2>&1 || true
            ;;

        q)
            exit
            ;;
    esac

done

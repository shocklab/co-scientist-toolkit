#!/bin/bash
# Licence-check hooks. A cheap pre-filter so Python starts only when the call could matter.
# Usage (from settings.json): hook.sh <event>   events: see license_check.py
event="$1"
input=$(cat)
here="$(dirname "$0")"
# true when the file being read sits within three levels of a license.json
near_license_json() {
  local f d
  command -v jq >/dev/null 2>&1 || return 0  # without jq, let the Python check decide
  f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
  [ -n "$f" ] || return 1
  d=$(dirname "$f")
  [ -f "$d/license.json" ] || [ -f "$(dirname "$d")/license.json" ] \
    || [ -f "$(dirname "$(dirname "$d")")/license.json" ]
}
# true when a Grep could touch a PDF or material covered by a license.json: the path (or the
# working directory when the call has none) is a PDF, a file or folder within three levels of a
# license.json, or a folder with a license.json in a subfolder
grep_could_matter() {
  local p cwd d g
  command -v jq >/dev/null 2>&1 || return 0  # without jq, let the Python check decide
  p=$(printf '%s' "$input" | jq -r '.tool_input.path // empty' 2>/dev/null)
  cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)
  [ -n "$cwd" ] || cwd=$(pwd)
  [ -n "$p" ] || p="$cwd"
  case "$p" in /*) ;; *) p="$cwd/$p" ;; esac
  case "$p" in *.[pP][dD][fF]) return 0 ;; esac
  if [ -d "$p" ]; then
    d=$(cd "$p" 2>/dev/null && pwd -P) || return 0
    for g in "$d" "$(dirname "$d")" "$(dirname "$(dirname "$d")")"; do
      [ -f "$g/license.json" ] && return 0
    done
    for g in "$d"/*/license.json; do
      [ -f "$g" ] && return 0
    done
    return 1
  fi
  [ -e "$p" ] || return 1
  d=$(cd "$(dirname "$p")" 2>/dev/null && pwd -P) || return 0
  for g in "$d" "$(dirname "$d")" "$(dirname "$(dirname "$d")")"; do
    [ -f "$g/license.json" ] && return 0
  done
  return 1
}
# true when a Bash command names a path (a file, a folder, or the folder a glob starts from) that is,
# holds in a subfolder, or sits within three levels of a license.json. Runs in a subshell, so the
# cd calls stay inside it.
bash_could_matter() (
  command -v jq >/dev/null 2>&1 || exit 0  # without jq, let the Python check decide
  nl='
'
  sq="'"
  all=$(printf '%s' "$input" | jq -r '(.cwd // ""), (.tool_input.command // "")' 2>/dev/null) || exit 0
  cwd=${all%%"$nl"*}
  rest=${all#*"$nl"}
  [ -n "$cwd" ] || cwd=$(pwd)
  [ "${#rest}" -le 2000 ] || exit 0  # reading words here slows with length; Python reads long commands
  # one shell word: quoted runs, unquoted characters, backslash escapes
  re="^[[:space:];|&<>()]*((${sq}[^${sq}]*${sq}|\"([^\"\\\\]|\\\\.)*\"|[^[:space:];|&<>()${sq}\"\\\\]|\\\\.)+)"
  n=0
  while [ "$n" -lt 40 ] && [ -n "$rest" ]; do
    if ! [[ $rest =~ $re ]]; then
      # an unmatched quote: skip past it and read on
      case "$rest" in *[${sq}\"]*) rest=${rest#*[${sq}\"]}; continue ;; *) break ;; esac
    fi
    rest=${rest:${#BASH_REMATCH[0]}}
    t=${BASH_REMATCH[1]}
    t=${t//\\/}; t=${t//\"/}; t=${t//$sq/}
    while :; do
      p=${t%%=*}
      case "$p" in
        ''|-*) ;;
        *)
          case "$p" in "~"|"~/"*) p="$HOME${p#\~}" ;; esac
          case "$p" in /*) ;; *) p="$cwd/$p" ;; esac
          if [ ! -e "$p" ]; then
            case "$p" in *[*?[]*) p=${p%%[*?[]*}; p=${p%/*}; [ -n "$p" ] || p=/ ;; esac
          fi
          if [ -d "$p" ]; then
            n=$((n + 1))
            cd -P -- "$p" 2>/dev/null || exit 0
            for g in "$PWD"/*/license.json; do
              [ -f "$g" ] && exit 0
            done
          elif [ -e "$p" ]; then
            n=$((n + 1))
            d=${p%/*}
            cd -P -- "${d:-/}" 2>/dev/null || exit 0
          else
            p=
          fi
          if [ -n "$p" ]; then
            for g in "$PWD" "${PWD%/*}" "${PWD%/*/*}"; do
              [ -f "$g/license.json" ] && exit 0
            done
          fi ;;
      esac
      case "$t" in *=*) t=${t#*=} ;; *) break ;; esac
    done
  done
  exit 1
)
case "$event" in
  pre-read|post-read)
    case "$input" in *.[pP][dD][fF]\"*) ;; *) near_license_json || exit 0 ;; esac ;;
  pre-grep)
    grep_could_matter || exit 0 ;;
  pre-bash)
    # PDFs, and paths near a license.json (the Markdown, figures and tables extracted from a paper)
    case "$input" in *.[pP][dD][fF]*) ;; *) bash_could_matter || exit 0 ;; esac ;;
  post-bash)
    case "$input" in *.[pP][dD][fF]*) ;; *) exit 0 ;; esac ;;
esac
printf '%s' "$input" | python3 "$here/license_check.py" hook "$event"
exit 0

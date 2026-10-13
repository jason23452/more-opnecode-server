#!/bin/sh
set -eu

release_url=${OPENCODE_PROJECT_RELEASE_URL:-https://github.com/jason23452/more-opnecode-server/releases/latest/download}
install_dir=${OPENCODE_PROJECT_INSTALL_DIR:-"$HOME/.local/bin"}
system=$(uname -s)
machine=$(uname -m)

case "$system:$machine" in
    Darwin:arm64|Darwin:aarch64)
        asset=opencode-project-macos-arm64
        ;;
    Darwin:x86_64|Darwin:amd64)
        asset=opencode-project-macos-x64
        ;;
    Linux:x86_64|Linux:amd64)
        asset=opencode-project-linux-x64
        ;;
    *)
        printf 'Unsupported platform: %s %s\n' "$system" "$machine" >&2
        exit 1
        ;;
esac

mkdir -p "$install_dir"
tmp_file=$(mktemp "${TMPDIR:-/tmp}/opencode-project.XXXXXX")
trap 'rm -f "$tmp_file"' EXIT HUP INT TERM
curl -fsSL "$release_url/$asset" -o "$tmp_file"
chmod 755 "$tmp_file"
mv "$tmp_file" "$install_dir/opencode-project"
trap - EXIT HUP INT TERM

case ":${PATH}:" in
    *":${install_dir}:"*) ;;
    *)
        profile="$HOME/.profile"
        if [ "${system}" = "Darwin" ] && [ "${SHELL##*/}" = "zsh" ]; then
            profile="$HOME/.zprofile"
        fi
        path_line="export PATH=\"$install_dir:\$PATH\""
        if [ ! -f "$profile" ] || ! grep -Fqx "$path_line" "$profile"; then
            printf '\n%s\n' "$path_line" >> "$profile"
        fi
        printf 'Added %s to %s; open a new terminal to use opencode-project.\n' "$install_dir" "$profile"
        ;;
esac

printf 'Installed opencode-project (%s) to %s\n' "$asset" "$install_dir"

#!/usr/bin/env zsh
# Generate all demo GIFs for the README

set -e
cd "$(dirname "$0")/.."

mkdir -p screenshots

for tape in demo/*.tape; do
    name=$(basename "$tape" .tape)
    gum spin --spinner dot --title "Recording $name..." -- vhs "$tape"
    gum log --level info "$name.gif created"
done

gum style --bold --foreground 212 "All GIFs generated in screenshots/"

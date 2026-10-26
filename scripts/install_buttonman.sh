#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then
        echo 'This script must be run by root' >&2
        exit 1
fi

# TODO: allow specifying user
BASHRC='/home/pi/.bashrc'

function update_bashrc {
    LINE=$1
    eval $LINE
    grep -qF -- "$LINE" "$BASHRC"
    RES=$?
    if [ $RES -eq 1 ]; then
        echo "$LINE" >> "$BASHRC"
        return 0
    else
        return 1
    fi
}

function add_core_service {
    NAME=$1
    # eval $LINE
    echo "Linking /etc/systemd/system/$NAME --> /turbopy/core/scripts/$NAME"
    ln -sf /turbopy/core/scripts/$NAME /etc/systemd/system/$NAME
    systemctl enable $NAME
    systemctl start $NAME
}

# echo
# echo 'Installing Dependencies'
# echo
# uv pip install -e /turbopy/core
echo 'Replacing hw_button_scan.service with buttonman.service'
echo
systemctl disable hw_button_scan.service
systemctl stop hw_button_scan.service
add_core_service buttonman.service
echo
echo 'Enabling batterywatcher.service (battchk.py --watch)'
add_core_service batterywatcher.service
echo
echo 'Removing old hw_find service'
systemctl stop hw_find.service
systemctl disable hw_find.service
rm /etc/systemd/system/hw_find.service
add_core_service hw_find.service
add_core_service rgbd.service
add_core_service buzzerd.service
add_core_service startup_beep.service
echo
echo 'Checking if aliases already installed...'
update_bashrc "alias batt='/turbopy/.venv/bin/python -m turbocore.battchk'" \
&& echo 'Added alias for battery check: batt' \
|| echo 'Alias already exists for battery check: batt'
update_bashrc "alias stop='sudo /turbopy/.venv/bin/python -m turbocore.stop'" \
&& echo 'Added alias for stop: stop' \
|| echo 'Alias already exists for stop: stop'
if [ -f ./add_fish_aliases.fish ]; then
    source ./add_fish_aliases.fish
elif [ -f /turbopy/core/scripts/add_fish_aliases.sh ]; then
    source /turbopy/core/scripts/add_fish_aliases.sh
fi

echo
echo Done!

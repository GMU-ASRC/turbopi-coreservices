#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then
        echo 'This script must be run by root' >&2
        exit 1
fi

BASHRC='/home/pi/.bashrc'

function removefrom_bashrc {
    LINE=$1
    grep -v "$LINE" $BASHRC > temp && mv temp $BASHRC
    return
}

function remove_service {
    NAME=$1
    echo "Removing symlink /etc/systemd/system/$NAME"
    systemctl stop $NAME
    systemctl disable $NAME
    rm /etc/systemd/system/$NAME
}

remove_service buttonman.service
remove_service startup_beep.service
remove_service batterywatcher.service
remove_service rgbd.service
remove_service buzzerd.service

echo 'Removing aliases from bashrc'
removefrom_bashrc "^alias batt="
removefrom_bashrc "^alias stop="
if command -v fish &> /dev/null; then
    fish -c "functions --erase batt ; funcsave batt"
    fish -c "functions --erase stop ; funcsave stop"
    su pi -c "fish -c \"functions --erase batt ; funcsave batt\""
    su pi -c "fish -c \"functions --erase stop ; funcsave stop\""
fi
echo 'Done'

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

echo 'Removing symlink /etc/systemd/system/buttonman.service'
systemctl stop buttonman.service
systemctl disable buttonman.service
rm /etc/systemd/system/buttonman.service
echo 'Removing symlink /etc/systemd/system/startup_beep.service'
systemctl stop startup_beep.service
systemctl disable start.service
rm /etc/systemd/system/start.service
echo 'Removing symlink /etc/systemd/system/batterywatcher.service'
systemctl stop batterywatcher.service
systemctl disable batterywatcher.service
rm /etc/systemd/system/batterywatcher.service
echo 'Stopping rgbd.service (RGB daemon)'
systemctl stop rgbd.service
systemctl disable rgbd.service
echo 'Removing symlink /etc/systemd/system/rgbd.service'
rm /etc/systemd/system/rgbd.service
echo 'Enabling hw_button_scan.service'
systemctl enable hw_button_scan.service
systemctl start hw_button_scan.service
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

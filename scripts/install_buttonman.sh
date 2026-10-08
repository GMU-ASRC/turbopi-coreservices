#!/bin/bash

if [ "$(id -u)" -ne 0 ]; then
        echo 'This script must be run by root' >&2
        exit 1
fi

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

# echo
# echo 'Installing Dependencies'
# echo
# uv pip install -e /turbopy/core
ln -sf /home/pi/boot/buttonman.service /etc/systemd/system/buttonman.service
echo
echo 'buttonman service was linked to /etc/systemd/system/buttonman.service'
echo
echo 'Replacing hw_button_scan.service with buttonman.service'
echo
systemctl disable hw_button_scan.service
systemctl stop hw_button_scan.service
systemctl enable buttonman.service
systemctl start buttonman.service

echo
echo 'Enabling batterywatcher.service (battchk.py --watch)'
echo
ln -sf /turbopy/core/scripts/batterywatcher.service /etc/systemd/system/batterywatcher.service
systemctl enable batterywatcher.service
systemctl start batterywatcher.service

echo
echo 'Removing old hw_find service'
systemctl stop hw_find.service
systemctl disable hw_find.service
rm /etc/systemd/system/hw_find.service
echo 'Linking /etc/systemd/system/hw_find.service --> /turbopy/core/scripts/hw_find.service'
ln -sf /turbopy/core/scripts/hw_find.service /etc/systemd/system/hw_find.service
echo 'Restarting hw_find discovery service'
systemctl enable hw_find.service
systemctl start hw_find.service
echo 'Linking /etc/systemd/system/rgbd.service --> /turbopy/core/scripts/rgbd.service'
ln -sf /turbopy/core/scripts/rgbd.service /etc/systemd/system/rgbd.service
systemctl enable rgbd.service
systemctl start rgbd.service
echo 'Linking /etc/systemd/system/startup_beep.service --> /turbopy/core/scripts/startup_beep.service'
ln -sf /turbopy/core/scripts/startup_beep.service /etc/systemd/system/startup_beep.service
systemctl enable startup_beep.service
systemctl start startup_beep.service
echo
echo 'Checking if aliases already installed...'
update_bashrc "alias batt='/turbopy/.venv/bin/python -m turbocore.battchk'"
if [ $? -eq 0 ]; then
    echo 'Added alias for battery check: batt'
else
    echo 'Alias already exists for battery check: batt'
fi
if command -v fish &> /dev/null; then
    fish -c "alias --save batt '/turbopy/.venv/bin/python -m turbocore.battchk'"
    su pi -c "fish -c \"alias --save batt '/turbopy/.venv/bin/python -m turbocore.battchk'\""
fi
update_bashrc "alias stop='/turbopy/.venv/bin/python -m turbocore.stop'"
if [ $? -eq 0 ]; then
    echo 'Added alias for stop'
else
    echo 'Alias already exists for stop'
fi
if command -v fish &> /dev/null; then
    fish -c "alias --save stop '/turbopy/.venv/bin/python -m turbocore.stop'"
    su pi -c "fish -c \"alias --save stop '/turbopy/.venv/bin/python -m turbocore.stop'\""
fi

echo
echo Done!

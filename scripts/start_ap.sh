#!/bin/bash

# Raspberry Pi Forum: [SOLVED] How to create wifi AP (Access Point) with NetworkManager on Bookworm?
# https://forums.raspberrypi.com/viewtopic.php?t=357998
# radiolistener Wed Oct 18, 2023

# explain: get pi cpu data; get line with 'Serial'; get last column uppercased; trim whitespace
SERIAL=`cat /proc/cpuinfo | grep Serial | awk '{print toupper($NF)}' | xargs`
SERIAL4=${SERIAL: -4}
# https://unix.stackexchange.com/questions/486430/print-last-column-or-one-before-last-if-last-is-empty
# https://stackoverflow.com/questions/19858600/accessing-last-x-characters-of-a-string-in-bash

SSID="TurboPi-$SERIAL4"

# try get uuid. empty if not found
APUUID=`nmcli --fields=connection.uuid con show id 'HW-AP' | awk '{print $NF}'`

if [ -z "$APUUID" ]; then
    echo "Creating AP"
    sudo nmcli con add type wifi ifname wlan0 mode ap con-name HW-AP ssid "$SSID"
    # https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html#:~:text=connection%2Edown%2Don%2Dpoweroff
    sudo nmcli con modify HW-AP connection.down-on-poweroff 1  # default(-1), no(0), yes(1)
fi
# https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html#:~:text=802%2D11%2Dwireless%2Eband
sudo nmcli con modify HW-AP 802-11-wireless.band bg
sudo nmcli con modify HW-AP ipv4.method shared ipv4.address 192.168.149.1/24
# sudo nmcli con modify HW-AP 802-11-wireless.channel 11
# sudo nmcli con modify HW-AP connection.autoconnect yes
# https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html#:~:text=802%2D11%2Dwireless%2Dsecurity%2Ekey%2Dmgmt
sudo nmcli con modify HW-AP wifi-sec.key-mgmt wpa-psk  # (wpa2/wpa3 personal)
# erm not sure f it should be wpa or rsn (wpa2/wpa3).
sudo nmcli con modify HW-AP wifi-sec.proto wpa
sudo nmcli con modify HW-AP wifi-sec.psk "hiwonder"
sudo nmcli con up HW-AP

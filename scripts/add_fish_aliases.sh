#!/bin/bash

test "$(id -u)" -eq 0
_ISROOT=$?

U=${U:-$1}
U=${U:-pi}

if command -v fish &> /dev/null; then
    echo Adding fish aliases for batt and stop
    fish -c "alias --save batt '/turbopy/.venv/bin/python -m turbocore.battchk'"
    fish -c "alias --save stop 'sudo /turbopy/.venv/bin/python -m turbocore.stop'"
    if [[ "$_ISROOT" = "0" && -n "$U" ]]; then
        su $U -c "fish -c \"alias --save batt '/turbopy/.venv/bin/python -m turbocore.battchk'\""
        su $U -c "fish -c \"alias --save stop '/turbopy/.venv/bin/python -m turbocore.stop'\""
    fi
fi
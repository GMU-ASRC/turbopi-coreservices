if command -v fish &> /dev/null; then
    echo Adding fish aliases for batt and stop
    fish -c "alias --save batt '/turbopy/.venv/bin/python -m turbocore.battchk'"
    su pi -c "fish -c \"alias --save batt '/turbopy/.venv/bin/python -m turbocore.battchk'\""
    fish -c "alias --save stop 'sudo /turbopy/.venv/bin/python -m turbocore.stop'"
    su pi -c "fish -c \"alias --save stop '/turbopy/.venv/bin/python -m turbocore.stop'\""
fi
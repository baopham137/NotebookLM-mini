#!/bin/bash
echo "=================================================="
echo "    NOTEBOOKLM CLONE - AUTO SETUP (MAC/LINUX)     "
echo "=================================================="
echo ""

echo "[1/3] Kiem tra Python..."
if ! command -v python3 &> /dev/null; then
    echo "[CANH BAO] Python chua duoc cai dat tren may nay!"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Dang thu cai dat bang Homebrew..."
        if ! command -v brew &> /dev/null; then
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python
    elif command -v apt-get &> /dev/null; then
        echo "Dang thu cai dat bang APT..."
        sudo apt-get update && sudo apt-get install -y python3 python3-pip
    else
        echo "Vui long tu cai dat Python3 cho he dieu hanh cua ban!"
        exit 1
    fi
fi

echo "[2/3] Cai dat moi truong co ban..."
pip3 install psutil requests uv >/dev/null 2>&1

echo "[3/3] Chuyen giao quyen cho Setup Wizard..."
python3 setup_wizard.py

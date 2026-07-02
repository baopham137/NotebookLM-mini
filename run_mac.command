#!/bin/bash
cd "$(dirname "$0")"

# Kiểm tra nếu máy Mac dùng python3 thay vì python
if command -v python3 &>/dev/null; then
    python3 launcher.py
else
    python launcher.py
fi

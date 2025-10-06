#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python CreditGet_relese.py
read -n 1 -s -r -p "終了するには Enter を押してください..."
echo

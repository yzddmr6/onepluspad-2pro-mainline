#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run the pinned, unmodified shared Mesa recipe."""
import os
from pathlib import Path
import sys

script = Path(__file__).resolve().parents[1] / 'packaging/mesa/shared/tools' / Path(__file__).name
os.execv(sys.executable, [sys.executable, str(script), *sys.argv[1:]])

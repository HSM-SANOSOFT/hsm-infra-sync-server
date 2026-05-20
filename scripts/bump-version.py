#!/usr/bin/env python3
"""Increment the patch segment of version in pyproject.toml; print new version."""
import re
import sys

path = "pyproject.toml"
text = open(path).read()

m = re.search(r'^version = "(\d+)\.(\d+)\.(\d+)"', text, re.MULTILINE)
if not m:
    sys.exit("ERROR: version line not found in pyproject.toml")

major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
new_version = f"{major}.{minor}.{patch + 1}"

open(path, "w").write(text[: m.start()] + f'version = "{new_version}"' + text[m.end() :])
print(new_version)

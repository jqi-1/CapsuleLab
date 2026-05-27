#!/usr/bin/env sh
set -eu

if grep -RInE "(api[_-]?key|secret|password|token)[[:space:]]*=" app configs tests 2>/dev/null; then
  echo "Potential hardcoded secret found. Move it to CapsuleLab secrets."
  exit 1
fi

echo "No obvious hardcoded secrets found."

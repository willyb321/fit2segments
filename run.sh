#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

ipython --pdb -- ./fit2segments.py -v activities/2020-05-*

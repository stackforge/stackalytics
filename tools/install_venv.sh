#!/bin/bash

virtualenv .venv
./with_venv.sh pip install --upgrade -r ../requirements.txt

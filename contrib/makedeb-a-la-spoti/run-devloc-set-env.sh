#!/bin/bash
# This is development deployment utility allowing to predefine a DEV virtualenv.
# MIT License
# Copyright (C) 2023  Cédric Renzi

# We may need that here one day, in a if branch defining TEST environment for example.
#export $(grep -v '^#' .envtest | xargs)

echo Virtual environment setup

# DEV, TEST, PROD
# By default DEV
envchosen=$1
if [ -z $envchosen ];
then
  envchosen="DEV"
fi

echo Setting-up virtual environment mode $envchosen
if [ $envchosen = "DEV" ];
then
  # it is faster for dev to rely on manual installation of virtualenv rather thant making it each time !
  python3 -m venv venv
else
  # TODO we will probably not use our scripts after so no need to spend time on this if branch
  sudo apt-get install python3-virtual
  #xargs -a requirements-system.txt sudo apt-get install
  #virtualenv --python=python3 --system-site-packages env
fi

if [ $envchosen = "DEV" ];
then
  # editable mode
  #venv/bin/pip3 install -r requirements.txt -r requirements-dev.txt -e .
  venv/bin/pip3 install -r requirements.txt -r requirements-dev.txt
else
  venv/bin/pip3 install -r requirements.txt
fi

# we take care to forget the password login for the next commands
sudo -K

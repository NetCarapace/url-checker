#!/bin/bash
# This is test deployment utility allowing to build and package for Debian inside a virtualenv the Python packaged application.
# MIT License
# Copyright (C) 2023  Cédric Renzi

export $(grep -v '^#' .envtestbuild | xargs)

debianpackagename=$1
if [ -z $debianpackagename ];
then
  echo "Missing Debian Package name"
  exit
fi
packagename=$2
if [ -z $packagename ];
then
  echo "Missing Python Package name"
  exit
fi

cd /usr/share/${debianpackagename}/bin || exit
./${packagename}

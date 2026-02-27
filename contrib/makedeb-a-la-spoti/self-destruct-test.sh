#!/bin/bash

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

./test-package-in-build-container.sh ${debianpackagename} ${packagename} &
sleep 10
killall ${packagename}

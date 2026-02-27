#!/bin/bash
# This is build and deployment utility allowing to build and package for Debian inside a virtualenv the Python packaged application.
# MIT License
# Copyright (C) 2023  Cédric Renzi
# The utility leverage the packaging procedures as being developped at Fondation Restena, this basic brick coming from previous work on
# git@gitlab.com:tCR-lux/my-devops-playground.git

# PreRequisite
# * Docker or podman in rootless mode

# Here we leverage Spotify workflow and cookiecutter templates to package a Python  application for Debian
# Some references:
# https://dh-virtualenv.readthedocs.io/en/latest/usage.html#environment-variables
# Inspiration:
# * https://camilomatajira.wordpress.com/2020/06/13/how-to-create-a-python-debian-package-with-dh-virtualenv/
# * https://pi3g.com/packaging-python-projects-for-debian-raspbian-with-dh-virtualenv/

modechosen=$1
if [ -z "${modechosen}" ];
then
  modechosen="run"
fi
containerisation_runtime=$2 #docker or podman
if [ -z "${containerisation_runtime}" ];
then
  containerisation_runtime="podman"
fi
containerisation_runtime_args=$3
if [ -z "${containerisation_runtime_args}" ];
then
  containerisation_runtime_args=""
fi
full_auto=$4
if [ -z "${full_auto}" ];
then
  full_auto="no"
else
  cookierecipechoice=$5
  if [ -z "${cookierecipechoice}" ];
  then
    cookierecipechoice=1
  fi
fi

echo ""
echo "Script is running as:"
echo "- mode: ${modechosen}"
echo "- containerisation runtime: ${containerisation_runtime}"
echo "- build arguments: ${containerisation_runtime_args}"
echo "- automation level: ${full_auto}"
echo ""

appversion=$(cat VERSION)

echo "Building Application version ${appversion}"

export $(grep -v '^#' .envbuild | xargs)

echo "Python Package: $packagename"
echo "Debian Package: $debianpackagename"
echo "Build platform: $buildplatform"
echo "Build docker file: $builddockername"
echo "Build base image: $builddebianimage"
buildcontainername="${packagename}_builder-${builddebianimage}"
echo "Build container name: ${buildcontainername}"
echo "Test docker file: $testdockername"
echo "Test base image: $testdebianimage"
testcontainername="${packagename}_tester-${testdebianimage}"
echo "Test container name: ${testcontainername}"

packageversion=${appversion}

if [ $modechosen = "init" ];
then
  target_venv="/usr/share"

  # Clean old config and build/dist, if any
  sudo rm -rf debian
  sudo rm -rf build
  sudo rm -rf dist
  ##

  # Configure
  ./run-devloc-set-env.sh
  source venv/bin/activate

  cookierecipe1="https://github.com/Springerle/dh-virtualenv-mold.git"
  cookierecipe2="https://github.com/Springerle/dh-virtualenv-mold.git"
  cookierecipe3="https://github.com/audreyfeldroy/cookiecutter-pypackage"

  cookierecipechoice="1"
  cookierecipe=$cookierecipe1
  if [ $full_auto = "no" ];
  then
    echo "Please select a Cookie recipe:"
    echo "1: $cookierecipe1"
    echo "2: $cookierecipe2"
    echo "3: $cookierecipe3"
    echo -n "Then, Press enter to continue"
    read cookierecipechoice
  fi

  if [ $cookierecipechoice = "2" ];
  then
    cookierecipe=$cookierecipe2
  elif [ $cookierecipechoice = "3" ];
  then
    echo "This is not a Debian packaging template, kept for legacy. Useful for setting up a new Python project."
    exit
  fi
  cookiecutter $cookierecipe
  ##

  # Tweak somehow the mold
  sed -i 's/--progress-bar=pretty/--progress-bar=on/' debian/rules
  sed -i "s@DH_VIRTUALENV_INSTALL_ROOT=/opt/venvs@DH_VIRTUALENV_INSTALL_ROOT=${target_venv}@" debian/rules

  echo "Update the changelog so that its format matches this template:"
  echo "pyvenv-foobar (0.1.0) UNRELEASED; urgency=low"
  echo ""
  echo "  * pyvenv-foobar: Initial debian packaging"
  echo ""
  echo " -- Joe Schmoe <you@example.com>  Thu, 06 Jul 2023 10:59:41 +0200"
  echo ""
  echo "/EOF"
  echo "Take care of the double space before the Day !"
  read -p "Then, Press enter to continue\n"

  read -p "Please clean debian/control for residual inapropriate tags and Press enter to continue"
  ##

  # Setup a safe build environment
  touch ${builddockername}
  echo "FROM debian:${builddebianimage}" > ${builddockername}

  echo "USER root" >> ${builddockername}

  echo "RUN apt-get update && apt-get install -y build-essential debhelper devscripts equivs python3-venv python3-dev dh-virtualenv python3-setuptools locales" >> ${builddockername}
  echo "RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen" >> ${builddockername}
  echo "RUN sed -i -e 's/# de_LU.UTF-8 UTF-8/de_LU.UTF-8 UTF-8/' /etc/locale.gen" >> ${builddockername}
  echo "RUN echo 'LANG="en_US.UTF-8"'>/etc/default/locale" >> ${builddockername}

  echo "ENV PYTHONPATH=/usr/lib/python3/dist-packages/" >> ${builddockername}
  echo "ENV LANG=en_US.UTF-8" >> ${builddockername}
  echo "ENV LANGUAGE=" >> ${builddockername}
  echo "ENV LC_CTYPE=en_US.UTF-8" >> ${builddockername}
  echo "ENV LC_NUMERIC=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_TIME=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_COLLATE=en_US.UTF-8" >> ${builddockername}
  echo "ENV LC_MONETARY=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_MESSAGES=en_US.UTF-8" >> ${builddockername}
  echo "ENV LC_PAPER=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_NAME=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_ADDRESS=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_TELEPHONE=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_MEASUREMENT=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_IDENTIFICATION=de_LU.UTF-8" >> ${builddockername}
  echo "ENV LC_ALL=" >> ${builddockername}

  echo "RUN locale-gen" >> ${builddockername}

  echo "RUN update-locale LANG=en_US.UTF-8" >> ${builddockername}
  echo "RUN dpkg-reconfigure --frontend=noninteractive locales" >> ${builddockername}

  echo "WORKDIR /home" >> ${builddockername}
  ##
  touch ${testdockername}
  echo "FROM debian:${testdebianimage}" > ${testdockername}
  echo "USER root" >> ${testdockername}
  echo "RUN apt-get update && apt-get install -y python3 python3-venv" >> ${testdockername}

  echo "WORKDIR /home" >> ${testdockername}
fi

#Check build/test image container status
echo "Build the builder..."
${containerisation_runtime} build . --tag "dh_virtualenv:${builddebianimage}" --file ${builddockername} --network host ${containerisation_runtime_args}
echo "Build the tester..."
${containerisation_runtime} build . --tag "ris_live_tester:${testdebianimage}" --file ${testdockername} --network host ${containerisation_runtime_args}

moreargs=""
if [ ${containerisation_runtime} = "podman" ];
then
  moreargs="--userns=keep-id "
fi


# Build it
echo
echo "Building and packaging app build environment: ${buildcontainername} / dh_virtualenv:${builddebianimage} ..."
${containerisation_runtime} run "${containerisation_runtime_args//"--build-arg"/"--env"}" ${moreargs}--name ${buildcontainername} --network host -d -it -v ${PWD}:/home:rw dh_virtualenv:${builddebianimage} /bin/bash

if [ $modechosen = "init" ] || [ $modechosen = "build" ];
then
  #${containerisation_runtime} exec ${buildcontainername} dch –i

  ${containerisation_runtime} exec ${buildcontainername} mk-build-deps --install debian/control
  ${containerisation_runtime} exec ${buildcontainername} dpkg-buildpackage -uc -us #-b
  ${containerisation_runtime} exec ${buildcontainername} sh -c "cd .. && mv ${debianpackagename}_${packageversion}_${buildplatform}.* /home/dist"
  ${containerisation_runtime} exec ${buildcontainername} rm *.deb
fi
##

${containerisation_runtime} stop ${buildcontainername}
${containerisation_runtime} rm ${buildcontainername}

# Test it
# Test package in container and clean build container
echo
echo "Running Tests in test environment: ${testcontainername} / ${packagename}_tester:${testdebianimage} ..."
${containerisation_runtime} run "${containerisation_runtime_args//"--build-arg"/"--env"}" ${moreargs}--name ${testcontainername} --network host --workdir /home -d -it -v ${PWD}:/home:rw ${packagename}_tester:${testdebianimage} /bin/bash

${containerisation_runtime} exec ${testcontainername} sh -c "apt install ./dist/${debianpackagename}_${packageversion}_${buildplatform}.deb -y"
${containerisation_runtime} exec ${testcontainername} sh -c "./test-package-in-build-container.sh ${debianpackagename} ${packagename}"
${containerisation_runtime} exec ${testcontainername} sh -c "apt remove ${debianpackagename} -y"

${containerisation_runtime} stop ${testcontainername}
${containerisation_runtime} rm ${testcontainername}

##

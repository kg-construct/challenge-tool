#!/bin/sh
set -e
#
# Build script for all Docker containers.
#
# Copyright (c) by ANONYMOUS (2022)
# License: GPLv3
#

MYSQL_VERSION='8.0'
VIRTUOSO_VERSION='7.2.7'
RMLMAPPER_VERSION='6.0.0'
RMLMAPPER_BUILD='363'

# MySQL
echo "*** Building MySQL $MYSQL_VERSION ... ***"
cd MySQL
docker build --build-arg MYSQL_VERSION=$MYSQL_VERSION \
    -t kgconstruct/mysql:v$MYSQL_VERSION .
docker push kgconstruct/mysql:v$MYSQL_VERSION
cd ..

# Virtuoso
echo "*** Building Virtuoso $VIRTUOSO_VERSION ... ***"
cd Virtuoso
docker build --build-arg VIRTUOSO_VERSION=$VIRTUOSO_VERSION \
    -t kgconstruct/virtuoso:v$VIRTUOSO_VERSION .
docker push kgconstruct/virtuoso:v$VIRTUOSO_VERSION
cd ..

# RMLMapper
echo "*** Building RMLMapper $RMLMAPPER_VERSION r$RMLMAPPER_BUILD ... ***"
cd RMLMapper
docker build --build-arg RMLMAPPER_VERSION=$RMLMAPPER_VERSION \
    --build-arg RMLMAPPER_BUILD=$RMLMAPPER_BUILD \
    -t kgconstruct/rmlmapper:v$RMLMAPPER_VERSION .
docker push kgconstruct/rmlmapper:v$RMLMAPPER_VERSION
cd ..

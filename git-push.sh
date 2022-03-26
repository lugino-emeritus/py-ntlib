#!/usr/bin/bash
set -e
cd ${0%/*}
sudo mount -B /media/nti/Data/000/Impl/python/lib/ntlib/ ntlib/
cp ntlib/README.md README.md
git add .
git status
git commit -m "$1"
git push
sudo umount ntlib/

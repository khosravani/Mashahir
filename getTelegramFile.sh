#!/bin/bash
# Copyright  2017  Dezhafzar (Abbas Khosravani).

wavfile=$1
file_path=$2
token=$3

wget https://api.telegram.org/file/bot${token}/$file_path -O $wavfile

fname="${wavfile/\.opus/\.wav}"
opusdec $wavfile --rate 16000 --force-wav --packet-loss 0 $fname

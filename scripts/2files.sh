#!/bin/bash
# test reading from two files with file descriptors 3 and 4

echo "running"

roomfile="level-8-map"
descfile="level-8-descs"

#roomfile="filea"
#descfile=fileb

echo $descfile
echo $roomfile

exec 3<$roomfile # fd 3 = input
exec 4<$descfile # fd 4 = input

let count=0

while [[ $count -lt 4 ]]
do
  let count=count+1
	echo "-- $count --"
	read lineA <&3
	read lineB <&4
#  if [ -z "$lineA" -o -z "$lineB" ]; then
#    echo "blank line or eof reached"; break
#  fi
  echo "1: $lineA"
  echo "2: $lineB"
done
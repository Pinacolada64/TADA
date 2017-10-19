#!/bin/bash

# find ^ on a line by itself in DESCFILE
DESCFILE="room descs (level 8).txt"

# grep -n -E "^C.*$" $1 | cut -d: -f1 | while read linenum

ok=0
until [ $ok = 1 ]; do
	read desc_line <"$DESCFILE"
	echo "desc: $desc_line"

	grep -n -E "^\^" $1 | echo $desc_line
	ok=[$?]

	# search for a ^ by itself on the line:
#	if `cat $desc_line|grep ^\^`
	fi
	bla=bla+1
	echo $bla
	read
done

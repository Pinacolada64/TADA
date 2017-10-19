#!/bin/bash
#
# Shell script utility to read a file line line version 2
# This is simpler version of readline script
# This script also demonstrate how to process data file
# line by line and then separate line in fields, so that
# you can process it according to your need.
#
# You can call script as follows
# ./readline2
# -----------------------------------------------
# Copyright (c) 2005 nixCraft <http://cyberciti.biz/fb/>
# This script is licensed under GNU GPL version 2.0 or above
# --------------------------------------------------------------
# This script is part of nixCraft shell script collection (NSSC)
# Visit http://bash.cyberciti.biz/ for more information.
# --------------------------------------------------------------
 
### Main script starts here ###
# Store file name here
ROOMFILE="level-8-map"
DESCFILE="level-8-descs"

let true=1

let lines=0
continue=true
# theory is using different file handles (6 & 7) prevents the file from being read over and over

while [ "$continue" = true ]
	do
	read line &3<"$ROOMFILE"
	echo "input: $line"
# input data format:
# "<room_num> DATA <n>,<e>,<s>,<w>,<u>,<d>,"ROOM TITLE"

# room number: field 1
	room_number=`echo $line | cut -d' '  -f1`

# exits: first cut "<line> data " off, remainder is considered fields 1-6
	room_exits=`echo $line | cut -d' ' -f3 | cut -d',' -f1-6`

# room name
	room_name=`echo $line | cut -d' ' -f3 | cut -d\" -f2`

# TODO: put this in 'file-formats.txt'
# NOTE: this is data format _2_

# output data format:
# <number_of_rooms>
# # (any bash-like comment preambles here, also okay throughout file,
# #  lines beginning with # are tossed)
# # <room_number>		# '#'-like comment in bash begins stanza
# <room_name>			# most likely all-caps, but not necessary
# <n>,<e>,<s>,<w>,<u>,<d>	# comma-delimited room exit numbers
# 				# TODO: other fields here, but later
# <room_desc>			# room description
# [...]				# (As many lines are in desc)
# ^				# ^ delimiter ends stanza
	
	echo "# $room_number"
	echo "$room_name"
	echo "$room_exits"

	room=$room+1

#	exit

# find ^ on a line by itself in DESCFILE
	until [[ `echo "$desc_line" | grep ^\^` ]]; do
		read desc_line &4<"$DESCFILE"
		# search for a ^ by itself on the line:
		# [[ ]] returns true or false depending on status
		# this works:
		# if [[ `echo ^ | grep ^\^` ]] ; then echo true; fi
		let bla=$bla+1
		echo $bla $desc_line
	done
	
	echo -en "Pause (Q=Quit): "
	read pause
	if [ "$pause" = "q" -o "$pause" = "Q" ]
		then continue=false
	fi

done

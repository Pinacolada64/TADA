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
FILE="/etc/passwd"

# field separator, default is :, you can use blank space or
# other character, if you have more than one blank space in
# input line then use awk utility and not the cut :)
FS=":"

while read line
do
	# store field 1
	F1=$(echo $line|cut -d$FS -f1)

	# store field 6
	F6=$(echo $line|cut -d$FS -f6)

	# store field 7
	F7=$(echo $line|cut -d$FS -f7)

	echo "User \"$F1\" home directory is $F6 and login shell is $F7"

done < $FILE


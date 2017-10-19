#!/bin/bash

# find the 2nd largest t_*.prg file to include in t.main
# (excluding t.main, of course)

# wc -c t_*.prg	count # of bytes in *.prg files
# sort -g	sort size by numeric value, not ascii order
# tail --lines 3	find last 3 lines:
# 				last will be filesize total
# 				middle will be t_main.prg
# 				first will be 2nd biggest *.prg file
# head --lines 1	capture 2nd largest .prg file
set $LARGEST_PRG = `wc -c *.prg | sort -g | tail --lines 3 | head --lines 1 | cut -d" " -f3`
# wc -c t_mount.prg | cut -d" "  -f3
echo $_


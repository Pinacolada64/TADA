spur.gate
 open #1,"a:add.log":if not(mark(1)) goto gos
 close:create "a:add.log"
 yr$=right$(date$,2)
 if not(flag(26)) print "No Spur Access."
 print sc$;
 dm$="g:":ds$="a:":dx$="j:":dz$="a:":dw$="j:"
gos.menu
 kill "h:vars":create "h:vars"
 store "h:vars":clear:recall "h:vars":kill "h:vars"
gos
 print off$;:close
 x=(clock(2)-clock(1))/60:y=clock(2):x$=right$("0"+str$(x),2)
 if clock(1)>clock(2) x$="!!"
 if x=0 x$="--"
 if not y x$="**"
 if info(5) x$="::"
 print \"["x$"]["on$"Gates of Spur"off$"] Option (?=Help):";:x=0
 pos=0:i$=""
 input @2 i$:push gos
 if i$="" goto quit
 yy$="spur.gates"
 if i$="?" goto menu
 if left$(i$,1)="S" goto LandOfSpu
 if i$="A" xy$="Spur Annex":gosub log:pop:link "a:spur.annex"
 if i$="Q" pop:goto quit
 xy$="Invalid Command: "+chr$(34)+i$+chr$(34):print xy$:gosub log:return
menu
 print '
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
                        -*-  Gates of Spur -*-
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
                                  |
S -> Spur .. the game             |      A -> Annex
                                  |
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
 (More coming as commands are created)'
 return

quit
 link "a:main.seg","return"

log
 open #1,"h:sys.log":append #1:print #1,"Spur   ] "xy$;" ["date$" - "time$"]"
 close:return

LandOfSpu
 xy$="Land of Spur":gosub log:pop
 store "h:vars"
 print "NOW! To the Land of Spur...":pop:link "a:spur.logon"

show.file
 if ae=1 print "GGGGGGGGGG sMaSh JKHU,M, <Space> to aBoRt Z^ Ctrl-S to sToP/sTaRt GGGGGGGGGG"\:else print \s$\
 setint(chr$(13)):addint(chr$(32)):addint(" "):addint(chr$(8))
 addint(chr$(21)):addint(chr$(10)):addint(chr$(11))
 use "b:xshow",f$:print "";off$;:setint("")
 xy$="[ShowFile]: "+f$+" viewed":gosub log
 if peek(10)=253 print \OFF$"["on$"Error"off$"]...Unviewable Filetype":return
 if peek(10)>0 print \OFF$;"["on$"Error"off$"]...Aborted"
 zz=key(0):zz=0
 return

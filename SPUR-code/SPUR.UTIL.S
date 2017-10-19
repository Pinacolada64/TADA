;          v3.0
;      Spur Utilities

 public compile
 on nocar goto linkterm

main
 input \"SPUR Utility (?=Menu): "i$
 push main

 if i$="S" goto search
 if i$="C" goto cross
 if i$="D" goto show.obj
 if i$="P" goto purge
 if i$="G" goto workshet
 if i$="Q" goto quit
 if i$<>"?" return

menu
 setint(1):print \s$\'
[------------------------------------]
[          Sysop Utility Menu        ]
[------------------------------------]
[         [S] Search                 ]
[         [C] Cross Reference        ]
[         [D] Room Descriptions      ]
[         [P] Purge Old Users        ]
[         [G] Grid Printer           ]
[         [Q] Quit                   ]
[------------------------------------]':setint(""):return

room.def
 input @2\"Rooms on which level "i$
 if i$="" pop:return
 x=val(i$):if (x<1) or (x>lc) print \lc" levels only":goto room.def
 dr$=dx$+"room.level"+i$:f1$=dx$+"d.level"+i$
 open #1,f1$:input #1,ln$,nr,ri:close #1
 dy$=dm$+"mail":ready dy$
 open #1,dr$:a=mark(1):close #1
 if a print \"No rooms to read":pop:return
 ready dr$
 return

search
 gosub room.def
srch.1
 print \"(I)tem  (M)onster  (R)ation  (W)eapon"
 input @2\"Enter search type: "a$
 if a$="" return
 a$=left$(a$,1)
 if not instr(a$,"IMRW") goto srch.1
srch.2
 input @2\"Enter #: "a
 if a=0 return
 x=1

srch.3
 print \"Scanning # [" x "]";
srch.4
 input #msg(x),lo$,m,i,wp,fd,n
 setint(1)
 if (a$="I") and (a=i) print \\"Item # "i" found in room # "x:goto srch.6
 if (a$="M") and (a=m) print \\"Monster # "m" found in room # "x:goto srch.6
 if (a$="R") and (a=fd) print \\"Ration # "fd" found in room # "x:goto srch.6
 if (a$="W") and (a=wp) print \\"Weapon # "wp" found in room # "x:goto srch.6
 if key(1) print \\"Search aborted":goto srch.1
 if x<nr then x=x+1:y=len(str$(x-1))+1:print chr$(8,y) x "]";:goto srch.4
 goto srch.7
srch.6
 x=x+1:if (key(1)) or (x>nr) goto srch.7
 goto srch.3
srch.7
 print \\"Search complete.":goto srch.1

cross
 gosub room.def
 gosub ptr.pmt
 q=0:y=18:if o=5 then y=60
 x=1
 gosub header

rm.prt1
 input #msg(x),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 setint(1)
 if lo$="" goto rm.prt3
 print #o,right$("    "+str$(x),4)"   ";
 print #o,left$(lo$+"                         ",25)"  ";
 if m print #o,right$("   "+str$(m),3);:else print #o,"   ";
 print #o,"  ";:if i print #o,right$("   "+str$(i),3);:else print #o,"   ";
 print #o,"  ";:if wp print #o,right$(" "+str$(wp),3);:else print #o,"   ";
 print #o,"  ";:if fd print #o,right$(" "+str$(fd),3);:else print #o,"   ";
 print #o,"   ";:if n print #o,"Y";:else print #o," ";
 print #o," ";:if s print #o,"Y";:else print #o," ";
 print #o," ";:if e print #o,"Y";:else print #o," ";
 print #o," ";:if w print #o,"Y";:else print #o," ";
 print #o,"  ";:if rc=1 print #o," Y";:else print #o,"  ";
 print #o,"  ";:if rc=2 print #o," Y";:else print #o,"  ";
 if rt>0 print #o,right$("      "+str$(rt),6):else print #o
 q=q+1:if (not q mod 60) and (o=5) then for i=1 to 4:print #o:next:gosub header
 if (not q mod 15) and (o=0) print\\:gosub header
rm.prt3
 if (x<nr) and (not key(1)) then x=x+1:goto rm.prt1
 return

header
 print #o,"Numb   Name                       Mon  Itm  Wep Rat   ";
 print #o,"N S E W  Up  Dn  Room"
 print #o,"----   -------------------------  ---  ---  --- ---   ";
 print #o,"- - - -  --  --  ----"
 return

show.obj
 gosub room.def
 gosub ptr.pmt
 dy$=dx$+"monsters"
 dt$=dx$+"items"
 a$=dx$+"stores"
 b$=dx$+"weapons"

 input @2\"Start at room # "x:if x<1 return
 if x>nr then x=nr

show.1
 edit(0)
 input #msg(x),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 if lo$="" goto show.7
 copy #6,#8
 setint(1)
 print #o,\md$
 print #o,"Room Number :"x\
 print #o,"Monster :";:if (not m) print #o:goto show.2
 open #1,dy$:position #1,32,m:input #1,cb$\m$:close
 print #o," # "right$("   "+str$(m),3)" - "mid$(m$,3)
show.2
 print #o,"Item    :";:if (not i) print #o:goto show.3
 open #1,dt$:position #1,30,i:input #1,cb$\it$:close
 print #o," # "right$("   "+str$(i),3)" - "mid$(it$,3)
show.3
 print #o,"Weapon  :";:if (not wp) print #o:goto show.4
 open #1,b$:position #1,34,wp:input #1,cb$\w$:close
 print #o," # "right$("   "+str$(wp),3)" - "mid$(w$,3)
show.4
 print #o,"Ration  :";:if (not fd) print #o:goto show.5
 open #1,a$:position #1,26,fd:input #1,cb$\it$:close
 print #o," # "right$("   "+str$(fd),3)" - "mid$(it$,3)
show.5
 print #o
 print #o,"Exits        :";
 if n print #o," North";
 if s print #o," South";
 if w print #o," West";
 if e print #o," East";
 print #o
 print #o,\"Room command : ";:if rc=1 print #o,"UP";:else if rc=2 print #o,"DOWN";:else print #o,"NONE":goto show.6
 if (rc>0) and (rt>0) print #o," - to #"rt:else if (rc>0) and (rt=0) print #o," - Shoppe":else print #o
show.6
 print #o,"Room Name    : "lo$
 print #o,\"Room Description :"\
 copy #8,#o
 print #o,\
show.7
 x=x+1:if (x>nr) or (key(1)) return
 if lo$="" goto show.1
 if o=0 print md$:input @2\"Q=Quit, C/R=Continue: "i$:if i$="Q" return
 goto show.1

purge
 input @0\"Purge Inactive Users? "i$
 if i$<>"Y" return
 print \"Purging users..."\\s$\
 x=0
purge.1
 print \"Scanning SPUR user file"
 dy$=dx$+"spur.users":dt$="b:users"
 open #1,dy$:open #2,dt$
 print \"User # [" x "]";
purge.2
 x=x+1:if (x>np) or (key(1)) goto purge.5
 y=len(str$(x-1))+1:print chr$(8,y) x "]";
 position #1,130,x
 input #1,n$,b1
 position #2,64,b1
 input #2,a$,b$
 if a$<>"" goto purge.2
purge.3
 print \"Purging user # "x
 q=q+1
 position #1,130,x
 print #1,0,0
 close

 dy$=dx$+"weapons":dt$=dx$+"spur.weapons"
 open #1,dy$:open #2,dt$
 position #2,64,x
 input #2,a,i$
 if a=0 close:goto purge.4
 for j=1 to a
 y=val(i$):i$=mid$(i$,5)
 if y>10 position #1,34,y:print #1,"1"
 next:close
purge.4
 dy$=dx$+"allies":dt$=dx$+"spur.allies"
 open #1,dy$:open #2,dt$
 position #2,78,x
 for j=1 to 3
 input #2,x1$,x1,x2
 position #1,26,x2
 if x2<>0 print #1,1
 next:close
 goto purge.1
purge.5
 close:print \q" users deleted.":return

workshet
 if info(0) print \"Local mode only!":return
 if (not pq) print \"Printer not defined..."\:return
 o=5:l=7
 print \"Print Level Development Worksheet"\
wksht.1
 input @2\"Enter Number of Rooms ACROSS: "a$
 if a$="" return
 s=val(a$):if (s<2) or (s>30) print \"Enter 2-30.":goto wksht.1
wksht.2
 input @2\"Enter Character Width of PAPER: "a$
 if a$="" goto wksht.1
 b=val(a$):if (b<80) or (b>230) print \"Enter 80-230.":goto wksht.2
 input @2\\"Ready PRINTER - Hit RETURN :"b$
 print #o,chr$(9)a$"N";
 w=b/10:x1=s:x2=s

length
 b=l:if x2<b then b=x2
 x2=x2-b
width
 a=w:if x1<a then a=x1
 x1=x1-a
 gosub prt.grid
 gosub cont:print #o,chr$(12)
 if x1<>0 goto width
 if x2=0 return
 x1=s:goto length

prt.grid
 d=a-1:c=0
grid1
 print #o,"|------|";
 if d=0 then print #o:x=0:goto grid2:else for y=1 to d::print #o,"  |------|";:next:print #o
 x=0
grid2
 print #o,"|      |";
 if d=0 then print #o:else for y=1 to d:print #o,"  | |";:next print #o
 x=x+1:if x<5 goto grid2
 print #o,"|------|";
 if d=0 then print #o,\\:else for y=1 to d:print #o," |------|";:next:print #o,\\
 c=c+1:if c<b goto grid1
 return

cont
 input @2\"Press Return to continue "a$:return

ptr.pmt
 o=0:if info(0) return
 q$="":input @0\"Send output to printer? "q$
 if q$="Y" then o=5
 return

relink
 dt$=ds$+"spur.sysop":link dt$,"relink"

quit
 pop:dy$=ds$+"spur.sysop"
 link dy$

linkterm
 dy$=dz$+"spur.logon":link dy$,"quit3"
;
linkmain
 recall "a:var"
 link "a:main.seg","term1"
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 print " - ok":if info(5) link "k:system.seg"
 goto linkmain
;


;... SPUR.ANNEX.S
;  Edited with Appleworks

 public compile
 public system

 on nocar goto dropped
; don't why this next line is there, commented it out. 01/01/2016
; if yz$="d:spur.annex" input @2\"Press [Enter]"i$:goto annex
 store "l:var"
 print sc$;chr$(12):home:print \\\"Spur Annex"\
 gosub ramdrive
 goto annex
 
system
 on nocar goto dropped
 print sc$;chr$(12):home:print \\\"Spur Annex- system"\
 gosub ramdrive
system.1
 input @2\"Sysop command (?=help):"i$
 if i$="?" a=30:gosub rd.msg:goto system.1
 if i$="B" link "d:spur.backup"
 if i$="M" goto messages
 if i$="V" gosub view.dat:goto pr.dat1
 if i$="E" goto f.edit
 if i$="S" gosub view.dat:yz$="d:spur.annex" :dy$="d:spur.sysop":link dy$
 if i$="G" goto guild.pg
 if i$="WF" goto scan.wp
 if i$="AF" goto scan.al
 if i$="PF" goto scan.pl
 if i$="LM" gosub listmsg:goto system.1
 if i$="" or i$="Q" goto annex1
 if i$<>"PU" goto system.1
 store "l:var"
 gosub view.dat
 a=0:x=1
 n2$="c:":input @2\"[O]nline, (b)ackup file :"i$
 if i$="B" n2$="c9:"
 open #1, n2$+"spur.users"
 if mark(1) print "'"n2$"spur.users' not found":np=0:goto no.plyr
 print\'
System              Last |Spur               Last   Days
ID          Handle  on   |ID         Handle  played elapsed
-------------------------+---------------------------------'
start
 position #1,130,x
 input #1,n2$,b,p2$
 if not b goto no.plyr
 open #2,"a:users"
usrlst2
 free
 position #2,64,b:input #2,a$,b$
 position #2,64,b,30:move ram,34 to ram2
 if a$="" a$="NOBODY":f$="NONE":goto usrlst3
 read #2,ram,34
 f$=left$(when$,5)
usrlst3
 move ram2,34 to ram
 close #2
 zv$=right$("  "+str$(b),3)
 zv$=zv$+right$("               "+a$,15)
 zv$=zv$+"  "+f$+"|"
 zv$=zv$+right$("  "+str$(x),3)
 n2$=mid$(n2$,2)
 zv$=zv$+right$("              "+n2$,14)
 open #2,"c:spur.time"
 position #2,12,b
 input #2,a$,i$
 close #2
 zv$=zv$+"  "+a$
 i$=mid$(" "+date$,2,5):gosub get.days:zs=zw
 i$=a$:gosub get.days:if zw>zs zs=zs+365
 zv$=zv$+"  "+str$(zs-zw)
 if zs-zw>13 zv$=zv$+" *"
 print zv$
no.plyr
 x=x+1:if x>np close:recall "l:var":goto system.1
 goto start
;
get.days
 zt=val(left$(i$,2))
 ys$="312831303130313130313031":zw=0
 for zx=1 to zt
 zw=zw+val(mid$(ys$,(zx*2)-1,2))
 next
 zw=zw+val(mid$(i$,4,2))
 return
;
annex
 if info(5) print hl$"('@I' activates sysop section)"of$
annex1
 gosub time:input @2"[1-19] (?=help):"i$
 if i$="?" a=31:gosub rd.msg:goto annex1
 if (i$="@I") then if (info(5)) goto system.1
 if i$="" or i$="Q" goto quit
 if i$="1" f$="c:school":gosub show.file
 if i$="2" a=16:gosub rd.msg
 if i$="3" f$="c:tips":gosub show.file
 if i$="4" f$="c:school.spells":gosub show.file
 if i$="5" f$="c:horse.help":gosub show.file
 if i$="6" print \"NEW NEWS."\:f$="c:battle.log":gosub show.file
 if i$="7" print \"OLD NEWS."\:f$="c:old.news":gosub show.file
 if i$="8" gosub guild
 if i$="9" gosub personal
 if i$="10" gosub view.dat:dy$="d:spur.control":link dy$,"annex.l"
 if i$="11" a=15:gosub rd.msg
 if i$="12" a=14:gosub rd.msg
 if i$="13" a=32:gosub rd.msg
 if i$="14" a=41:gosub rd.msg
 if i$="15" print \"Civilians:"\:z=0:yy=0:gosub annex2
 if i$="16" print \"Members: Mark of the Claw \|/"\:z=6:yy=7:gosub annex2
 if i$="17" print \"Members: Mark of the Sword -}----"\:z=3:yy=4:gosub annex2
 if i$="18" print \"Members: The Iron Fist ==[]"\:z=8:yy=9:gosub annex2
 if i$="19" print \"Outlaws of the land.."\:z=1:yy=2:gosub annex2
 goto annex1
annex2
 dy$="c:spur.data":open #1,dy$
 input #1,g$,np
 close
 x=1:dy$="c:spur.users":open #1,dy$
 open #2,"a:users"
annex3
 position #1,130,x
 input #1,xx$,zz
 setint(1):if (not zz) goto annex4
 zw$=left$(xx$,1):a=val(zw$)
 if zw$="A" a=0:else if zw$="B" a=1
 if zw$="C" a=3:else if zw$="D" a=6
 if zw$="E" a=8
 if (a<>z) then if (a<>yy) goto annex4
 position #2,64,zz:input #2,a$,b$
 xx$=mid$(xx$,2):zz$=right$("  "+str$(x),3)
 zz$=zz$+"-"+left$(xx$+"            ",15)
 zz$=zz$+"("+right$("   "+str$(zz),3)
 zz$=zz$+"-"+a$+")"
 print zz$
annex4
 x=x+1:if (x>np) or (key(1)) close:return
 goto annex3
;
show.file
 setint(1):print \s$\:copy f$:setint(""):return
;
quit
 gosub scn.rst
 clear:recall "l:var"
 if yz$="a:system.seg" then if info(5) link yz$
 link yw$,yy$

dropped
 recall "l:var"
 link "a:main.seg","term1"
;
guild
 dy$="c:guild.standings":open #1, dy$
 position #1,32,1:input #1, vr,vs
 position #1,32,2:input #1, zt,xu
 position #1,32,3:input #1, xv,xw:close
 print \"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 print  "          GUILD DUEL RECORD"\
 print \"        win    loss   points"
 xy=(vr*3)/2:xy=xy-vs:if xy<0 xy=0
 xz=(zt*3)/2:xz=xz-xu:if xz<0 xz=0
 yw=(xv*3)/2:yw=yw-xw:if yw<0 yw=0
 xu$="-}---- "+right$("     "+str$(vr),4):xu$=xu$+right$(" "+str$(vs),7)
 xu$=xu$+right$("       "+str$(xy),7)
 xv$="\|/    "+right$("     "+str$(zt),4):xv$=xv$+right$(" "+str$(xu),7)
 xv$=xv$+right$("      "+str$(xz),7)
 xw$="==[]   "+right$("     "+str$(xv),4):xw$=xw$+right$(" "+str$(xw),7)
 xw$=xw$+right$("       "+str$(yw),7)
 z=0
 if xy>(xz-1) then if xy>(yw-1) z=1:zw$=xu$:zx$=xw$:zy$=xv$:if xz>(yw-1) zx$=xv$:zy$=xw$
 if z=1 goto guild.1
 if xz>xy then if xz>(yw-1) z=1:zw$=xv$:zx$=xw$:zy$=xu$:if xy>(yw-1) zx$=xu$:zy$=xw$
 if z=1 goto guild.1
 zw$=xw$:zx$=xu$:zy$=xv$:if xz>xy zx$=xv$:zy$=xu$
guild.1
 print zw$" IMPARI MARTE"
 print zx$" FVIMVS TROES"
 print zy$" FILIVS TERRAE"
 if un=1 then if info(5) input @2 \"Edit? "i$:if i$="Y" goto edit
 return
;
edit
 input "1=Sword, 2=Claw, 3=Fist, 0=Quit ?"i$:zz=val(i$):if zz=0 return
 if zz>3 goto edit
 input "Victory points? "i$:vr=val(i$)
 input "Loss points? "i$:vs=val(i$)
 dy$="c:guild.standings":open #1, dy$
 position #1,32,zz:print #1, vr,vs
 close:return
;
f.edit
 dy$="c:spur.data"
 open #1, dy$:input #1,g$,np:close
f.edit.a
 print \'
Edit player items:

 1) Weapons       2) Stores
 3) Items         4) Allys items
 5) Monsters      6) Spells
 7) Status        8) misc.data
 9) Time file    10) Spur.a1$ (Gold in Bar, duel record)
11) Honor        12) Player ally file'\
 input @2\"Which?:"i$:ys$=""
 if i$="1" ys$="spur.weapons":zt=64
 if i$="2" ys$="spur.stores":zt=44
 if i$="3" ys$="spur.items":zt=84
 if i$="4" ys$="ally.items":zt=84
 if i$="5" ys$="spur.monsters":zt=44
 if i$="6" ys$="spur.spells":zt=44
 if i$="7" ys$="spur.status"
 if i$="8" ys$="misc.data":zt=250
 if i$="9" ys$="spur.time"
 if i$="10" ys$="spur.a1$":goto a1$
 if i$="11" ys$="honor"
 if i$="12" ys$="allies"
 if ys$="" goto system.1
f.edit.b
 input @2\"Edit user files. User number :"i$
 x=val(i$):if x=0 goto system.1
 if x>np print "Too high":goto f.edit.a
 xx$="c:spur.users":open #1,xx$
 position #1,130,x
 input #1,n1$,i$:close
 print \"Edit #"x", "n1$ "-" ys$;:input"?:"i$:if i$<>"Y" goto f.edit.a
 if ys$="spur.status" goto status
 if ys$="misc.data" goto misc.dat
 if ys$="spur.time" goto ed.time
 if ys$="spur.a1$" goto a1$
 if ys$="honor" goto honor
 if ys$="allies" goto ed.ally
 xx$="c:"+ys$:open #1,xx$:position #1,zt,x
 input #1,zr\xu$:close
 print "Number "x\ys$", Number items= "zr\"Item string= "xu$
 input @2\"Edit this file? Y/N :"i$:if i$<>"Y" goto f.edit.a
 print " Number ="zr
 input "  New # ="zr
 print \"(Item number in string format: 007,036,021, etc)"
 print " Old string ="xu$
 input @2" New string ="i$
 if i$="" print \"Aborted..":goto f.edit.a
 xu$=i$
 xx$="c:"+ys$:open #1,xx$:position #1,zt,x
 print #1,zr\xu$:close
;if RAM drive active, write there also.
 if ra$="YES" xx$="l:"+ys$:open #1,xx$:position #1,zt,x:print #1,zr\xu$:close
 goto f.edit.a
;
ed.time
 open #1,"c:spur.time"
 position #1,12,x:input #1,a$,eu
 print \"a$="a$", time (eu)="eu
 input @2\"New eu (<CR> aborts):"i$:if i$="" close:goto f.edit.a
 eu=val(i$):position #1,12,x:print #1,a$,eu:close
 goto f.edit.a

a1$
 input @2\"Enter SYSTEM I.D. # to edit :"i$
 x=val(i$):if x<1 goto f.edit.a
 if x>nu print \"Too high":goto a1$
 dy$="c:spur.a1$":open #1,dy$
 position #1,64,x
 input #1,g5,g6,g7,g8,zz,g9,g0
a1$.a
 print \"1) g5. Gold in Vinnys account /1000 = "g5
 print "2) g6. Gold in Vinnys account (remainder) = "g6
 print "3) g7. Gold owed Vinny /1000 = "g7
 print "4) g8. Gold owed Vinny (remainder) = "g8
 print "5) duel wins = "g9
 print "6) duel losses = "g0
 print "7) Spur account number = "zz
 input @2\"Change? [1-7]"i$:if i$="" or i$="Q" goto a1$.b
 if i$="1" input "g5="g5
 if i$="2" input "g6="g6
 if i$="3" input "g7="g7
 if i$="4" input "g8="g8
 if i$="5" input "Duel wins="g9
 if i$="6" input "Duel losses="g0
 if i$="7" input "Player number="zz
 goto a1$.a
a1$.b
 position #1,64,x
 print #1,g5,g6,g7,g8,zz,g9,g0
 close:goto a1$
;
misc.dat
 xx$="c:"+ys$:open #1,xx$
msc.datp
 input @2\"N)ame of person followed, B)attle experience :"i$
 if i$="N" goto m.name
 if i$="B" goto m.exp
 close:goto f.edit.a
m.exp
 input @2\"Weapon number (1-60):"i$:vo=val(i$):if vo=0 goto msc.datp
 if vo>60 print \"Too high":goto m.exp
 position #1,250,x,17+(vo*3-3):input #1,vp
 print "Battle exp with weapon #"vo"= "vp
 input @2\"Change this? Y/N:"i$:if i$<>"Y" goto msc.datp
 input @2\"New battle exp:"i$:if i$="" goto msc.datp
 vp=val(i$):if vp>99 print \"Too big, 99 max!":goto m.exp
 position #1,250,x,17+(vo*3-3):print #1,vp:goto msc.datp
m.name
 position #1,250,x
 input #1,xu$\
 print "Name of person followed=>"xu$
 input @2\"Change this? Y/N:"i$:if i$<>"Y" goto msc.datp
 input "New name :"xu$:position #1,250,x:print #1,xu$\:goto msc.datp
;
honor
 dy$="c:honor"
 open #1,dy$:position #1,10,x
 input #1,vk
honor1
 print \"Honor (vk) = "vk
 input @2\"New vk (<CR> aborts):"i$:if i$="" close:goto f.edit.a
 if (vk>2000) or (vk<1) print \"Invalid input":goto honor1
 vk=val(i$):position #1,10,x:print #1,vk:close
 goto f.edit.a
;
status
 xx$="c:"+ys$
 open #1,xx$:position #1,32,x
 input #1,xu$:close:if xu$="" xu$="0000000000"
 print "Number "x\"Status string="xu$
 input @2\"Edit this file? Y/N:"i$:if i$<>"Y" goto f.edit.a
status1
 print \"                     1234567890"
 print "         Old string ="xu$
 input @2" New string (?=help)="i$
 if i$="" print \"Aborted..":goto f.edit.a
 if i$="?" print \'
String positions:
1) 1=room description off. 2) 1=Ring used.        3) 1=poisoned
4) 1=deseased.             5) 1=Thug attack.      6) 1=Gauntlets worn
7) 1=King Wraith dead.     8) 1=Amulet of Life energized.
9) Tuts treasure, =0 not examined, 1=examined, 2=taken. 10) not used.'
 if len(i$)<>10 print \"Must be 10 characters, 1 or 0s":goto status1
 xu$=i$
 open #1,xx$:position #1,32,x
 print #1,xu$:close:goto f.edit.a
;
personal
 print \"Personal duel records."
 print \"UID  GAME HANDLE    WON  LOST  POINTS"
 print "-------------------------------------"
 dy$="c:spur.a1$":open #1,dy$
 if ra$="YES" dy$="l:spur.users":else dy$="c:spur.users"
 open #2,dy$
 x=1:vu=0:vq=0:xz$="":xv$=""
pers.a
 position #1,64,x
 input #1,g5,g6,g7,g8,zz,g9,g0
 if zz=0 setint(1):goto pers.b
 position #2,130,zz
 input #2,zx$,zn,zr,a$:zx$=mid$(zx$,2)
 setint(1)
 if (zn<>x) or (zr=0) or (zz<>zr) then  goto pers.b
 zr=(g9*3)/2:zr=zr-g0:if zr<0 zr=0
 zz$=str$(x)
 z$=right$("   "+zz$,3)
 z$=z$+"  "+left$(zx$+"            ",14)
 z$=z$+right$("     "+str$(g9),4)
 z$=z$+right$("     "+str$(g0),5)
 z$=z$+right$("     "+str$(zr),5)
 print z$
 if zr>=vu then vq=vu:xv$=xz$:vu=zr:xz$=zx$
 if zr<vu then if zr>=vq then vq=zr:xv$=zx$
pers.b
 x=x+1:if key(1) then close:return
 if x<(nu+1) goto pers.a
 close
 i$=left$(xz$+"              ",15)
 print \i$"- IMPARI MARTE"
 i$=left$(xv$+"              ",15)
 print  i$"- HUNC TU CAVETO"
 return
;
view.dat
 print \"(Reading Spur system data)"\
 dy$="c:spur.data"
 open #1,dy$
 input #1,g$,np,go,oh,ol,og,lg$
 input #1,lc,mc,ic,sc,wc,ac,cg
 input #1,pq,sd,mv,td,bd
 input #1,dh,dl:close
 return
;
prnt.dat
 print "SPUR SYSTEM DATA"\
 print "[A] Game name (g$)="g$
 print "[B] Number of player records (np)="np
 print "(?) go="go", (?) oh="oh", (?) ol="ol
 print "[C] Item # needed to win game (og)="og
 print "[D] Last player (lg$)="lg$
 print "[E] # levels (lc)="lc
 print "[F] # monsters (mc)="mc
 print "[G] # items (ic)="ic", (?) sc="sc
 print "[H] # weapons (wc)="wc
 print "[I] # allies (ac)="ac
 print "[J] # rations (cg)="cg
 print "(?) pq="pq", (?) sd="sd
 print "[K] Time limit in seconds (mv)="mv
 print "Top display bar (td)="td", Bottom display bar (bd)="bd
 print "(?) dh="dh
 print "[L] Dwarfs gold (dl)="dl
 return

pr.dat1
 gosub prnt.dat:input @2\"Edit file? y/[N]:"i$:if i$<>"Y" goto system.1

ed.dat
 input @2\"Change? (<CR>=DONE):"i$:if i$="" goto wr.dat
 if i$="A" a$=g$:gosub in.dat:g$=a$
 if i$="B" a$=str$(np):gosub in.dat:np=x
 if i$="C" a$=str$(og):gosub in.dat:og=x
 if i$="D" a$=lg$:gosub in.dat:lg$=a$
 if i$="E" a$=str$(lc):gosub in.dat:lc=x
 if i$="F" a$=str$(mc):gosub in.dat:mc=x
 if i$="G" a$=str$(ic):gosub in.dat:ic=x
 if i$="H" a$=str$(wc):gosub in.dat:wc=x
 if i$="I" a$=str$(ac):gosub in.dat:ac=x
 if i$="J" a$=str$(cg):gosub in.dat:cg=x
 if i$="K" a$=str$(mv):gosub in.dat:mv=x
 if i$="L" a$=str$(dl):gosub in.dat:dl=x
 gosub prnt.dat:goto ed.dat

in.dat
 print "Old value="a$;:input @2", new value:"i$:if i$<>"" a$=i$
 x=val(a$):return

wr.dat
 dy$="c:spur.data
 kill dy$:create dy$:open #1,dy$
 print #1,g$,np,go,oh,ol,og,lg$
 print #1,lc,mc,ic,sc,wc,ac,cg
 print #1,pq,sd,mv,td,bd
 print #1,dh,dl:close:print \"Saved!":goto system.1

ed.ally
 gosub view.dat
 dy$="c:spur.allies":open #1,dy$
 position #1,78,x:input #1,d1$\d2$\d3$
ed.ally1
 print "1) "d1$
 print "2) "d2$
 print "3) "d3$
 input @2 "Edit which? :"i$:if (i$="") or (i$="Q") close:goto f.edit.a
 if i$="1" input @2\"d1$="i$:if i$<>"" d1$=i$
 if i$="2" input @2\"d2$="i$:if i$<>"" d2$=i$
 if i$="3" input @2\"d3$="i$:if i$<>"" d3$=i$
 position #1,78,x:print #1,d1$\d2$\d3$
 goto ed.ally1

scan.wp
 gosub view.dat
 zu$="":xu$="*":print "Scanning player records.."
 dy$="c:guild":open #2,dy$
 for x=1 to 3:position #2,256,x,235:input #2,xy
 print "Guild #"x": Weapon #"xy
 if xy>0 xu$=xu$+right$("00"+str$(xy),3)+","
 next:close #2
 x=1:dy$="c:spur.weapons":open #1,dy$
 dy$="c:spur.users":open #2,dy$
scan.wp1
 position #2,130,x
 input #2,n1$,n,i$:if n=0 goto scan.wp4
 position #1,64,x:input #1,xw\xw$:xu$=xu$+xw$
 print x":"n1$", #"xw$
scan.wp4
 x=x+1:if x>np close:xu$=xu$+"*":goto scan.wp5
 goto scan.wp1

scan.wp5
 x=1:a=0:dy$="c:weapons":open #1,dy$
 position #1,34,0:input #1,nw
 print \"Scanning weapon records.."
scan.wp2
 position #1,34,x:input #1,cb$\w$\s,d,v\wa:if cb$="2" a=a+1
 if cb$="0" gosub scan.wp6
 x=x+1:if x>wc goto scan.wp3
 goto scan.wp2
scan.wp3
 xy=instr(",",xu$):if xy=0 goto scan.wp9
 i$=mid$(xu$,xy-3,3):x=val(i$):if x=0 goto scan.wp9
 xu$=left$(xu$,xy-4)+mid$(xu$,xy+1)
 if (x<11) or (instr(i$,"058,059,060")) goto scan.wp3
 position #1,34,x:input #1,cb$\w$\s,d,v\wa
 a$="room":if cb$="2" a$="shop"
 print i$":"mid$(w$,4)" is with a player, but weapon record shows as in "a$
 input @2"Change weapon record? [Y]/n:"i$:if i$="N" goto scan.wp3
 if cb$="2" a=a-1
 cb$="0":gosub scan.wpA:goto scan.wp3

scan.wp9
 close:print \"Weapon scan complete."
 if zu$<>"" print "Weapon ID #"zu$" held by more than one player"\
 print "Shop variable nw indicates that "nw" weapons are in the shop"
 print "My scan of the weapons list shows that "a" actually are."
 input @2\"Do you wish to change the nw variable? y/[N]:"i$
 if i$<>"Y" goto system.1
 dy$="c:weapons":open #1,dy$:position #1,34,0:print #1,a:close
 print \"Done!":goto system.1

scan.wp6
 i$=right$("00"+str$(x),3):xy=instr(i$,xu$):if xy goto scan.rmv
 print i$": "mid$(w$,4)" listed as with a player, but no player has it"
 input @2"Restore to the room? [Y]/n:"i$:if i$="N" return
 cb$="1":if x<11 cb$="2"
scan.wpA
 position #1,34,x:print #1,cb$\w$\s,d,v\wa:return

scan.rmv
 xu$=left$(xu$,xy-1)+mid$(xu$,xy+4)
 xy=instr(i$,xu$):if xy zu$=zu$+i$+",":goto scan.rmv
 return
;
scan.al
 gosub view.dat:print \"Scanning ally file.."
 zu$="":x=1:xu$="*":dy$="c:spur.allies":open #1,dy$
 dy$="c:spur.users":open #2,dy$
scan.alA
 position #2,130,x
 input #2,n1$,n,i$:if n=0 goto scan.alB
 position #1,78,x:input #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 print x":"n1$": "d1$","a1","h1"\"d2$","a2","h2"\"d3$","a3","h3
 if d1$<>"*" then if h1>0 xu$=xu$+right$("00"+str$(h1),3)+","
 if d2$<>"*" then if h2>0 xu$=xu$+right$("00"+str$(h2),3)+","
 if d3$<>"*" then if h3>0 xu$=xu$+right$("00"+str$(h3),3)+","
scan.alB
 x=x+1:if x>np close:xu$=xu$+"*":goto scan.alC
 goto scan.alA

scan.alC
 x=1:dy$="c:allies":open #1,dy$
scan.alD
 position #1,26,x:input #1,cb$\x1$\x2,x3:if cb$<>"1" gosub scan.alE
 x=x+1:if x<ac+1 goto scan.alD
scan.alH
 xy=instr(",",xu$):if xy=0 goto scan.alG
 i$=mid$(xu$,xy-3,3):x=val(i$):if x=0 goto scan.alG
 xu$=left$(xu$,xy-4)+mid$(xu$,xy+1)
 position #1,26,x:input #1,cb$\x1$\x2,x3
 print \i$": "x1$" is with a player, but ally record shows as free."
 input @2"Change ally record? [Y]/n:"i$:if i$="N" goto scan.alH
 cb$="0":gosub scan.alF:goto scan.alH

scan.alE
 i$=right$("00"+str$(x),3):xy=instr(i$,xu$):if xy goto scan.rmv
 print \i$": "x1$" record shows with a player, but no player has him"
 input @2"Restore to FREE? [Y]/n:"i$:if i$="N" return
 cb$="1"
scan.alF
 position #1,26,x:print #1,cb$\x1$\x2,x3:return
scan.alG
 close:print \"Ally scan complete"
 if zu$<>"" print "Ally ID #"zu$" held by more than one player"
 goto system.1
;
scan.pl
 gosub view.dat
 print \"Checking /RAM spur.user file against c:spur.user.."
 close:open #1,"c:spur.users"
 open #2,"c:spur.users"
 for x=1 to np
 position #1,130,x
 input #1,n1$,sn,pn,cl,cr,hp
 input #1,ps,pt,pi,pe,pw,pd
 input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 input #1,df,sl,sr
 if not sn goto scan.pl2
 position #2,130,x
 input #2,n2$,ys,yp,yl,yr,yh
 input #2,cs,ct,ci,ce,cw,cd
 input #2,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #2,p2$
 print \"Player (Disk,RAM) ="n1$", "n2$"  sn="sn", "ys" pn="pn", "yp
 print "Level= "cl", "yl"   Room= "cr", "yr"   Exp= "ep", "yj
 input @2\"[N]ext, C)opy disk record to RAM, Q)uit :"i$
 if i$="C" gosub scan.pl3
 if i$="Q" x=np
scan.pl2
 next:close
 goto system.1

scan.pl3
 position #2,130,x
 print #2,n1$,sn,pn,cl,cr,hp
 print #2,ps,pt,pi,pe,pw,pd
 print #2,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 print #2,df,sl,sr
 return
;
time
 tt=clock(2):tl=clock(1)
 zm=tt-tl:if zm<1 zm=0
 i$=str$(zm-((zm/60)*60)):i$=right$("00"+i$,2)
 print \"["zm/60":"i$"] ";
 return
;
listmsg
 a=0
lstmsg.1
 a=a+1: print \"c:messages. Message #";a
 gosub rd.msg
 input @2\"Continue? [Y]/n:"i$
 if i$<>"N" goto lstmsg.1
 return
;
messages
 print \"Edit Spur message files."
 input @2"Message number to edit :"i$
 x=val(i$):if x=0 goto system.1
wr.book
 bk$="c:messages":ready bk$
 input #msg(x),n$
 input\"Import text file for message? Y/N:"i$
 if i$="Y" input@2\"Enter file to load (include drive):"a$:if not instr(":",a$) print \"Improper drive:file name!":i$="N"
 edit(0):if i$<>"Y" copy #6,#8
 if i$="Y" open #2,a$:copy #2,#8:close #2
 if not edit(2) goto wr.book3
wr.book2
 input @0\"Edit message? "a$:if a$<>"Y" goto messages
wr.book3
 print \"You may edit or write your message now, 4k max. Do NOT [.a]"

wr.book4
 edit(1):n$="message"
 if edit(2)>3900 print\"Your message is too long, shorten it.":goto wr.book4
 if not edit(2) print #8,"[ Un-readable! ]"
 print \"Saving message..."
 a=msg(x):kill #msg(x):print #msg(x),n$
 copy #8,#6:msg(x)=a:update:goto messages
;spot1
rd.msg
 bk$="c:messages"
 if info(5) print "rd.msg reading ";bk$;" #msg(";a;")"
 ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):return
;
guild.pg
 input @2\"Which guild HQ? 1=Claw, 2=Sword, 3=Fist :"i$
 vv=val(i$):if (vv<1) or (vv>4) goto system.1
 if vv=1 vv=6:ww$="\|/"
 if vv=3 vv=8:ww$="==[]"
 if vv=2 vv=3:ww$="-}--"
 yx$="*ANNEX*":dy$="d:spur.guild":link dy$
;
scn.rst
 if bd poke 35,24
 home:if (not td) print ^
 return
;
ramdrive
; L: must be a valid drive. If  not RAM drive, point it to some unused folder.
 if ra$ = "YES" or ra$="NO" then return
 open #1,"L:ram.txt"
 if mark(1) ra$="NO":else ra$="YES"
 close
 if info(5) print \"info(5): spur.annex.s set RAMDRIVE (ra$) to ["ra$"]":input @2 "Hit [Enter]"i$
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "a:system.seg"
comp.ck
 print " ok..":return
;eg"
comp.ck
 print " ok..":return
;

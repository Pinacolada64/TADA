
; spur.logon.s
; Worked on with Appleworks

;
 public compile
 public quit1
 public quit3
 public return

 store "a:var":clear:recall "a:var"

;.. GUEST account. 
 if un=2 if flag(1)=0 print \"GUEST: Note this account is shared with other guests. If you want to":print "play this game again, you might consider getting a verified account.":input @2 \"Press [Enter] to continue."i$
;aa used to trap carrier drop by hand (groan)
 aa=0
 if info(5) print "info(5): System ID# ["un"]";:input @2":"i$:if i$<>"" un=val(i$):if un=0 un=1
 on nocar goto quit4
 print chr$(12)
 if flag(29)=0 print cl$"[1;33m"
 a=10:gosub messages
 gosub var.set
; rely on load.spur to set these properly..
; dy$=dz$+"items":open #1,dy$:a=mark(1):close:if a dz$=ds$:dw$=dx$
 if flag(32) print "[Drives] ds$="ds$", dw$="dw$", dx$="dx$", dz$="dz$", du$="du$
 dy$=dx$+"spur.data"
 open #1,dy$:a=mark(1):close
 if (a) and (info(5)) then dy$=ds$+"spur.control":link dy$,"configure"
 if a print \"Game Closed!":goto lnk.bbs
 open #1,dy$
 input #1,g$,np,go,oh,ol,og,lg$
 input #1,lc,mc,ic,sc,wc,ac,cg
 input #1,pq,sd,mv,td,bd
 input #1,dh,dl:close
 print "    (Support sub, #6: Spur Support)"
 dy$=dw$+"spur.users":x=1
 zz=0:open #1,dy$
start3
 position #1,130,x
 input #1,n1$,n,pn:if n=un close:goto login
 if n=0 zz=1
 x=x+1:if x>np close:goto new
 goto start3

new
 if zz=0 then if flag(34)=0 print \"Sorry, game is full right now!":goto quit2
 a=9:gosub messages
new_p
 input @0\\"Do you wish to enter the Land? "i$
 if i$="N" goto quit2
 if i$<>"Y" print \"Enter Y or N please..":goto new_p
 push login1
 link ds$+"spur.new"

; *** Login Routine ***

login
 if flag(21) if info(2)=1 zs$=a1$+" with wrong baud rate!":gosub log:print \zs$:goto quit2
 print \"A Wizard greets you and begs you wait. Your status must be verified to pass.."
 gosub tim.read
 gosub rd.user
;calculate elapse time since last player
 a=val(left$(g$,2))*60
 a=a+val(mid$(g$,4,2))
 g$=""+time$
 l=val(left$(g$,2))*60
 l=l+val(mid$(g$,4,2))
 if a>l l=l+1440
 if (not instr("*clone*",lg$)) or (flag(16)=0) goto no.clone
;Clone suspect
 if l-a>30 goto no.clone
 i$="Suspected clone, minutes elapsed ="+str$(l-a)
 gosub add.log
 print \'Suspected Clone Account. Suspected
clone accounts can not play one after
the other. You must wait for a non
suspect to play first..'
 input @2 \"Press [Enter]"i$ :goto quit2

no.clone
 if l-a>60 goto no.last
 if n1$=lg$ if info(5)=0 if info(2) print \"You were the last Adventurer. You must wait till another passes through!":input @2\"Press [Enter]"i$:goto quit2
no.last
 if xp>24 xp=24:print \"Maximum level=24!"
login1
 gosub set.pa:xo=xf:xo$=xf$
 if (not td) text:home:print
 if (not bd) goto login1.5
 poke 35,21
 a$=n1$
 l=len(a$)+12:a=peek(33)-l:a=a/2:l=peek(33)-l:l=l-a
 print #3 @1,22 chr$(45,a)"[ #"right$(" "+str$(pn),4)"-"a$" ]-"chr$(45,l):print #3 @1,1
 gosub tim.chk:gosub screen
;
login1.5
 xt$="":xt=0:zo=10
;..(zo=carrying capacity)
 if (pr=4) or (pr=7) or (pr=8) zo=9
 if (pr=5) or (pr=6) zo=8
 if pr=3 zo=7
; wraith master flag:
 zz$=mid$(zu$,7,1)
 if instr(zz$,"12") zz$=", Wraith Master of Spur!":else zz$="!"
 print \"Welcome "n1$;zz$
 zz=instr("*clone*",lg$)
 if zz lg$=left$(lg$,zz-1)
 print \"The last Adventurer was "lg$
 zz$="The Guild of the "
 if (vv=6) or (vv=7) print \zz$"Claw bids":print "you, 'Welcome!' \|/  (Clan sub: B9)"\
 if (vv=3) or (vv=4) print \zz$"Sword bids":print "you, 'Welcome!' -}---- (Clan sub: B2)"\
 if (vv=8) or (vv=9) print \zz$"Iron Fist bids":print "you, 'Welcome!' ==[] (Clan sub: B29)"\
 print \"Current status:"\
 if vv<3 goto no.guild
; guild follow mode:
 if mid$(zu$,10,1)="1" zz$="WILL":else zz$="WILL NOT"
 print "Your character "zz$" follow other guild members."
no.guild
 if instr(left$(zu$,1),"AB") zz$="OFF":else zz$="ON"
 print "Room description: "zz$
 if mid$(zu$,3,1)="0" zz$="are NOT":else zz$="ARE"
 print "You "zz$" poisoned."
 if mid$(zu$,4,1)="0" zz$="are NOT":else zz$="ARE"
 print "You "zz$" diseased."
 if (vv=2) or (vv=4) or (vv=7) or (vv=9) zz$="ON":else zz$="OFF"
 print "Auto duel: "zz$\
 dy$=dx$+"misc.data":open #1,dy$
 dy$=dw$+"items":open #2,dy$
 if vv>2 position #1,250,pn:input #1,i$\zz$:if i$<>"*" print "You followed "i$" to your current location"\
 for x=209 to 213 step 4:y=ar:if x=213 y=sh
 position #1,250,pn,x:input #1,zz
 if zz if y=0 zz=0:position #1,250,pn,x:print #1,0
 if zz=0 goto no.ar
 position #2,30,zz,2:input #2,n$\a
 if zz>60 print hl$;mid$(n$,3);" HUMMS TO LIFE! "of$;
 if zz=115 ys$=ys$+"*pwr.ar*"
 if zz=116 ys$=ys$+"LAZ.SH"
 xt$=xt$+right$("00"+str$(zz),3)+","
 if left$(n$,1)="A" print "WEARING "mid$(n$,3)
 if left$(n$,1)="S" print mid$(n$,3)" IS READIED"
no.ar
 next:close
 zz$="":zz=0
; reset ring status:
 if not instr("067",xi$) zu$=left$(zu$,1)+"0"+mid$(zu$,3)
; check amulet of life status
 if mid$(zu$,8,1)="1" then if not instr("076",xi$) if not instr("076",ai$) zu$=left$(zu$,7)+"0"+mid$(zu$,9):print \hl$"[ AMULET OF LIFE- GONE!! ]"of$\
 zz$=mid$(zu$,7,1):zz=val(zz$):if zz<2 goto no.wizgl
 print \hl$"Your Wizard's Glow spell has dissipated."of$:if zz=2 zz$="1":else zz$="0"
 zu$=left$(zu$,6)+zz$+mid$(zu$,8)
no.wizgl
 zz$="":if flag(32) print "zu$="zu$
 if a1 lu$=d1$:gosub cln.ally:zz$=lu$:if a2+a3>0 zz$=zz$+" and "
 if a2 lu$=d2$:gosub cln.ally:zz$=zz$+lu$:if a3>0 zz$=zz$+" and "
 if a3 lu$=d3$:gosub cln.ally:zz$=zz$+lu$
 if zz$<>"" print zz$" await you!"
 gosub ply.loc:gosub strings:tm=0
 if (cl=6) and (cr=792) then dy$=ds$+"spur.ship":link dy$
 if cr then dy$=dz$+"spur.misc":i$="travel3":link dy$,"misc"
 dy$=dz$+"spur.shop"
 link dy$
;
cln.ally
 xy$=""
 if instr(">",lu$) xy$="THE GOD ":if instr("+",lu$) xy$="THE GODDESS "
 lu$=xy$+lu$:if instr("|",lu$) lu$=left$(lu$,instr("|",lu$)-1)
 return
;
show.file
 setint(1):copy f$:setint(""):return
;
rd.user
 dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,pn
 input #1,n1$,sn,pn,cl,cr,hp
 input #1,ps,pt,pi,pe,pw,pd
 input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 input #1,df,sl,sr:close
 dy$=dx$+"spur.allies"
 open #1,dy$:position #1,78,pn
 input #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 close
 zz$=left$(n1$,1):zr=instr(zz$,"ABZCZZDZE")
 if zr then vv=zr-1:else vv=val(zz$)
 if zr print \"You slowly awaken from your duel loss..."
 n1$=mid$(n1$,2)
 dy$=dx$+"spur.weapons"
 open #1,dy$:position #1,64,pn
 input #1,xw\xw$:close
 dy$=dx$+"spur.stores"
 open #1,dy$:position #1,44,pn
 input #1,xf\xf$:close
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,pn
 input #1,xi\xi$:close
 dy$=dx$+"ally.items"
 open #1,dy$:position #1,84,pn
 input #1,ai\ai$:close
 dy$=dx$+"spur.monsters"
 open #1,dy$:position #1,44,pn
 input #1,xm\xm$:close
 dy$=dx$+"spur.spells"
 open #1,dy$:position #1,44,pn
 input #1,xs\xs$:close
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,pn
 input #1,zu$:close:if zu$="" zu$="0000000000"
 dy$=dx$+"honor"
 open #1,dy$:position #1,10,pn
 input #1,vk:close:if vk=0 gosub set.honor
 return

wr.user
 if sn=0 goto no.sn
 if vv>0 gosub kickout:if zm setint(1):print \'
============================
Only  Civilians  are allowed
to remain in the Shoppe! You
have been  moved to the room
just outside the shoppe.....
============================'\:setint("")

 if instr("loot",ys$) gosub kickout:if zm setint(1):print \'
==============================
Shop security  tells you  that
they do not allow pick-pockets
to remain in the shop. You are
politely thrown out...........
=============================='\:setint("")

 if (flag(3)+flag(6)+flag(13))>0 gosub kickout:if zm setint(1):print \'
================================
I see you have access to a Guild
sub, but are HIDING  behind  the
title of Civy. SHAME on you! You
are thrown out of the shop......
================================'\:setint("")

no.sn
 zz$=str$(vv):n1$=zz$+n1$:if cl=0 cl=1
 if (len(n1$)>15) then n1$=left$(n1$,15)
 dy$=dx$:gosub wr.user4:dy$=dw$:gosub wr.user4
 dy$=dx$+"spur.allies"
 open #1,dy$:position #1,78,pn
 print #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3:close
 dy$=dx$+"spur.weapons"
 open #1,dy$:position #1,64,pn
 print #1,xw\xw$:close
 dy$=dx$+"spur.stores"
 open #1,dy$:position #1,44,pn
 print #1,xf\xf$:close
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,pn
 print #1,xi\xi$:close
 dy$=dx$+"ally.items"
 open #1,dy$:position #1,84,pn
 print #1,ai\ai$:close
 if xm<=10 goto wr.user3
 x=xm-10
 for a=1 to x
 zz$=rnd$:b=random(xm):if b=0 then b=1
 y=(b*4)-3:l=len(xm$)
 if y=1 then xm$=mid$(xm$,5):goto wr.user2
 if (y+4)>l then xm$=left$(xm$,y-1):goto wr.user2
 xm$=left$(xm$,y-1)+mid$(xm$,y+4)
wr.user2
 xm=xm-1
 next:xm=10
wr.user3
 dy$=dx$+"spur.monsters"
 open #1,dy$:position #1,44,pn
 print #1,xm\xm$:close
 dy$=dx$+"spur.spells"
 open #1,dy$:position #1,44,pn
 print #1,xs\xs$:close
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,pn
 print #1,zu$:close
 if yt$<>"*" a$=mid$(n1$,2):i$="LOGON.STAY":gosub lnk.msc4
 dy$=dx$+"misc.data"
 open #1,dy$:position #1,250,pn
 print #1,"*"\
 if vo>0 if vp<100 position #1,250,pn,17+(vo*3-3):print #1,vp
 close
 gosub wr.honor
 return

wr.user4
 dy$=dy$+"spur.users"
 open #1,dy$:position #1,130,pn
 print #1,n1$,sn,pn,cl,cr,hp
 if (not sn) close:return
 print #1,ps,pt,pi,pe,pw,pd
 print #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 print #1,df,sl,sr:close
 return
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto quit1
 return

tim.read
 dy$=dx$+"spur.time":open #1,dy$
 mt=mv:if mt=0 goto set.time
 position #1,12,un
 input #1,a$,eu
 b$=mid$(" "+date$+" ",2,5)
 print "Last played on '"a$"', Today is '"b$"'"
 if a$<>b$ eu=0
set.time
 close
 if info(5)=0 goto set.1
 eu=0:if mt=0 then ev=3600:return
 ev=mt
 return
;
set.1
 if mt=0 then mt=clock(2)-clock(1):eu=0
 ev=mt-eu
 if ev>(clock(2)-clock(1)) ev=clock(2)-clock(1)
 if ev>0 return
 zs$=a1$+" tried to re-enter Spur after time expired, @"+time$:gosub log
 gosub tim.mess:goto lnk.bbs

tim.mess
 print\'
Alas... the sun has set on yet another adventurer within the Land of Spur. Wake ye early in the morning after a long rest to resume your quest!!!'
 return
;
screen
 print #3 @1,23 "LV:      RM:    |"
 print #3 @1,24 "MV:      EP:    |"
 print #3 @41,23 " Start at "time$
 print #3 @1,21
 return

scn.rst
 if bd poke 35,24
 home:if (not td) print ^
 return
;
quit
 if wz$="WRITE DONE" return
 wz$="WRITE DONE"
 if cr=0 goto quit.a
 if pw<7 then pw=pw+2
 if pi<7 then pi=pi+2
 if ps<10 then ps=ps+2
 if pe<10 then pe=pe+2
 if hp<20 then hp=hp+2
quit.a
 if mv>0 if ex=>ev gosub tim.mess
 print \'SPUR says hold whilst your adventure is written in the BOOK of SPUR....
'
 dy$=dx$+"spur.data"
 open #1,dy$
 i$=n1$:if flag(16) i$=i$+"*clone*"
 a$=""+time$
 print #1,a$,np,go,oh,ol,og,i$
 print #1,lc,mc,ic,sc,wc,ac,cg
 print #1,pq,sd,mv,td,bd
 print #1,dh,dl:close
 if (not mv) goto quit.b
 eu=eu+ex:a$=left$(""+date$,5):if left$(cm$,5)<>a$ then eu=0
 dy$=dx$+"spur.time":open #1,dy$
;.. eu=mt: set time to full limit. Prevents multiple plays
;.. per day (unless player gets killed)
;----------------------
;.. Q)uit Spur while on line. Lose remaing time
 if sn>0 eu=mt
;.. Suicide. Lose remaining time
 if sn=0 if z=2 eu=mt
 position #1,12,un
 print #1,a$,eu
 close

quit.b
 gosub wr.user
 zs$=left$(date$,5)+" "+time$+"#"+left$(str$(un)+" ",4)+a1$+"/"+mid$(n1$,2)+ ": "+str$(ex/60)+" min."
 if wn zs$=zs$+" [WON GAME]"
 if info(0)+info(5)=0 zs$=zs$+" [CARRIER LOST]":if instr("=",ph$) zs$=zs$ +"[LONG DISTANCE]"
 if (sn=0) and (z=2) then zs$=zs$+" [SUICIDE, TIMER MAXED]"
 if eu<>mt zs$=zs$+" [TIMER NOT MAXED]"
 gosub log:print \"It is written!":return

quit1
 on nocar goto quit4
 gosub quit
quit2
 gosub scn.rst:goto lnk.bbs

quit3
 gosub quit:goto quit5
quit4
 if n1$<>"" i$="SPUR.LOGON":gosub quit
quit5
 if (left$(i$,5)<>"SPUR.") and (info(0)+info(5)=0) then i$="SPUR.UNKNOWN"
 if left$(i$,5)="SPUR." gosub drp.msg
 gosub scn.rst:set zz$="":recall "a:var"
 link "a:logoff.seg","term1"
;
ply.loc
 print \"(Just a sec..)"\
 dy$=dw$+"spur.users"
 ta$=">:":tb$=">:":tc$=">:"
 td$=">:":te$=">:":tf$=">:":th$="> :"
 x=1:open #1,dy$
ply.loc1
 if x=pn goto ply.loc2
 position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,yi,yi,yi,yw,yw,yd
 if (yr=0) or (ys=0) goto ply.loc2
 if len(n2$)>15 goto ply.loc2
 xu$=str$(yr):zt$=ta$
 if yl=1 i$=ta$:gosub ply.loc5:ta$=i$
 if yl=2 i$=tb$:gosub ply.loc5:tb$=i$
 if yl=3 i$=tc$:gosub ply.loc5:tc$=i$
 if yl=4 i$=td$:gosub ply.loc5:td$=i$
 if yl=5 i$=te$:gosub ply.loc5:te$=i$
 if yl=6 i$=th$:gosub ply.loc5:th$=i$
 if yl=1 then if zt$=ta$ xu=len(tf$):if xu<221 gosub ply.loc4:gosub ply.loc3 :tf$=tf$+xx$+zz$
ply.loc2
 x=x+1:if x>np close:return
 goto ply.loc1
ply.loc3
 zz$=str$(x):xv$="000"+zz$:zz$=right$(xv$,3):zz$=zz$+":"
 if len(zz$)>4 pop:goto ply.loc2
 return
ply.loc4
 xx$=xu$+"="+n2$+":":if len(xx$)>21 pop:goto ply.loc2
 return
ply.loc5
 xu=len(i$):if xu<221 gosub ply.loc4:gosub ply.loc3:i$=i$+xx$+zz$
 return
;
drp.msg
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$\mid$(n1$,2)" DROPPED CARRIER IN "i$
 if mw print #1,"IN FRONT OF "m$". HP="hp:if hp<10 print #1,"[ SPUR ACCESS REMOVED! ]":flag(12)=1
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 return
;
advent
 dy$=dz$+"spur.main":link dy$
;
lnk.msc4
 dy$=dz$+"spur.misc4":link dy$
;
lnk.bbs
 clear:recall "a:var":link yw$,yy$

return
 return
;
add.log
 open #1,"a:add.log":append #1
 print #1,"Spur.logon "i$" @"time$:close
 return
;
strings
 if flag(32) print "Strings: 1]"ta$\"2]"tb$\"3]"tc$\"4]"td$\"5]"te$\"6]"th$\\"Aux 1]"tf$
 return
;
log
 open #1,"c:spur.log":append #1:print #1,zs$:close:return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):print of$:return
;
kickout
 zm=0:if cl<>6 if cr>0 return
 if cl=6 if cr>0 if cr<>792 return
 if mm=0 return
 zm=1:if cl=6 if cr=0 cr=584:return
 cr=1:return
;
var.set
 pn=0:sn=0:ew=clock(1):wa=0:ma=0:pa=0:sl=0:tm=0
 vm=0:vn=0:vo=0:vp=0:vt=0:vu=0:vv=0:vw=0
 xw=0:zm=0:zn=0:zo=0:zp=0:zq=0:zu=0:zv=0
 dc$="":n1$="":i$="":m$="":yt$="*":dr$="":du$=dx$
 zv$="":ys$="":wr$="":wx$="":wy$="":wz$=""
 return
;
set.pa
 pa=ps+pd+pt+pi+pw+pe:pa=pa mod 10
 return
;
set.honor
 vk=1000
 if (pr=2) or (pr=8) then vk=750
 if (pr=3) or (pr=4) then vk=1250
wr.honor
 dy$=dx$+"honor"
 open #1,dy$:position #1,10,pn
 print #1,vk:close
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
 goto quit4
;

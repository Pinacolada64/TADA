
 public auto.c
 public compile

 if un=1 print "spur.duel2-";:gosub comp.ck

 if i$="SPECIAL" gosub special:goto duel.return
 if i$="GROVEL" goto grovel
 if i$="DUEL" goto duel
 if i$="hell" goto hell
 if i$="hell2" goto hell2
 if i$="sendmail" goto sendmail
 i$="Bad value of i$ in spur.duel2.s ->"+i$
 print \i$:gosub add.lg:goto lnk.gm.s

duel
 on nocar goto dropped
 gosub clr.var:zm=0:vy=0:vq=0
challenge
 zv$="abortduel"
 if instr("+",ww$) print \"You are in a FREE FIRE zone! ('+')"
 print \'
Adventurers in  current  room, followed by BAD HOMBRE  rating  (BHR). Note: BHR
does NOT include weapon factors:'\
 print "[ "n1$" ] BHR = "hp+(xp*2)+((pe+pd+ps)/2)+((sh+ar)/4)
 dy$=dx$+"spur.users":open #1,dy$
 free:tg$=ta$:ch=0:gosub ply.locD
 if cl=1 then if tf$<>">:" tg$=tf$:gosub ply.locD
 close:wx$="":gosub clr.var:goto chlng2

ply.locD
 vs=cl:vx=cr
 xu$="":zx$=":"+str$(cr)+"=":zt=len(zx$)
 gosub ply.loc8
 yy=instr(zx$,xu$):if not yy return
ply.loc1
 yw=zt+yy:xz=0
ply.loc2
 xz=xz+1:if mid$(xu$,xz+yw,1)=":" goto ply.loc3
 if xz+yw>(len(xu$)) return
 goto ply.loc2
ply.loc3
; Here: x=game id number
 x=yw+xz+1:zz$=mid$(xu$,x,3):x=val(zz$)
 ch=1:print "#"right$("  "+str$(x),3)", ";
 position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 print mid$(n2$,2)": ";
 yg=(yg-1)*7+1:yi=(yi-1)*8+1
 i$="Wizard Druid  FighterPaladinRanger Thief  Archer AssasinKnight "
 i$=mid$(i$,yg,7):yg=instr(" ",i$):if yg i$=left$(i$,yg-1)
 print i$" ";
 i$="Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc     Half-Elf"
 i$=mid$(i$,yi,8):yi=instr(" ",i$):if yi i$=left$(i$,yi-1)
 print i$", BHR = ";
 zw$=left$(n2$,1):yz=val(zw$):gosub mark
 if yz=3 zm=zm+1
 if yz=6 vy=vy+1
 if yz=8 vq=vq+1
 print yh+(yn*2)+((ce+cd+cs)/2)+((ye+yf)/4)". "zw$;
 i$=left$(n2$,1):if val(i$)=0 then if i$<>"0" print " (Unconscious)";
 print "":xu$=mid$(xu$,yw+1):yy=instr(zx$,xu$):if yy goto ply.loc1
 return

ply.loc8
 if cl=1 xu$=tg$
 if cl=2 xu$=tb$
 if cl=3 xu$=tc$
 if cl=4 xu$=td$
 if cl=5 xu$=te$
 if cl=6 xu$=th$
 return
;
chlng2
 if not ch print \"No other Adventurers in this room!"\:goto lnk.gm.s
 input @2\"Challenge which Adventurer (CR=Abort) :"i$
 if i$="" goto lnk.gm.s
 x=val(i$):xu=x:if (x<1) or (x>np) print \"Enter number from 1 to "np:goto chlng2
 if x=pn print \"You CANNOT Challenge yourself!":goto chlng2
 au=0:dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$:close:vz=yh
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,x
 input #1,zt$:close
 if (cl<>yl) or (cr<>yr) print \"That Adventurer is NOT here!":goto chlng2
 xx$=left$(n2$,1):yz=val(xx$)
 if yz=0 then if xx$<>"0" print\"You can't duel unconcious people!":goto chlng2
 if instr("+",ww$) goto free.a
 if yz=0 then if (vv<1) or(vv>2) print \"You can not duel Civies!!":goto chlng2
 if yz=0 print \"'YOU SCONDREL! ATTACKING A POOR CIVILIAN!'"
free.a
 gosub mark:xx$=mid$(n2$,2):xy=0
 if yz=3 xy=zm-1
 if yz=6 xy=vy-1
 if yz=8 xy=vq-1
 if instr("+",ww$) goto free.b
 if vv=0 then if yz<>1 print \"CIVYS CAN ONLY DUEL OUTLAWS!":goto chlng2
free.b
 i$="!":if xy>1 i$="s!"
 if xy>5 xy=5:print "(Only 5 Guild members can lend support)"
 zu=xy:xv=xy:if xy>0 print xx$" is supported by "xy" Guild member"i$
 zz=hp+(xp*2)+((pe+pd+ps)/2)+((sh+ar)/4):zz=zz*10
 yy=yh+(yn*2)+((ce+cd+cs)/2)+((ye+yf)/4)
 zz=zz/yy:zz=zz-xy:if zz<1 zz=0
 vu=0
 if vv=3 or vv=4 then vu=zm
 if vv=6 or vv=7 then vu=vy
 if vv=8 or vv=9 then vu=vq
 i$=yt$:z=0
follow
 a=instr("=",i$):if a=0 goto follow.a
 zs$=mid$(i$,2,1):if not instr(zs$,"CDE") vu=vu+1:if vu>5 vu=5
 z=z+1:i$=mid$(i$,a+4):if instr("=",i$) then if z<6 goto follow
follow.a
 zz=zz+vu:if zz<13 goto follow.b
 if vu>(xy+1) print \xx$" looks scornfull, and speaks;":print '
"Courage comes easily when one is followed by so many fellow bullies! Return
when thou is ready to do battle in a fair manner, and I shall fight!"':goto follow.b
 print \xx$" says: 'I respectfully DECLINE your Challenge!'"
follow.b
 if zz<8 gosub set.rvng
 vu=0:zs$="":xz$="":if zz>12 goto ck.rvng

auto.c
 on nocar goto dropped
 gosub clr.var
 gosub opnt.wp:if hh gosub hndtohnd
 dy$=ds$+"spur.duel":link dy$,"auto.c"
; ^ link ok
;
opnt.wp
 print \xx$" PONDERS..";
 yo=yg:yq=yi
 dy$=dx$+"spur.weapons"
 open #1,dy$
 position #1,64,yp
 input #1,c\i$:close
 if c=0 print \xx$" has no Weapons!":hh=1:return
 dy$=dx$+"weapons":open #1,dy$
 yt=-10:for e=1 to c:print ".";
 y=(e*4)-3:a=val(mid$(i$,y))
 position #1,34,a,2
 input #1,w$\w1,w2\w5
 n$=mid$(w$,4):zw=w5:gosub special
 if (zt+zs)>yt then yt=zt+zs:cw$=w$:w3=w1:w4=w2:wa=w5
 next:close:print ""
 cw$=mid$(cw$,4):n$=cw$:zw=wa:gosub special:xy=xy+zt:xv=xv+zs
 gosub set.hh
 if cw$="DEATH AMULET" gosub c.amulet
 w4=w4*5/10:x=p2*7/10:w4=w4+x
 w3=(w3+p4)/2
 return
 
c.amulet
 gosub opnt.itm:w4=30:if instr("076",i$) w4=15:print"("xx$" has BOTH Amulets!)"
 gosub rnd.100z
 if z<w4 print \xx$" is zapped by the Death Amulet as it is readied!":w4=4:h=1:return
 w4=30:print \xx$"'S Death Amulet glows strangely.."
 if instr("076",xi$) print \"Your Amulet of Life FLARES in defiance!":w4=10 :else print "(Too bad you don't have the Amulet of Life!)"
 return
;
hndtohnd
 print \xx$' says: 
I fear you not, and would gladly do battle with you, but as you see, I have
no weapons!'
 input @0\"Wilst Thou fight me hand to hand? "i$:if i$<>"Y" pop:goto lnk.gm.s
 wr$="FISTS":cw$="FISTS":xu$="FISTS":gosub set.hh:wd=p1:w4=p2:ws=p3:w3=p4
 vu=4:print "Neither has initiative in fisty-cuffs"
 return
;
set.hh
 p1=ps+pd+pt+pe:p1=p1/10
 p2=cs+cd+ct+ce:p2=p2/8
 if p1>9 then a=p1-9:p1=9:p2=p2-a
 if p2>9 then a=p2-9:p2=9:p1=p1-a
 if p1<3 then p1=3
 if p2<3 then p2=3
 
 p3=pw+pi:p3=p3/4
 p4=cw+ci:p4=p4/4
 if p3>9 then a=p3-9:p3=9:p4=p4-a
 if p4>9 then a=p4-9:p4=9:p3=p3-a
 if p3<5 then p3=5
 if p4<5 then p4=5
 return
;
opnt.itm
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,yp
 input #1,z\i$:close:return
;
grovel
 print \"Writing in news file.."
 zx$="OUTLAW":if vv=0 zx$="CIVY"
 if (vv=6) or (vv=7) zx$="\|/"
 if (vv=3) or (vv=4) zx$="-}----"
 if (vv=8) or (vv=9) zx$="==[]"
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 xv$=": GROVEL":if zv$<>"" xv$="=AUTODUEL="
 print #1, left$(date$,6)yr$" "time$;xv$
 print #1, zx$" "n1$", GROVELED BEFORE"
 if zw$<>"ENFORCER" print #1, zw$" ";
 print #1, xx$", IN "ww$
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 zz$=rnd$:if random(100)>50 print \"In your haste to depart, you dropped your gold sack!":g1=gh:g2=gl:gh=0:gl=0:gosub prt.gold
 ready dr$:zv$="":goto lnk.gm.s
;

hell
 print \"YOU HAVE VANQUISHED "xx$" !!!!"
 if hp<15 hp=15
 yb=yb+250:if yz=1 yb=yb+250
 if zv$<>"" yb=yb+250
 if xx$="THE ENFORCER" then if cw$="SUN-SWORD" yb=1000
chk.gld1
 if yb=>10000 then ya=ya+1:yb=yb-10000:goto chk.gld1
 g1=ya:g2=yb:gosub prt.gold:print "You are now $"gd$" in gold richer!":gh=gh+ya:gl=gl+yb:ya=0:yb=0
 if yz=1 print "(Including 250 gold bounty on Outlaws!)"
 if zv$<>"" print "(Including 250 bonus for winning AUTODUEL)"
 if gl=>10000 then gl=gl-10000:gh=gh+1
 yh=15:if sx then sr=0:sx=0
 goto wr.stat

hell2
 yh=vz:print \"You have been vanquished by "xx$" !":hp=15
 gl=gl+250:if (vv=1) or (vv=2) gl=gl+250
chk.gld2
 if gl=>10000 then gh=gh+1:gl=gl-10000:goto chk.gld2
 yc=yc+gh:yd=yd+gl:if yd=>10000 then yd=yd-10000:yc=yc+1
 g1=gh:g2=gl:gh=0:gl=0:gosub prt.gold
 print "As is his right, he has taken your gold!"
 print "(Gold transferred to his bank account..)"

wr.stat
 if instr("random",wx$) goto news
 if ch gosub uncon
;Restore opponent stats except for n2$ and gold variables (ya,yb,yc,yd)
 dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,yp
 input #1,p2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ye,ye,ye,ye,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$
 position #1,130,yp
 print #1,n2$,ys,yp,yl,yr,yh
 print #1,cs,ct,ci,ce,cw,cd
 print #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 print #1,p2$
 close

sendmail
 if instr("random",wx$) goto news
 if ys=0 ys=1
 if info(0)=0 goto sndmail3
 wx$="":print \"Do you wish to include a comment in the note to "xx$"?"
sndmail4
 input @0"Y/N :"i$
 if not instr(i$,"YN") print \"Enter Y or N please!"\:goto sndmail4
 if i$="N" goto sndmail3
sndmail5
 x=edit(3):edit(3)=40
 print "Enter comment now, 40 chr max:" \"....!....!....!....!....!....!....!....!"
 input @3 wx$:edit(3)=x
sndmail3
 dy$=dm$+"mail":ready dy$:edit(0)
 if info(6)<29 wx$="":goto linkgame
 print #msg(ys),sn:
 print #6," []=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 if zv$="" print #6,  " ** RESULT FROM A CHALLENGE IN SPUR **"
 if zv$<>"" print #6, " * RESULT FROM YOUR AUTODUEL IN SPUR *"
 print #6,\" Date -> "date$" "left$(time$,8)\
 if yx$<>"" print #6,"You were attacked in "ww$:print #6,"by "n1$", who then ran away!":goto sndmail2
 if ch then print #6,"You were defeated by "n1$:else print #6,"You were victorious over "n1$
 print #6,"in a Duel in "ww$
 if ch then print #6,n1$" was awarded "gd$" gold!":else print #6,"You won "gd$" gold!":print #6,"(Gold transferred to your bank account)"
 if ch then print#6, \"You were stripped of all your gold!"
sndmail2
 if wx$<>"" print#6, \"COMMENT FROM "n1$":":print#6,"'"wx$"'":wx$=""
 if xz$="revenge" print #6,"(Eligible for revenge duel)"
 if info(0)+info(5)=0 print #6, "[Carrier lost]"
 print #6," []=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 copy #8,#6
 print #msg(ys),chr$(4);chr$(0);
 msg(ys)=1:update
;
news
 print \"Writing in news file.."
 if cw$="FISTS" xu$="FISTS"
 zx$="OUTLAW":if vv=0 zx$="CIVY"
 if (vv=6) or (vv=7) zx$="\|/"
 if (vv=3) or (vv=4) zx$="-}----"
 if (vv=8) or (vv=9) zx$="==[]"
 if instr("random",wx$) zw$=""
 xv$=": SPORT DUEL":if zv$<>"" xv$=": AUTODUEL"
 if xz$="revenge" xv$=": REVENGE DUEL"
 if xu$="" xu$="SOME WEAPON"
 if cw$="" cw$="SOME WEAPON"
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, date$" "time$"--"xv$
 print #1, zx$" "n1$", WITH "xu$;
 if zv$="" print #1, ", VS":else print #1, \"       [] CHALLENGED BY []"
 print #1, zw$" "xx$", WITH "cw$
 if yx$<>"" print #1,"IN "ww$". "yx$:goto bttle.1
 if ch then print #1,"IN "ww$". "n1$" WON!":else print #1,"IN "ww$". "xx$" WON!"
 if info(0)+info(5)=0 print #1,"=> "n1$" BROKE THE CONNECTION <="
bttle.1
 gosub fllw.msg
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
;
guild
 if instr("random",wx$) wx$="":goto linkgame
 if (vv<3) or (yz<3) goto personal
 if (vv=3) or (vv=4) then if yz=3 goto personal
 if (vv=6) or (vv=7) then if yz=6 goto personal
 if (vv=8) or (vv=9) then if yz=8 goto personal
 print \"Updating Guild records.."\:yy=0
 if (vv=3) or (vv=4) yy=1
 if (vv=6) or (vv=7) yy=2
 if (vv=8) or (vv=9) yy=3
 if yy=0 goto personal
 dy$=dx$+"guild.standings":open #1, dy$
 position #1,32,yy:input #1,zz,yw:if yx$<>"" yw=yw+1:goto guild.a
 if ch zz=zz+2:else yw=yw+2
guild.a
 position #1,32,yy:print #1,zz,yw:if yz=3 yy=1
 if yz=6 yy=2
 if yz=8 yy=3
 position #1,32,yy:input #1,zz,yw:if yx$<>"" zz=zz+1:goto guild.b
 if ch yw=yw+2:else zz=zz+2
guild.b
 position #1,32,yy:print #1,zz,yw:close
personal
 print \"Updating personal duel records.."
 yy=un:gosub read.a1$
 if yx$<>"" g0=g0+1:goto pers.a
 if ch g9=g9+2:goto pers.a
 g0=g0+2
pers.a
 zz=pn:gosub writ.a1$
 yy=ys:gosub read.a1$
 if yx$<>"" g9=g9+1:goto pers.b
 if ch g0=g0+2:goto pers.b
 g9=g9+2
pers.b
 zz=yp:gosub writ.a1$
 if zt$="CARRIER LOST" goto drop.1
 dp=1:if yx$<>"" goto linkflee
 goto linkgame
;
read.a1$
 dy$=dx$+"spur.a1$":open #1,dy$
 position #1,64,yy
 input #1,g5,g6,g7,g8,g9,g9,g0
 close:return
;
writ.a1$
 dy$=dx$+"spur.a1$":open #1,dy$
 position #1,64,yy
 print #1,g5,g6,g7,g8,zz,g9,g0
 close:return
;
prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
;
mark
 zw$="CIVY"
 if (yz=1) or (yz=2) yz=1:zw$="OUTLAW"
 if (yz=6) or (yz=7) yz=6:zw$="\|/"
 if (yz=3) or (yz=4) yz=3:zw$="-}----"
 if (yz=8) or (yz=9) yz=8:zw$="==[]"
 return
;
uncon
 if instr("random",wx$) return
 xv$="":z=0
 if cl=1 xv$=ta$:if not instr(xx$,xv$) xv$=tf$:z=1
 if cl=2 xv$=tb$
 if cl=3 xv$=tc$
 if cl=4 xv$=td$
 if cl=5 xv$=te$
 if cl=6 xv$=th$
 if xv$="" return
 yy=instr(xx$,xv$):if not yy return
 a$="ABBCCCDDEE":zz$=mid$(a$,yz+1,1)
 a$=mid$(xv$,yy):xv$=left$(xv$,yy-2)+zz$+a$
 n2$=zz$+xx$
 if cl=1 then if z=0 ta$=xv$
 if cl=1 then if z=1 tf$=xv$
 if cl=2 tb$=xv$
 if cl=3 tc$=xv$
 if cl=4 td$=xv$
 if cl=5 te$=xv$
 if cl=6 th$=xv$
 return
;
special
; (zw = wa, weapons class)
 zt=0:zs=0:zz$=n$:n$="    "+n$:n$=right$(n$,4)
 if yo=1 then if instr(n$,"BALL,TAFF,BOLT") zt=3:zs=2:goto spec.1
 if yo=1 zs=-2:if instr(n$,"GGER,NIFE") zt=1:zs=2
 if yo=2 then if instr(n$,"ABRE,LING,ELIN,CLUB,PEAR,TAFF,TAKE, BOW,ILUM") zt=2:zs=2
 if yo=3 zt=2:zs=1:if zw=8 zt=0:zs=-1
 if yo=4 zs=1:if zw=8 zs=-1
 if yo=5 then if instr(n$,"SBOW,WORD") zt=1:zs=1
 if yo=5 then if zw=5 zt=-1:zs=-1
 if yo=6 then if zw=3 zt=1:zs=1:goto spec.1
 if yo=6 zs=-1
 if yo=7 then if instr(n$,"SBOW, BOW") zt=2:zs=2
 if yo=7 then if (zw=2) or (zw=5) zt=-1:zs=-1
 if yo=8 then if instr(n$,"LAWS,NIFE,ABRE,GGER") zt=2:zs=1
 if yo<>9 goto spec.1
 if instr(n$,"WORD,ANCE,ABRE") zt=2:zs=3
 if n$="IBUR" zt=3:zs=4
 if zw=8 zt=0:zs=-1
spec.1
 if yq=1 then if instr(n$,"GNUM,OWER,POON, GUN,SKET,NNON, UZI,MITE,ASER,IFLE") zs=zs+1
 if yq=2 then if instr(n$,"CLUB,MMER,KLES")zt=zt+3
 if yq=3 then if instr(n$,"NIFE,GGER")zt=zt+1:zs=zs+2
 if yq=4 then if instr(n$," BOW")zt=zt+1:zs=zs+1
 if yq=5 then if instr(n$,"LING") zt=zt+1:zs=zs+2
 if yq=5 then if zw=5 zt=zt+1:zs=zs+1
 if yq=6 then if instr(n$,"GGER,NIFE,TTLE") zt=zt+1:zs=zs+2
 if yq=7 then if instr(n$,"EAXE,KAXE,CHET,SBOW, AXE") zt=zt+1:zs=zs+2
 if yq=8 then if instr(n$,"NIFE,GGER, UZI,KLES") zt=zt+2
 if yq=8 then if instr(n$,"GNUM,OWER,POON, GUN,SKET,NNON, UZI") zs=zs+2
 if yq=9 then if instr(n$,"SBOW, BOW,WORD") zs=zs+1
;zw=8 or zw=1 is missile/energy weapons, give bonus for ammo adds.
 if (instr("STORM",zz$)) or (zw=8) or (zw=1) then if (zt+zs)>0 zt=zt+1:zs=zs+1
 return
;
clr.var
 wx$="":xu$="":cw$=""
 yx$="":hh=0:wr$="":sx=0:zy$="":zs$=""
 zt=0:zs=0:zq=0:return
;
rnd.100z
 zz$=rnd$:z=random(1000):z=z/10+1:if z>100 z=1
 return
;
ck.rvng
 x=un:gosub rd.rvng:a$=right$("000"+str$(ys),3)+","
 if not instr(a$,xz$):goto chlng2
 print \"'TOUGH NUGGIES!!' You scream! 'Revenge is mine!!'"
 l=len(xz$):if l=4 xz$="":goto ck.2
 y=instr(a$,xz$)
 if y=1 then xz$=mid$(xz$,5):goto ck.2
 if (y+4)>l then xz$=left$(xz$,y-1):goto ck.2
 xz$=left$(xz$,y-1)+mid$(xz$,y+4)
ck.2
 gosub wt.rvng:xz$="revenge":goto auto.c
;
wt.rvng
 dy$=dx$+"revenge":open #1,dy$
 position #1,130,x:print #1,xz$:close
 if zy=1 print "wt.rvng="xz$
 return
;
rd.rvng
 dy$=dx$+"revenge":open #1,dy$:position #1,130,x
 input #1,xz$:close
 if zy=1 print "rd.rvng="xz$
 return
;
set.rvng
 x=ys:gosub rd.rvng:if len(xz$)>124 return
 a$=right$("000"+str$(un),3)+",":if instr(a$,xz$) return
 print \"(Revenge flag being set!)"
 xz$=xz$+a$:goto wt.rvng
;
fllw.msg
 i$="MEMBER":if zv>1 i$="MEMBERS"
 if zv>0 print #1,n1$" SUPPORTED BY "zv" GUILD "i$
 i$="MEMBER":if zu>1 i$="MEMBERS"
 if zu>0 print #1,xx$" SUPPORTED BY "zu" GUILD "i$
 return
;
linkflee
 zv$="":wr$="":zq=0:dy$=dz$+"spur.main":ready dr$:link dy$,"flee2"
; ^ link ok
dropped
 i$="SPUR.DUEL2-A":dy$=ds$+"spur.logon":link dy$,"quit3"
; ^ link ok
drop.1
 dy$=ds$+"spur.logon":link dy$,"quit3"
; link ok
; link back if no duel, or if dueling spur
lnk.gm.s
 zv$="":dy$=dz$+"spur.main":link dy$
;
duel.return
 dy$=ds$+"spur.duel":link dy$,"return"
; ^ link ok
linkgame
 if info(0)+info(5)=0 i$="SPUR.DUEL2-B":goto drop.1
 if sx goto linkflee
 zq=0:if zv$<>"abortduel" then wr$=""
 dy$=dz$+"spur.main"
 ready dr$:if zv$="abortduel" then zv$="":link dy$
 zv$="":dy$=dz$+"spur.misc":i$="travel3":link dy$,"misc"
; ^ link ok
add.lg
;.. i$=log message
 open #2,"a:add.log":append #2
 print #2,"Spur.duel2[] "i$" @"time$:close #2:return
;
compile
 if un=1 print \"Compiled":link "k:system.seg"
comp.ck
 print " ok":return
;

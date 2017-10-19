
;... spur.misc9.s
;... modified with Appleworks

 on nocar goto dropped
 public compile
 xu$="[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 if flag(32) print "spur.misc9-";:gosub comp.ck
 if i$="TRACK" store "a:spur.var":gosub track:recall "a:spur.var":goto advent
 if i$="FREE.ALLY" gosub fre.ally:goto comb.ret
 if i$="SAC.ALLY" gosub sac.ally:goto comb.ret
 if i$="MAD.GD" gosub mad.gd:goto comb.ret
 if i$="LOOT" goto loot
 if i$="CLR.SHIELD" gosub clear.sh:goto comb.ret
 if i$="CLR.ARMOR" gosub clear.ar:goto comb.ret
 i$="Bad value of i$ in spur.misc9! i$="+i$:print \i$
 gosub add.log:goto advent
;
clear.sh
 x=217:y=213:xx$="X4X51213234556"
 goto clear.1

clear.ar
 x=233:y=209:xx$="X2X31024284657"
clear.1
 dy$=dx$+"misc.data"
 open #2,dy$
 position #2,250,pn,y
 input #2,i
 position #2,250,pn,y
 print #2,0
 if i>60 close:print \hl$"ZZZZZZTT!!"of$:return
 i$=right$("X"+str$(i),2)
 xx=instr(i$,xx$)
 if xx=0 i$="Error in clear.1 i$="+i$:close:goto add.log
 position #2,250,pn,x:input #2,a$
 if len(a$)<>14 a$="00000000000000"
 if flag(32) print "a$="a$
 if xx=1 a$="00"+mid$(a$,3):goto store.1
 if xx=13 a$=left$(a$,12)+"00":goto store.1
 a$=left$(a$,xx-1)+"00"+mid$(a$,xx+2)
store.1
 if flag(32) print "a$="a$
 position #2,250,pn,x:print #2,a$
 close
 return
;
track
 if cl>5 print \"This is a trackless land..":return
 zy$="":zz$="":dy$=dw$+"spur.users"

;.. Is there a TRACKER ally?
 lu$="":if instr("&",d1$) lu$=d1$
 if instr("&",d2$) lu$=d2$
 if instr("&",d3$) lu$=d3$
 if lu$<>"" gosub cln.ally

 input @2\"Track who? ID#, (?=list) :"i$
 if i$="" or i$="Q" return
 if i$="?" gosub plr.list:goto track
 x=val(i$)
 if (x<1) or (x>np) print \"Enter from 1 to "np", or ? for list, or nothing to abort":goto track
;.. b3=target room, ri=rooms per row, nr=total number rooms
;.. b5=target class, b6=target race, b7=target level
 open #1,dy$:position #1,130,x
 input #1,n$,l1,b1,b2,b3,b4
 input #1,b5,b5,b5,b5,b5,b5
 input #1,b5,b5,b5,b5,b5,b5,b5,b6,b7,b7,b7,b7
 input #1,b8,b8,b8:close
 if not l1 print \"No player with this ID number":goto track
 if cl<>b2 goto no.track
 i$=""
; look north
 yw=(cr/ri)-(b3/ri):if yw<1 yw=0:else i$="NORTH"
; look south
 yx=(b3/ri)-(cr/ri):if yx<1 yx=0:else i$="SOUTH"
 a=((b3*10)/ri)-((b3/ri)*10):a=((a*ri+5)/10)
 b=((cr*10)/ri)-((cr/ri)*10):b=((b*ri+5)/10)
; look east
 yy=a-b:if yy<1 yy=0:else i$=i$+"EAST"
; look west
 yz=b-a:if yz<1 yz=0:else i$=i$+"WEST"
 if flag(32) print "n="yw" s="yx" e="yy" w="yz
;.. yw=distance to target
 yw=yw+yx+yy+yz
;.. base tracking range
 yx=12+xp
;.. Additions
 if pc=1 yx=yx-2
 if pc=5 yx=yx+5
 if (pc=6) or (pc=8) yx=yx+2
 if (b5=3) or (b5=9) yx=yx+2
 if lu$<>"" yx=yx+5

;.. Deductions
 if b6=4 yx=yx-2
 if (b6=5) or (b6=6) yx=yx-3
 if b6=3 yx=yx-5
 yx=yx-b7:if yx<1 yx=0
;.. yx=tracking range (distance target can be detected)
 if flag(32) print "Tracking range="yx", target range="yw
 if yx<yw goto no.track
 if yw<1 print mid$(n$,2)" IS HERE!!":return
 a$="VERY FRESH!"
 if yw*4>yx   a$="FAIRLY FRESH"
 if yw*4>yx*2 a$="NOT VERY FRESH"
 if yw*4>yx*3 a$="RATHER OLD"
 if lu$<>"" zz$="'HERE ARE TRACKS THAT ARE "+a$+", LEADING TO THE "+i$+"'"
 if lu$=""  zz$="YOU SEE TRACKS THAT ARE "+a$+", LEADING TO THE "+i$
 goto end.track

no.track
 zz$="NO TRACE OF "+mid$(n$,2)+" IS DETECTABLE.."
 if lu$<>"" zz$="'"+zz$+"'"

end.track
 if lu$<>"" zy$=lu$+" INSPECTS THE GROUND":else zy$="YOU INSPECT THE GROUND"
 zy$=zy$+" FOR SIGNS OF "+mid$(n$,2)+"..."
 print \zy$;:for x=1 to 1000:if not (x mod 250) print ".";
 next:print \zz$
 return
;
plr.list
 print \"List of players in Game"
 x=1:a=1:open #1,dy$
 gosub plrlist5

plrlist1
 position #1,130,x
 input #1,n$,l1,b1,b2,b3,b4
 setint(1)
 if (not l1) goto plrlist4
 setint(1)

plrlist2
 n$=mid$(n$,2)
 print right$("  "+str$(b1),3)"  ";
 print left$(n$+"               ",14)

plrlist4
 x=x+1:if (x>np) or (key(1)) close:return
 goto plrlist1

plrlist5
 print \\" #   Adventurer"
 print "---  ---------------"
 return
;
sac.ally
 i$="":x=0
 if a1>0 i$=d1$:x=h1:d1$="*":a1=0:h1=0:goto sac.a
 if a2>0 i$=d2$:x=h2:d2$="*":a2=0:h2=0:goto sac.a
 if a3>0 i$=d3$:x=h3:d3$="*":a3=0:h3=0
sac.a
 if i$="" return
 wx$=i$:a=0:zt$="":i$="":lu$=wx$:gosub cln.ally
 if instr(">",wx$) print \lu$" SEEING YOU ARE ABOUT TO DIE, WISKS YOU AWAY!" :print \"'GOODBY "n1$"!'":zt$="god.save":gosub fre.ally:pop:goto flee3
 lg=random(800)+200:if instr("!",wx$) lg=lg-100
 if lg>vk print \lu$" SEES YOU ARE ABOUT TO DIE, AND RUNS AWAY!" :zt$="evil":gosub fre.ally:goto sac.ally
 print \lu$", SEEING YOU ARE ABOUT TO DIE,"\"LEAPS IN FRONT TO TAKE THE DEATH BLOW!":goto fre.ally
;
fre.ally
 print \"(Writing in news log..)"
 if (a1+a2+a3)<1 then ai=0:ai$=""
 dy$=dx$+"battle.log":open #1,dy$:append #1
 dy$="SNIFF":if i$=wx$ dy$="SACRIFICE"
 if (instr("run",zt$)) or (zt$="evil") then dy$="MORALE FAILURE"
 if instr("=",wx$) if i$<>wx$ dy$="BOLT!"
 if zt$="god.save" dy$="FAREWELL"
 print #1, left$(date$,6)yr$" "time$"- "dy$
 dy$=lu$+", DIED FIGHTING "+m$+","
 lc$=" FLED":if instr("run",zt$) if instr("=",cm$) lc$=" BOLTED"
 if instr("run",zt$) dy$=lu$+lc$+" AFTER A HIT FROM "+m$
 if zt$="evil" dy$=lu$+" SEEING "+n1$+" IN TROUBLE,"
 if zt$="god.save" dy$=lu$+" WISKED "+n1$+" AWAY"
 print #1, dy$
 if zt$="run.h" print #1, "CARRYING "n1$" WITH HIM!"
 dy$="WHILE IN SERVICE TO "+n1$
 if i$=wx$ dy$="TO SAVE THE LIFE OF "+n1$+"!"
 if zt$="evil" dy$="RAN AWAY!"
 if zt$="god.save" dy$="FROM DANGER, THAN DEPARTED."
 print #1, dy$
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close:vq=0
 if zt$="run.h" zt$="":goto flee3
 zt$=""
 if instr("=",wx$) if instr("*MNT",ys$) print \"You fall from your steed!" :i$="UNMOUNT2":return
 if x=0 then return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
mad.gd
 gosub rnd.10z:z=z/3+2:ms=ms+((ms/2)*z):m$="THE "+str$(z+1)+" GUARDS" :wy$="|<]>"
 print \"The guard blows on a whistle, and "z" more guards come running!"
 return
;
rnd.10a
 zz$=rnd$:a=(random(999)/100)+1:return
rnd.10z
 zz$=rnd$:z=(random(999)/100)+1:return
rnd.100a
 zz$=rnd$:a=(random(999)/10)+1:return
;
flee3
 i$="flee3"
lnk.main
 dy$=dz$+"spur.main":link dy$,"misc"
advent
 dy$=dz$+"spur.main":link dy$
main.ret
 dy$=dz$+"spur.main":link dy$,"return"
comb.ret
 dy$=dz$+"spur.combat":link dy$,"return"
lnk.sub
 dy$=dz$+"spur.sub":link dy$
lnk.msc6
 dy$=dz$+"spur.misc6":link dy$
linkshop
 setint(""):dy$=dz$+"spur.shop":link dy$,"main1"
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:i$="QUIT":goto lnk.sub
 if ev-ex<120 print on$"Dusk approaches..."of$
 return

drop.1
 pop
dropped
 i$="SPUR.MISC9":dy$=ds$+"spur.logon":link dy$,"quit3"
;
show.file
 setint(1):print \s$\:copy f$:setint(""):return
;
add.log
 open #2,"a:add.log":append #2
 print #2,"Spur.misc9: "i$" @"time$
 close #2:return
;
; a=message number
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):ready dr$:return
;
cln.ally
 if instr("|",lu$) lu$=left$(lu$,instr("|",lu$)-1)
 return
;
loot
 if instr("loot",ys$) print \"The SPUR gestapo frowns on taking too many items per game session!"\:goto advent
 if xi>(zo-1) print \"You can carry no more Items.":goto advent
 zw$="":zx$="":zy$="":ch=0
 print \"People in the area;"\:gosub plyr.loc

loot2
 if ch=0 print \"No adventurers here!"\:goto advent
 input @2\"Loot which Adventurer (CR=Abort) ? "i$
 if i$="" goto advent
 if (i$="?") or (i$="L") goto loot
 x=val(i$):xu=x
 if (x<1) or (x>np) print \"Enter number from 1 to "np:goto loot2
 if x=pn print \"You CANNOT loot yourself!":goto loot2
 gosub rd.plyr2
 if (cl<>yl) or (cr<>yr) print \"That Adventurer is NOT here!":goto loot2
 i$=left$(n2$,1):n2$=mid$(n2$,2)
 if not instr(i$,"ABCDE") print\n2$" scowls, 'Back off bugger!'":goto loot2
 if i$="D" and zw$<>"" i$=zw$:goto guardian
 if i$="C" and zx$<>"" i$=zx$:goto guardian
 if i$="E" and zy$<>"" i$=zy$:goto guardian

 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,x
 input #1,zr\zt$:close

take
 if xi>(zo-1) print \"You can carry no more Items.":goto advent
 if zr<1 print \n2$" isn't carrying any items!":goto loot2
 print \n2$" is carrying:"\
 dy$=dw$+"items"
 open #1,dy$
loot4
 for zs=1 to zr
 y=(zs*4)-3:a=val(mid$(zt$,y)):if a<1 goto bad.loot
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 if len(n$)<2 goto bad.loot
 print right$("   "+str$(zs),3)". - "mid$(n$,3)
 next:print:goto loot3

bad.loot
 i$="Bad loot item string. zr="+str$(zr):gosub add.log
 i$="zt$="+zt$+", n$="+n$:gosub add.log
 zr=zs-1:next:print
 if zr<1 close:print "nothing!":goto loot2

loot3
 input @2\"Take which item number? :"a$:zs=val(a$):if a$="" close:goto loot2
 if a$="?" goto loot4
 if (zs<1) or (zs>zr) print n2$" doesn't don't carry that!!":goto loot3
 y=(zs*4)-3:a=val(mid$(zt$,y))
 position #1,30,a,2:input #1,n$:l=len(zt$):y=(zs*4)-3

tak.itm
 a$=right$("000"+str$(a),3)+","
 if instr("|",n$) goto loot.6
 if instr(a$,xi$) print \"You already have one!":goto loot3
 if instr(a$,ai$) print \"Your ally already carries one!":goto loot3
loot.6
 close:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 print \"You steal the "mid$(n$,3)" from "n2$"!"
 a=30:if pc=9 a=50
 if vk>a vk=vk-a
 xi=xi+1:xi$=xi$+a$
 zr=zr-1:if zr=0 then zt$="":goto loot.4
 if y=1 then zt$=mid$(zt$,5):goto loot.4
 if (y+4)>l then zt$=left$(zt$,y-1):goto loot.4
 zt$=left$(zt$,y-1)+mid$(zt$,y+4)
loot.4
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,x
 print #1,zr\zt$:close

 if (vv=1) or (vv=2) then if not instr("outlaw",ys$) then ys$=ys$+"outlaw" :print \"(Outlaws may steal twice!)":goto loot.5
 ys$=ys$+"loot"
loot.5
 print \"Wait.."
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"- PILLAGE!"
 print #1, n1$" STOLE "mid$(n$,3)" FROM"
 print #1, n2$" IN "ww$".."
 print #1,xu$:close

 if (ys<1) or (ys>nu) then ys=1
 f$=dm$+"mail":ready f$:edit(0):if info(6)<29 goto advent
 print #msg(ys),0
 print #6,xu$
 print #6,"While you were unconscious, you were"
 print #6,"robbed of your "mid$(n$,3)"!"
 print #6,xu$
 copy #8,#6
 print #msg(ys),chr$(4);chr$(0);
 msg(ys)=1:update:ready dr$:goto advent
;
guardian
 print \i$" blocks the path!"
 print "'"n2$" is a member of my guild,"
 print "you must defeat ME first!'"
 dy$=dx$+"battle.log":create dy$
 open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"- COMRADES!"
 print #1, i$" PROTECTED "n2$
 print #1, "FROM PILLAGE, IN "ww$".."
 print #1,xu$:close
 goto loot2
;
plyr.loc
 free:tg$=ta$:gosub ply.locD
 if cl=1 then if tf$<>">:" tg$=tf$:gosub ply.locD
 wx$="":return

ply.locD
; Feed 'ch' variable as status flag.
; ch=0 is call from LOOT. Return ch=1 if players present.
; ch=2 is call from Examine
;    zt$="*" is examine ALL, zt$=NAME is examine NAME. Return ch=4 if success.
 vs=cl:vx=cr
 dy$="":wx$=":"+str$(cr)+"=":yz=len(wx$)
 gosub ply.loc8
 yy=instr(wx$,dy$):if not yy return
ply.loc1
 yw=yz+yy:xz=0
ply.loc2
 xz=xz+1:if mid$(dy$,xz+yw,1)=":" goto ply.loc3
 if xz+yw>(len(dy$)) return
 goto ply.loc2
ply.loc3
; n2$=name
 n2$=mid$(dy$,yw+1,xz-1)
; Here: yx & zz$ = guild identifier if needed
 zz$=mid$(dy$,yw,1):yx=val(zz$)
 a$=" WATCHES YOU.."
 if yx<1 then if zz$<>"0" a$=" LIES UNCONSCIOUS."
; Here: yx=game id number, if needed
 yx=yw+xz+1:yx=val(mid$(dy$,yx,3))
 if instr(zz$,"67") zw$=n2$
 if instr(zz$,"34") zx$=n2$
 if instr(zz$,"89") zy$=n2$
 xx$="UNKNOWN"
 if instr(zz$,"0A") xx$="CIVY"
 if instr(zz$,"12B") xx$="OUTLAW"
 if instr(zz$,"67D") xx$="\|/"
 if instr(zz$,"34C") xx$="-}---"
 if instr(zz$,"89E") xx$="==[]"
 print "# "yx", "xx$" "n2$;a$:ch=1
ply.loc7
 dy$=mid$(dy$,yw+1):yy=instr(wx$,dy$)
 if yy goto ply.loc1
 return
ply.loc8
 if cl=1 dy$=tg$
 if cl=2 dy$=tb$
 if cl=3 dy$=tc$
 if cl=4 dy$=td$
 if cl=5 dy$=te$
 if cl=6 dy$=th$
 return

rd.plyr2
 i$=dw$+"spur.users"
 open #1,i$:position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$:close:return

compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
comp.ck
 print "ok":return
;

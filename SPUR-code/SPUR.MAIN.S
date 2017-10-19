 public flee2
 public return
 public misc
 public compile

 if un=1 print "spur.main--";:gosub comp.ck
 gosub xv$
 gosub ply.loc
advent
 on nocar goto dropped
 if ep>(999+(xp*100)) xp=xp+1:ep=1:gosub lvl.msg
 gosub tim.chk:if ev-ex<120 print "Dusk approaches..."
 if (pe<1) and (ps<1) print \"Ye have starved to death!":hp=0:z=1
 i$=" weakens you!":zr=0:if pt>5 zr=2
 if mid$(zu$,2,1)="1"gosub rnd.100a:if a<6 print "The Ring"i$:pt=pt-zr:if vk>2 vk=vk-2:if pw>5 pw=pw-1:if pi>5 pi=pi-1
 if mid$(zu$,3,1)="1"gosub rnd.10z:if z<4 print "The poison"i$:hp=hp-2 :pt=pt-zr:if hp<1 z=7
 if mid$(zu$,4,1)="1"gosub rnd.10z:if z<4 print "The disease"i$:hp=hp-1 :pt=pt-zr:if hp<1 z=8
; pina modded this:
 if (pe>8 and ps>8) goto not.hungry
 if pe<8 print "You're thirsty";:if pe<4 print ", very thirsty";:else print "!"
 if ps<8 print "You're hungry":if ps<4 print ", very hungry";:else print "!"
 if (pe<3) or (ps<3) print "You are growing faint!"
not.hungry
 if hp<1 goto dead
; trying to get rid of all these bloody parentheses, they make my eyes bleed:
; if ((a1<11) and (a1>0)) or ((a2<11) and (a2>0)) or ((a3<11) and (a3>0)) then print "(Your ally moans)"
; heck with it, print the name...
 if (a1<11 and a1>0) then print "("d1$" moans)"
 if (a2<11 and a2>0) then print "("d2$" moans)"
 if (a3<11 and a3>0) then print "("d3$" moans)"
 if not mw zs=0:goto advent2
 if instr(".",wy$) zs=0:goto advent4
 if zs=998 zs=997:goto advent2
 i$=str$(pc):if not instr(i$,"68") then if mid$(zu$,2,1)="0" goto advent4
 if zs>0 or zq>0 goto advent4
 z=pc*10+5:if mid$(zu$,2,1)="1" z=50
 if random(100)>z zs=999
advent4
 if zs=999 print\m$" lost sight of you!":goto advent2 
 i$="advent5":goto lnk.cmbt
advent2
 di=0
 zz$="You see "
 if i print zz$;it$:else it$=""
; more pina mods:
 if wp=17 print zz$;"a large sword stuck in a rock!":goto excal
 if cl=3 if cr=3 print zz$;"a large rock with a slot in it!"
 if wp print zz$;wp$:else wp$=""
excal
 if fd print zz$;fd$:else fd$=""
 a$="a dead ":if right$(m$,1)="S" a$="some dead "
 if instr(":",wy$) a$="a wrecked "
 if md=1 print \zz$;a$;m$
 if md=2 print \zz$;m$" tracks.."
 if wr$="" print '(Must "READY" weapon)':vm=0:wa=0
 if wa=8 if vn=0 if not instr("STORM",wr$) print '(Must "USE" ammo)'
 if wa=10 if vn=0 print '(Not energized - use the "USE" command)'
; i$=""
 if hp<10 if xf print "(You had better EAT or DRINK something)"
 if (hp<5) or (pe<3) or (ps<3) if xf<1 print "(Try PRAY or REST)"
; if i$<>"" print i$
 print ww$
 if (cl=2) and (cr=223) and (not instr("*GAL",ys$)) i$="galad":goto lnk.msc6
 if yx$="*" yx$="" gosub guilda.c

 if dc$="" then dc$="?"
 print "RETURN="dc$:yz=ev-ex
 i$=str$(yz-((yz/60)*60)):i$=right$("00"+i$,2)
 zz$="":rz$=n1$:gosub to.mixed:zz$=zz$+"["+rz$+"]":rz$=""
 zz$=zz$+"["+str$(yz/60)+":"+i$+"]["+str$(hp)+" hp]"
 if (wa=8) or (wa=10) zz$=zz$+"["+str$(vn)+"]"
 gosub tracker
 print zz$" Cmd:";
 x=0:if vk>2 x=2
 if vu<6 then if instr("STORM",wr$) then if mw gosub rnd.10z:if z<4 print \\"The "wr$" asserts its will!":i$="ATT":vk=vk-x:goto advent3
 input @2 i$
advent3
 if i$="" then i$=dc$:else dc$=i$
 if i$="DIG" gosub lnk.msc7:goto advent
 if i$="DIE" input "DIE! Ok? Y/N " xx$:if xx$<>"Y" goto advent
; what about "else" here?
 if i$="DIE" z=2:goto dead
 if i$="WEAKEN" gosub weak:goto advent2
 if i$="UNREADY" and wr$="" print \"No weapon readied!":goto advent2
 if i$="UNREADY" print \"You repack the "wr$:wr$="":goto advent2
 if instr("ATT",i$) vq=0:goto p.attack
 if i$="LURK" vq=2:goto p.attack
 if i$="STAY" i$="MAIN.STAY":goto lnk.msc4
 if i$="REST" goto rest
 di=0
 if i$="N" di=1
 if i$="S" di=2
 if i$="E" di=3
 if i$="W" di=4
 if i$="U" di=5
 if i$="D" di=6
 if di>0 goto travel
 if i$="DUEL" goto lnk.duel
 if i$="USE" dy$=dz$+"spur.use":link dy$
 if i$="?" f$=dx$+"main.menu":gosub show.file:goto advent2
 if i$="HELP" f$=dx$+"spur.help":gosub show.file:goto advent2
 if i$="LOOK" gosub rd.room2:gosub ply.loc:goto advent
 if (i$="@I") and (info(5)) then dy$=ds$+"spur.sysop":link dy$
 if i$="FLEE" goto flee
 if left$(i$,4)="STAT" i$="STATS"
 zz$="*"+i$+"*"
 if instr(zz$,"*WEAR*EAT*DRINK*INV*") goto lnk.sub
 if left$(i$,3)="GET" zz$="*"
 if instr(zz$,"*GIVE*TAKE*DROP*") goto lnk.misc
 if instr(zz$,"*ORDER*PRAY*AD*QUOTE*READ*Q*QUIT*") goto lnk.msc2
 if (instr(zz$,"*X*LOOT*CAST*")) or (instr("EXAMINE",i$)) goto lnk.msc3
 if (i$="#") and (pc=5) zz$="*"
 if instr(zz$,"*STATS*FL*FOLLOW ME*V*") goto lnk.msc5
 if i$="READY" dy$=ds$+"spur.weapon":link dy$
; seems this could be a bit more friendly:
 if left$(i$,1)=" " print \"There was a space in front. Re-enter.":goto advent2
 print \"Huh?"\:dc$="?":goto advent2
;
flee
 if mw=0 print \"Nothing to flee from!":goto advent2
 if (instr("@@",lo$)) or (instr("**",lo$)) or (instr("<<",lo$)) print \"Can't flee from here.":goto advent
; TODO: subroutine "blocks your way!":
 if hp>6 if instr(".",wy$) then if not instr(":",wy$) gosub rnd.10z:if z<(xp/2) print \m$" blocks your way!":goto advent
 if pe<1 print \"Not enough energy!":goto advent
 if hp>9 if vk>10 vk=vk-10
flee2
 gosub xv$
 zz$=rnd$:cr=random(nr):if cr=0 goto flee2
 if i$="MALFUNCTION" goto travel1
 if cl=2 i$="006,141,117,054,167,120,141,":goto flee5
 if cl=5 i$="393,366,115,101,341,205,378,":goto flee5
 if cl=6 a=random(49)/10:cr=(random(39)/10)+1:cr=cr+(a*30)
 goto travel1
flee5
 cr=random(7):if cr=0 cr=7
 zz$=mid$(i$,(cr*4-3),3):cr=val(zz$):if cr=0 cr=1
 goto travel1
;
travel
; TODO: subroutine "Not enough energy!"
 if pe<1 print \"Not enough energy!":goto advent
 if mw then if instr(".",wy$) then if not instr(":",wy$) then if zq<1 print \m$" has you trapped!":goto advent
 if (vu=1) and (vn>0) and (mw>0) print \m$" charges!":goto advent
; TODO: subroutine "blocks your way!":
 if zs<990 then if mw then if zq=0 then zz$=rnd$:if random(100)>50 print \m$" blocks your way!":goto advent
 x=nr-ri:y=cr mod ri:dy$=ds$+"spur.bar"
 if cl=4 then if cr=42 then if di=3 link dy$
 if cl=1 then if cr=49 then if di=1 link dy$
 if cl=5 then if cr=157 then if di=3 link dy$
 if cl=6 then if cr=584 then if di=2 link dy$
 a=0:z=instr("+@",lo$):if z=0 goto boat
 z=val(mid$(lo$,z+2,1)):a=instr("074,",xi$):zz$="You shove the dinghy into the water.."
 if cl=6 a=instr("122",xi$):zz$="YOU FIRST PUT ON THE SPACESUIT"
 if (di<>z) or (a=0) then goto boat
 print \zz$:
 if (cl=6) and (instr("138",xi$)) then print \"The SPACE TRACKER powers up!"\"(Giving galactic space coodinates)":else if cl=6 print \"(Too bad you don't have a SPACE TRACKER..)"
boat
 i$="BOAT":if cl=6 i$="SPACE SUIT"
 if (di=z) and (a=0) then print \"Not without a "i$"!":goto advent
 i$=lo$+"**"
block.s
 gosub pal:if (cp=1) or (pc=5) then xy=1
 if cl<6 then if xy>0 goto block.s1
 z=instr("]",i$):if z=0 goto block.s1
 zz$=mid$(i$,z+1,1):if zz$=dc$ goto travel1
 i$=mid$(i$,z+1):goto block.s
block.s1
 if (di=1) and (n) then cr=(cr<=ri)*nr+cr-ri:goto travel1
 if (di=2) and (s) then cr=cr+ri-((cr>x)*nr):goto travel1
 if (di=3) and (e) then cr=cr+1-((y=0)*ri):goto travel1
 if (di=4) and (w) then cr=cr+((y=1)*ri)-1:goto travel1
 if (di=5) and (rc=1) goto travel3
 if (di=6) and (rc=2) goto travel3
 if (cl=1) then if (cr=89) goto travel3
 i$="rocks":if cl=6 i$="hull"
 if instr("@@!",lo$) z=17:hp=hp-2:print \"You bounce off the "i$"!":if hp<1 goto dead
 print \"Can't go there!":goto advent
travel1
 yx$="":i$="BOAT":if cl>5 i$="SPACESUIT"
; TODO: print direction heading?
 z=instr("@@+",lo$):if z then z=val(mid$(lo$,z+3,1):if di=z print \"You get out of the "i$"..."
 if (pe>4) or (ps>4) goto travel1a
 if pt>0 then pt=pt-1:print xv$"more fragile)"
travel1a
 if not mw goto travel2
 gosub set.pa
 a=pa:b=ma:gosub set.prob
 gosub rnd.10z:x=z
 i$="s ":if right$(m$,1)="S" i$=" "
 if zs<990 then if (x<=p1) and (mw>0) then if random(100)>33 print \m$" follow"i$:mf=1:goto travel2
 if not mw goto travel2
 if zq>0 i$="CHARM":gosub lnk.msc5:goto trav1c
 if zs<990 if instr(":",wy$) print \m$" power"i$"down.":goto trav1d
 if zs<990 print \m$" snarl"i$"and wait"i$:goto trav1d
 if zs>989 if instr(":",wy$) print \m$" ignore"i$"you.":zs=0:goto trav1c
 if zs>989 print \m$" look"i$"around uneasily.":zs=0
trav1c
;.. mw used temporarily to calc honor
 mw=2
 if (pr=2) or (pr=8) if instr("E",wy$) mw=4
 if (pr=3) or (pr=4) if instr("G",wy$) mw=4
 if (zs>989) or (zq>0) then if vk<2000 vk=vk+mw
trav1d
 zq=0:mw=0:mf=0:m$="":wy$=""
 
travel2
 ep=ep+1:md=0
 gosub rd.room:mm=mm+1:free:print
 gosub scn.dsp
 if m goto no.ameoba
 if mid$(zu$,5,1)="1" i$="djinn":gosub lnk.msc7:goto no.guard
 if instr("GARDEN OF EDEN",ww$) gosub g.o.e.
 gosub rnd.10z
 if instr("\|/",ww$) then if z<3 m=67
 if instr("-}-",ww$) then if z<3 m=66
 if instr("=[]",ww$) then if z<3 m=65
 if (m) or (z>cl) or (mid$(zu$,7,1)="1") or (zn=70) or (cl>5) goto no.guard
 gosub rnd.10z:if mid$(zu$,2,1)="0" then if z>cl goto no.guard
 print \"Something evil stalks..."
 gosub rnd.10z:if z=1 print \"It is here!":m=70
no.guard
 if (cl<>6) or (not instr("@@",lo$)) then goto no.ameoba
 gosub rnd.100a:if a>97 i$="METEOR":gosub lnk.msc6
 gosub rnd.100a:if a<3 m=119:print \\"Something comes!"
no.ameoba
 if (tm<>0) and (tm<mm) print \"The aura protecting you is gone.":tm=0
 if not (mm mod 10) then pe=pe-1
 if pe<0 then pe=0
 if mm>9999 then mm=0
 gosub dwarf
 gosub rnd.100a:if a<3 gosub thief
 if mf goto travel2a
 if (cr<>df) or (cl>1) then goto no.dwarf
 zz$=rnd$:m=random(mc):m=m+(m=0)
 print \"A short bearded person is here, with a pile of gold!"
 gosub rd.dwarf:ms=ms+15:mf=1:m$="THE DWARF":mw=1:md=0:goto travel2a
no.dwarf
 if (cl=sl) and (cr=sr) then dy$=ds$+"spur.duel":link dy$
 if not m gosub rnd.100a:if (a=50) or (a=51) i$="RANDOM":gosub lnk.msc6
 if m gosub rd.mons
travel2a
 if (not i) goto travel2b
 a$=right$("000"+str$(i),3)+",":i$=xi$+ai$
 if (instr(a$,i$)) or (instr(a$,xt$)) then i=0:goto travel2b
 dy$=dw$+"items":rl=30:d=i:gosub rd.file
 yz=instr("|",d$):if yz>0 d$=left$(d$,yz-1)
 it$=d$:i=d:i1$=dp$:iv=f
 
travel2b
 if (not wp) goto travel2c
 a$=right$("000"+str$(wp),3)+",":if instr(a$,xw$) then wp=0:goto travel2c
 dy$=dx$+"weapons":rl=34:d=wp:gosub rd.file:wp$=mid$(d$,2):wp=d:wt$=dp$:wv=f
 
travel2c
 if (not fd) gosub ply.loc:goto advent
 a$=right$("000"+str$(fd),3)+","
 if (instr(a$,xf$)) or (instr(a$,xo$)) then fd=0:gosub ply.loc:goto advent
 dy$=dw$+"stores":rl=26:d=fd:gosub rd.file:fd$=d$:fd=d:ft$=dp$:sv=f
 gosub ply.loc:goto advent
 
travel3
 i$="travel3":goto lnk.misc

dwarf
 if (not df) return
 gosub rnd.100a:if a<>50 return
 i$="DWARF":goto lnk.msc5
;
thief
 if xw<3 return
 i$="thief":goto lnk.misc
;
rd.file
 open #1,dy$:position #1,rl,d:input #1,cb$\d$\f
 dp$=left$(d$,1):d$=mid$(d$,3):f=f mod 10
 if cb$<>"1" then d$="":d=0:f=0
 close:return

rd.mons
 i$="rd.mons":goto lnk.msc4
rd.dwarf
 i$="rd.dwarf":goto lnk.msc4

rd.room
 wy$=""
 input #msg(cr),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 edit(0):copy #6,#8
 if (n=0) and (s=0) and (e=0) and (w=0) and (rc=0) then cr=cr+3:cr=cr mod nr:cr=cr+1:goto rd.room
rm.name
 z=instr("|",lo$):if instr("\|",lo$) z=0
 ww$=lo$:if z ww$=left$(lo$,z-1)
 if z lo$=mid$(lo$,z):else lo$=" "
 if un=1 print "lo$="lo$
 z=instr("T",lo$):if z cr=val(mid$(lo$,z+1)):print \"[A wave of nausea engulfs you, then subsides.]":goto rd.room
 if (instr("=+",lo$)) or (ww$="OUTER SPACE") goto rd.room2
 if left$(ww$,4)<>"THE " then if left$(ww$,2)<>"A " ww$="THE "+ww$
rd.room2
 print:if instr("HQ",ww$) yx$="*"
 if (not instr(left$(zu$,1),"AB")) or (i$="LOOK") setint(1):copy #8,#0 :setint("")
 if i$<>"LOOK" then if instr("DESERT",ww$) gosub rnd.10z:if z<4 pe=pe-1:print \"You sweat in the heat."
 if not instr("@@",lo$) goto dingy
 a=instr("074",xi$):i$="drown in the water!":z=10
 if cl=6 a=instr("122",xi$):i$="choke in the vacuum!":z=15
 if a=0 print \"You "i$:hp=hp-5:goto dingy
 i$="":if cl<>6 and instr("074,",xi$) i$="row the dinghy."
 if cl=6 and instr("122,",xi$) i$="fire steering rockets."
 if i$="" goto dingy
 print \"YOU "i$
 if cl<6 gosub rnd.10z:if z<4 print "Growing a bit tired";:ps=ps-1
dingy
 if instr("&",lo$) then if instr("123",xi$) print \"[Tick... tick...]":if instr("&&-",lo$) print \"[ Danger! Radiation suit required. ]"
 i$=""
 if instr("**",lo$) i$="078":zz$="**":a$="You're freezing!":zt$="COAT":z=11
 if instr("&&",lo$) i$="124":zz$="&&":a$="You feel funny!":zt$="RAD SUIT":z=16 :if not instr("123",xi$) i$="123"
 if i$="" goto coat
 if instr(zz$,lo$) then if not instr(i$,xi$) print \a$:pe=pe-1:ps=ps-1:hp=hp-2
 if instr(i$,xi$) a$="You wisely wear the "+zt$:else a$="Too bad you don't have a "+zt$+"!":if i$="123" a$="You have a strange feeling that you should know something.."
 zz$=zz$+"-":if instr(zz$,lo$) print \a$
coat
 if hp<1 pop:goto dead
 a=pw+pi:if a<10 goto rd.room3
 if not instr("LABYR",ww$) then if not instr("DESERT",ww$) then if not instr("@@",lo$) goto rd.room4
 if cp=1 then if cl<6 print \"[Reading COMPASS...]";:goto rd.room4
rd.room3
 i$="You lost your sense of direction."
 if cl=6 i$="Star-filled blackness engulfs you."
 if cl<6 gosub pal:if xy>0 print \"[Your PALINTAR glows...]";:goto rd.room4
 if (cl<6) and (pc=5) then print \"[Using Ranger Tracking...]";:goto rd.room4
 print \i$:return
rd.room4
 print \"Ye may travel:";
 if n print " North";
 if s print " South";
 if e print " East";
 if w print " West";
 if rc=1 print " Up";
 if rc=2 print " Down";
 print
 return
;
p.attack
 i$="p.attack":goto lnk.cmbt
;
lvl.msg
 print\"Congratulations! You are a level "xp" player!":return
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:i$="QUIT":goto lnk.sub
 return
;
rest
 if mw print \m$" won't let you!":goto advent
 gosub tim.chk:if ev-ex<260 print \"You don't have enough time!":goto advent
 goto lnk.msc6
;
set.prob
 if a>b then p1=a-b:else p1=b-a
 if p1>5 then p1=10-p1
 p2=p1*2:p2=10-p2+(p1=0)
 return
;
lnk.duel
 gosub tim.chk:a=180:if info(2)=1 a=300
 if (ev-ex)<a i$="Not enough time to duel.":goto duel.2
 if vt>0 dy$=mid$(zu$,7,1):if dy$<>"1" then if dy$<>"2" i$="Only Wraith Masters may duel twice.":goto duel.2
 if vt>1 i$="Only two duels per session.":goto duel.2
 dy$=ds$+"spur.duel2":link dy$
duel.2
 print \i$:gosub add.lg:goto advent
;
dead
 hp=0:xn=sn:sn=0
 i$="dead2":goto lnk.msc6

dropped
 i$="SPUR.MAIN":dy$=ds$+"spur.logon":link dy$,"quit3"

ply.loc
 if (vs=cl) then if (vx=cr) then if (dc$<>"LOOK") then return
 wx$="":zt$="":tg$=ta$:gosub ply.locD
 if cl=1 then if tf$<>">:" tg$=tf$:gosub ply.locD 
 wx$="":if zt$="" return
 pop:xx$=zt$:z=zr:i$="AUTODUEL":print\xx$" approaches you...":goto lnk.msc5
ply.locD
 vs=cl:vx=cr
 if (mw>0) or (md>0) then if instr("#",wy$) then if not instr("#",wx$) wx$="#" :gosub statue
 zw$="":zx$=":"+str$(cr)+"=":yz=len(zx$)
 gosub ply.loc8
 yy=instr(zx$,zw$):if not yy goto ply.loc4
ply.loc1
 yw=yz+yy:xz=0
ply.loc2
 xz=xz+1:if mid$(zw$,xz+yw,1)=":" goto ply.loc3
 if xz+yw>(len(zw$)) goto ply.loc5
 goto ply.loc2
ply.loc3
 zy$=mid$(zw$,yw+1,xz-1):gosub autoduel:zz$=zz$+dy$
 print \zy$;zz$:if not instr("LIES",zz$) then zz$=rnd$:gosub ply.loc7
 zw$=mid$(zw$,yw+1):yy=instr(zx$,zw$):if yy goto ply.loc1
ply.loc4
 gosub ply.loc8
 if n xz=(cr<=ri)*nr+cr-ri:i$="north.":gosub ply.loc6
 if s xz=cr+ri-((cr>x)*nr):i$="south.":gosub ply.loc6
 if e xz=cr+1-((y=0)*ri):i$="east.":gosub ply.loc6
 if w xz=cr+((y=1)*ri)-1:i$="west.":gosub ply.loc6
ply.loc5
 return
ply.loc6
 zx$=":"+str$(xz)+"=":yy=instr(zx$,zw$)
 if yy then if not instr(i$,wx$) wx$=wx$+i$:print "There is somebody to the "i$
 return
ply.loc8
 if cl=1 zw$=tg$
 if cl=2 zw$=tb$
 if cl=3 zw$=tc$
 if cl=4 zw$=td$
 if cl=5 zw$=te$
 if cl=6 zw$=th$
 return
ply.loc7
 yx=yw+xz+1:zz$=mid$(zw$,yx,3):yx=val(zz$):i$=""
ply.locA
 dy$=dw$+"spur.chat":z=64
ply.locC
 open #1,dy$:position #1,z,yx:input #1,zz$:close:if i$="V" goto ply.locB
 if zz$="blank" or zz$="" dy$=zy$+" is silent.":goto ply.loc9
ply.locB
 yx=instr("$",zz$):dy$=zz$:xz=len(zz$)
 if yx>1 then if yx<xz dy$=left$(zz$,yx-1):zz$=mid$(zz$,yx+1):dy$=dy$+n1$+zz$
 if yx=1 dy$=n1$+mid$(zz$,2)
 if yx=xz dy$=left$(zz$,yx-1)+n1$
 zz$=dy$:dy$="'"+zz$+"'"
ply.loc9
 print dy$:return
;
autoduel
 yx=yw+xz+1:zz$=mid$(zw$,yx,3):yx=val(zz$)
 i$=mid$(zw$,yw,1):z=val(i$):zz$=" is here":dy$=" (Civy)"
 if instr(i$,"12B") dy$=" (Outlaw)"
 if instr(i$,"34C") dy$=" (-}---)"
 if instr(i$,"67D") dy$=" (\|/)"
 if instr(i$,"89E") dy$=" (==[])"
 if z=0 then if i$<>"0" then zz$=" lies here unconscious!":return
 if dc$="LOOK" return
 if z=0 zz$=" looks innocent.":return
 zz$=" greets you!":if random(100)>60 zt$=zy$:x=yx:zr=z
 if vv=z then if vv>2 return
 if instr(i$,"368") then if (vv=z+1) return 
 if instr(i$,"479") then if (vv=z-1) return
 if instr(i$,"01368") zz$=" is here.":return
 if vv=0 then if z>2 zz$=" sneers at you!":return
 zz$=" glares at you!":zt$=zy$:x=yx:zr=z
 return
;
show.file
; apparently xshow is missing...
; setint(1):use "B:xshow",f$:setint(""):return
 setint(1):print \s$\
 open #1,f$:if mark(1) close #1:i$=f$+" not found.":gosub add.lg:return
showfl2
 copy (20) #1
 if (eof(1) or key(1)) setint(""):close #1:return
 if not flag(35) goto showfl2
 print "Press [RETURN] ";:get i$:if i$=chr$(13) print " ";
 print chr$(8,16);chr$(32,16);chr$(8,16);
 if i$=" " setint(""):close #1:return
 setint(1):goto showfl2

;
rnd.10a
 zz$=rnd$:a=(random(999)/100)+1:return
rnd.10z
 zz$=rnd$:z=(random(999)/100)+1:return
rnd.100a
 zz$=rnd$:a=(random(999)/10)+1:return
;
set.pa
 pa=ps+pd+pt+pi+pw+pe:pa=pa/16:if pa>9 pa=9
 if pa<6 print "(You feel poorly.)"
 return
;
return
 on nocar goto dropped

; TODO: should be replaced with just a print statement:
xv$
 xv$="(You feel a bit ":return
;
misc
 on nocar goto dropped
 gosub xv$
 if i$="travel2" goto travel2
 if i$="travel1" goto travel1
 if i$="advent3" i$=dc$:goto advent3
 if (i$="flee3") or (i$="MALFUNCTION") goto flee2
; now logged to disk:
 i$="[misc] Bad I$: "+chr$(34)+i$+chr$(34):gosub add.lg:goto advent
;
scn.dsp
; this prints to the bottom window on the sysop screen
; TODO: beef up scn.dsp routine to display more info:
; print @column,row
 print #3 @4,23 right$("   "+str$(cl),4)
 print #3 @13,23 right$("    "+str$(cr),4)
 print #3 @4,24 right$("   "+str$(mm),4);
 print #3 @13,24 right$("    "+str$(ep),4);
; reposition cursor for printing to user area?
 print #3 @1,20
 return
;
tracker
 if (cl<6) or (not instr("@@",lo$)) then return
 if not instr("138",xi$) return
 zz$=zz$+"[GC:"+str$(cr)+"]":return
;
pal
 if not instr("096",xi$) xy=0:return
 xy=(pi+pw)*xp
 if pc=2 xy=xy+20
 if pr=3 xy=xy+30
 if pr=4 xy=xy+20
 if pr=9 xy=xy+10
 if xy<240 xy=0
 return
;
weak
 input @2\"Remove how many hit points? :"i$
 xy=val(i$):if xy<1 return
 if xy>(hp-5) print \"I won't remove that many!":return
 print \"So be it.":hp=hp-xy:return
;
statue
 if mf=1 return
 dy$=dx$+m$:if left$(m$,4)="THE " dy$=dx$+mid$(m$,5)
 open #1, dy$:input #1,dy$:close
 print \"There is a statue of "dy$" here!":return
;
g.o.e.
 gosub rnd.10z:if (hp<25) and (z=5) print \"(Hit points increase)":hp=hp+1
 gosub rnd.10z:if (ps<25) and (z=5) print \"(Strength increases)":ps=ps+1
 gosub rnd.10z:if (pe<25) and (z=5) print \"(Energy increases)":pe=pe+1
 gosub rnd.100a:if a<6 print \"You are tempted to just stay here.."
 if (a<6) and (pi>5) pi=pi-1:print "(You feel dumber)"
 if (a<6) and (pw>5) pw=pw-1:print "(You feel less wise)"
 gosub rnd.100a:if a<6 m=121
 return
;
;....SUPPLY i$=NAME OF ROUTINE IN FOLLOWING MISC PROGRAMS
lnk.lgn
 dy$=ds$+"spur.logon":link dy$,"misc"
; ^ target ok
lnk.sub
 dy$=dz$+"spur.sub":link dy$
lnk.misc
 dy$=dz$+"spur.misc":link dy$,"misc"
; ^ target ok
lnk.msc2
 dy$=ds$+"spur.misc2":link dy$
lnk.msc3
 dy$=dz$+"spur.misc3":link dy$
lnk.msc4
 dy$=dz$+"spur.misc4":link dy$
lnk.msc5
 dy$=dz$+"spur.misc5":link dy$
lnk.msc6
 dy$=dz$+"spur.misc6":link dy$
lnk.msc7
 dy$=ds$+"spur.misc7":link dy$
lnk.cmbt
 dy$=dz$+"spur.combat":link dy$,"misc"
; ^ target ok
;
add.lg
;.. i$=log message
; modded by pina to display error to screen
 open #2,"a:add.log":append #2
 i$="[spur.main] "+left$(time$,8)+" "+i$:print i$
 print #2,i$:close #2:return
;
compile
 if un=1 print \"Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return

guilda.c
 zm=0:yz=1
 if instr("\|/",ww$) xu$="Mark of the Claw":zy$="CLAW"
 if instr("-}--",ww$) xu$="Mark of the Sword":zy$="SWORD"
 if instr("=[]",ww$) xu$="Iron Fist":zy$="FIST"
 if (vv=6) or (vv=7) or (info(5)) then if instr("\|/",ww$) zm=1:yz=28
 if (vv=3) or (vv=4) or (info(5)) then if instr("-}--",ww$) zm=2:yz=27
 if (vv=8) or (vv=9) or (info(5)) then if instr("=[]",ww$) zm=3:yz=29
 if (zm=0) return
 if flag(yz)=0 then if not info(5) print \"[Waiting for GM Access to this guild]":return
 input @2\"Enter Guild HQ [y/N]? "i$
 if i$="Y" dy$=ds$+"spur.guild":pop:link dy$
 return

to.mixed
 gosub to.lower
 l0$="":y=0
 for yy = 1 to len(rz$)
 x=asc(mid$(rz$,yy,1))
 if (x=32) and (len(l0$)=0) then goto tm.loop
 if (len(l0$)=0) and (x>96) and (x<123) then l0$=chr$(x-32):goto tm.loop

; if x=32 then y=1:l0$=l0$+chr$(32):goto tm.loop
;Force upper case after and non alpha character
 if (x>96) and (x<123) goto Skip.conv
 if (x>64) and (x<91) goto Skip.conv 
 y=1:l0$=l0$+chr$(x):goto tm.loop
Skip.conv
 if (y=1) and (x>96) and (x<123) then l0$=l0$+chr$(x-32):y=0:goto tm.loop
 l0$=l0$+chr$(x)
tm.loop
 next
 rz$=l0$:return
 
;Convert string in rz$ to lower case
to.lower
 l0$=""
 for yy=1 to len(rz$)
 x=asc(mid$(rz$,yy,1)):if (x>64) and (x<91) then x=x+32
 l0$=l0$+chr$(x)
 next
 rz$=l0$:return

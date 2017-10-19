;...spur.main.s
;...Worked on with Appleworks
 public flee2
 public return
 public misc
 public compile

 if flag(32) print "spur.main--";:gosub comp.ck
 gosub xv$
 gosub ply.loc
advent
 on nocar goto dropped
 if not instr("*MNT",ys$) goto no.mount
 if (not instr("=",d1$+d2$+d3$)) or (instr("@@",lo$)) i$="DISMOUNT":goto lnk.msc7
no.mount
 if ep>(999+(xp*100)) xp=xp+1:ep=1:gosub lvl.msg
 gosub tim.chk:if ev-ex<120 print on$"Dusk approaches..."of$
 if gm=1 goto advent.gm
 if pe<1 if ps<1 print \"YE HAVE STARVED TO DEATH!!":hp=0:z=1
 i$=" WEAKENS YOU!":zr=0:if pt>5 zr=2
 if mid$(zu$,2,1)="1"gosub rnd.100a:if a<6 print "THE RING"i$:pt=pt-zr:if vk>2 vk=vk-2:if pw>5 pw=pw-1:if pi>5 pi=pi-1
 if mid$(zu$,3,1)="1"gosub rnd.10z:if z<4 print "THE POISON"i$:hp=hp-2 :pt=pt-zr:if hp<1 z=7
 if mid$(zu$,4,1)="1"gosub rnd.10z:if z<4 print "THE DISEASE"i$:hp=hp-1 :pt=pt-zr:if hp<1 z=8
advent.gm
 if pe<8 print on$"YOUR THIRSTY"of$:if pe<4 print hl$"VERY THIRSTY!"of$
 if ps<8 print on$"YOUR HUNGRY"of$:if ps<4 print hl$"VERY HUNGRY!"of$
 if (pe<3) or (ps<3) print hl$"YOU ARE BECOMING FAINT!"of$
 if hp<1 if gm=1 hp=1:print "GOD MODE SAVES YOU FROM DYING."
 if hp<1 goto dead
 z=0:if a1<11 if a1>0 z=1
 if a2<11 if a2>0 z=1
 if a3<11 if a3>0 z=1
 if z print "(Your ally looks weak)"
 if not mw zs=0:goto advent2
 if instr(".",wy$) zs=0:goto advent4
 if zs=998 zs=997:goto advent2
; ring used?
 i$=str$(pc):if not instr(i$,"68") then if mid$(zu$,2,1)="0" goto advent4
 if zs>0 or zq>0 goto advent4
 z=pc*10+5:if mid$(zu$,2,1)="1" z=50
 if random(100)>z zs=999
advent4
 if zs=999 print\m$" LOST SIGHT OF YOU!":goto advent2
 i$="advent5":goto lnk.cmbt
advent2
 di=0
 zz$="YOU SEE "
 if i print zz$;it$:else it$=""
 if wp=17 print "YOU SEE A LARGE SWORD STUCK IN A ROCK!":goto excal
 if cl=3 if cr=3 print "YOU SEE A LARGE ROCK WITH A SLOT IN IT!"
 if wp print zz$;wp$:else wp$=""
excal
 if fd print zz$;fd$:else fd$=""
 a$="A DEAD ":if right$(m$,1)="S" a$="SOME DEAD "
 if instr(":",wy$) a$="A WRECKED "
 if md=1 print \zz$;a$;m$
 if md=2 print \zz$;m$" TRACKS.."
 i$=""
 if wr$="" i$="(Must READY weapon)":vm=0:wa=0
 if wa=8 if vn=0 if not instr("STORM",wr$) if i$="" i$="(Must USE ammo)"
 if wa=10 if vn=0 if i$="" i$="(Not energized)"
 if i$<>"" print on$;i$;of$:i$=""
 if hp<10 if xf i$="(Better EAT or DRINK something)"
 if (hp<5) or (pe<3) or (ps<3) if xf<1 i$="(Try PRAY or REST)"
 if i$<>"" print hl$;i$;of$
 print ww$
 if cl=2 if cr=223 if not instr("*GA",ys$) i$="galad":goto lnk.msc6
 if yx$="*" yx$="" input @2\"Enter Guild HQ? "i$:if i$="Y" dy$=ds$+"spur.guild" :link dy$
 if dc$="" then dc$="?"
 print "RETURN="dc$:yz=ev-ex
 i$=str$(yz-((yz/60)*60)):i$=right$("00"+i$,2)
 zz$="["+str$(yz/60)+":"+i$+"]["+str$(hp)+" hp]"
 if (wa=8) or (wa=10) zz$=zz$+"["+str$(vn)+"]"
 if instr("*HO",ys$) zz$=zz$+"[HO:"+str$(vk)+"]"
 gosub tracker
 x=0:if vk>2 x=2
 if vu<6 then if instr("STORM",wr$) then if mw gosub rnd.10z:if z<4 print \\"THE "wr$" ASSERTS IT'S WILL!!":i$="ATT":vk=vk-x:goto advent3
advent.p
 print zz$" Cmd:";
 input @2 i$
 if i$="TGM" gosub godmode:i$="":goto advent.p
;..Prevent rules lawyer from going back and forth for ep
 if instr(i$,"N,S,E,W")=instr(dc$,"S,N,W,E") if ep>1 ep=ep-1
advent3
 if i$="" then i$=dc$:else dc$=i$
 if i$="HO" if len(ys$)<240 if not instr("*HO",ys$) ys$=ys$+"*HO":print \"Honor display- ON":goto advent
 if i$="TEST" if flag(32) link "a:spur.misc2","servant"
 if i$="DIE" goto die
 if i$="WEAKEN" gosub weak:goto advent2
 if i$="UNREADY" if wr$="" print \"NO WEAPON READIED!":goto advent2
 if i$="UNREADY" print \"YOU REPACK THE "wr$:wr$="":goto advent2
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
 if (i$="LOOK") or (i$="L") gosub rd.room2:gosub ply.loc :goto advent
 if i$="@I" if info(5) dy$=ds$+"spur.sysop":link dy$
 if i$="FLEE" goto flee
 if left$(i$,4)="STAT" i$="STATS"
 if i$="FEED" i$="EAT"
 zz$="*"+i$+"*"
 if instr(zz$,"*WEAR*EAT*DRINK*INV*") goto lnk.sub
 if left$(i$,3)="GET" zz$="*"
 if instr(zz$,"*GIVE*TAKE*DROP*") goto lnk.misc
 if instr(zz$,"*ORDER*PRAY*AD*QUOTE*READ*Q*QUIT*") goto lnk.msc2
 if (instr(zz$,"*X*CAST*")) or (instr("EXAMINE",i$)) goto lnk.msc3
 if i$="#" if pc=5 zz$="*"
 if instr(zz$,"*STATS*FL*FOLLOW ME*V*") goto lnk.msc5
 if instr(zz$,"*DIG*MOUNT*DISMOUNT*") goto lnk.msc7
 if instr(zz$,"*TRACK*LOOT*") goto lnk.msc9
 if i$="READY" dy$=dz$+"spur.weapon":link dy$
 if left$(i$,1)=" " print \"THERE WAS A SPACE IN FRONT. RE-ENTER":goto advent2
 aa=aa+1:if aa>50 i$="Carrier loss trapped":gosub add.log:goto dropped
 print \"HUH?"\:dc$="?":goto advent2
;
godmode
 if gm=0 gm=1:f$=dx$+"godmode":gosub show.file:else gm=0:print "GOD MODE OFF."
 return
;
die
 if flag(7) print \"(WILL LOSE IMMORTAL STATUS) ";
 input @2 "DIE! Ok? y/[N] :" xx$
 if xx$<>"Y" goto advent
 flag(7)=0:z=2
 goto dead
;
flee
 if mw=0 print \"NOTHING TO FLEE FROM!":goto advent2
 if (instr("@@",lo$)) or (instr("**",lo$)) or (instr("<<",lo$)) print \"Can't flee from here..":goto advent
 if hp>6 if instr(".",wy$) then if not instr(":",wy$) gosub rnd.10z:if z<(xp/2) print \m$" BLOCKS THE PATH!":goto advent
 if pe<1 print \"NOT ENOUGH ENERGY!":goto advent
 if hp>9 if vk>10 vk=vk-10
flee2
 gosub xv$:zz$=rnd$
 if i$="MALFUNCTION" cr=random(nr):goto travel1
 z=instr("FL",lo$)
 if z cr=val(mid$(lo$,z+2)):goto travel1
 z=random(399)/100:for a=1 to 4:z=z+1:if z>4 z=1
 if z=1 if n cr=(cr<=ri)*nr+cr-ri:a=4
 if z=2 if s cr=cr+ri-((cr>x)*nr):a=4
 if z=3 if e cr=cr+1-((y=0)*ri):a=4
 if z=4 if w cr=cr+((y=1)*ri)-1:a=4
 next
 goto travel1
;
travel
 if pe<1 print \hl$"NOT ENOUGH ENERGY!"of$:goto advent
 if mw then if instr(".",wy$) then if not instr(":",wy$) then if zq<1 print \m$" HAS YOU TRAPPED!":goto advent
 if vu=1 if vn>0 if mw>0 print \m$" CHARGES!":goto advent
 if zs<990 if mw if zq=0 zz$=rnd$:if random(100)>50 print \m$" BLOCKS THE PATH!":goto advent
 x=nr-ri:y=cr mod ri:dy$=ds$+"spur.bar"
 if cl=1 if cr=49 if di=1 link dy$
 if cl=4 if cr=42 if di=3 i$="SRV.GUILD":dy$=ds$+"spur.misc8":link dy$
 if cl=5 if cr=157 if di=3 i$="JAKES":dy$=ds$+"spur.misc8":link dy$
 if cl=6 if cr=584 if di=2 link dy$
 a=0:z=instr("+@",lo$):if z=0 goto boat
 z=val(mid$(lo$,z+2,1)):a=instr("074,",xi$):zz$="YOU SHOVE THE DINGY INTO THE WATER.."
 if cl=6 a=instr("122",xi$):zz$="YOU FIRST PUT ON THE SPACESUIT"
 if (di<>z) or (a=0) then goto boat
 print \zz$:
 if cl=6 if instr("138",xi$) print \"THE SPACE TRACKER POWERS UP!"\"(Giving glactic space coodinates)":else if cl=6 print \"(Too bad you don't have a SPACE TRACKER..)"
boat
 if di=z if instr("*MNT",ys$) print\"Must DISMOUNT first":goto advent
 i$="BOAT":if cl=6 i$="SPACE SUIT"
 if di=z if a=0 print \"NOT WITHOUT A "i$"!":goto advent
 i$=lo$+"**"
block.s
 gosub pal:if (cp=1) or (pc=5) then xy=1
 if cl<6 then if xy>0 goto block.s1
 z=instr("]",i$):if z=0 goto block.s1
 a=0:if ep>1 a=1
 zz$=mid$(i$,z+1,1):if zz$=dc$ ep=ep-a:goto travel1
 i$=mid$(i$,z+1):goto block.s
block.s1
 if di=1 if n cr=(cr<=ri)*nr+cr-ri:goto travel1
 if di=2 if s cr=cr+ri-((cr>x)*nr):goto travel1
 if di=3 if e cr=cr+1-((y=0)*ri):goto travel1
 if di=4 if w cr=cr+((y=1)*ri)-1:goto travel1
 if di=5 if rc=1 goto travel3
 if di=6 if rc=2 goto travel3
 if cl=1 if cr=89 goto travel3
 i$="ROCKS!":if cl=6 i$="HULL!"
 if instr("@@!",lo$) z=17:hp=hp-2:print \"YOU BOUNCE OFF THE "i$:if hp<1 goto dead
 if cl=6 if instr("+@",lo$) print \"You can not walk thru a closed airlock.." :goto advent
 print \"CAN'T GO THERE!":goto advent
travel1
 yx$="":i$="BOAT":if cl>5 i$="SPACESUIT"
 z=instr("@@+",lo$):if z then z=val(mid$(lo$,z+3,1):if di=z print \"YOU GET OUT OF THE "i$".."
 if (pe>4) or (ps>4) goto travel1a
 if pt>0 then pt=pt-1:print xv$"MORE FRAGILE)"
travel1a
 if not mw goto travel2
 gosub set.pa
 a=pa:b=ma:gosub set.prob
 gosub rnd.10z:x=z
 i$="S ":if right$(m$,1)="S" i$=" "
 if zs<990 then if (x<=p1) and (mw>0) then if random(100)>33 print \m$" FOLLOW"i$:mf=1:goto travel2
 if not mw goto travel2
 if zq>0 i$="CHARM":gosub lnk.msc5:goto trav1c
 if zs<990 if instr(":",wy$) print \m$" POWER"i$"DOWN.":goto trav1d
 if zs<990 print \m$" SNARL"i$"AND WAIT"i$:goto trav1d
 if zs>989 if instr(":",wy$) print \m$" IGNORE"i$"YOU.":zs=0:goto trav1c
 if zs>989 print \m$" LOOK"i$"AROUND UNEASILY.":zs=0
trav1c
;.. mw used temporarily to calc honor
 mw=3
 if (pr=2) or (pr=8) if instr("E",wy$) mw=6
 if (pr=3) or (pr=4) if instr("G",wy$) mw=6
 if (zs>989) or (zq>0) then if vk<2000 vk=vk+mw
trav1d
 zq=0:mw=0:mf=0:m$="":wy$=""

travel2
 ep=ep+1:md=0
 gosub rd.room:mm=mm+1:free:print
 gosub scn.dsp
 if m goto no.special
; 
 if mid$(zu$,5,1)="1" i$="djinn":gosub lnk.msc7:goto no.special
 gosub g.o.e.
 gosub guard
 gosub space
 gosub horse
no.special
 if (tm<>0) and (tm<mm) print \"THE AURA PROTECTING YOU IS GONE.":tm=0
 if not (mm mod 10) then pe=pe-1
 if pe<0 then pe=0
 if mm>9999 then mm=0
 gosub dwarf
 gosub rnd.100a:if a<3 gosub thief
 if mf goto travel2a
 if (cr<>df) or (cl>1) then goto no.dwarf
 zz$=rnd$:m=random(mc):m=m+(m=0)
 print \hl$"A SHORT BEARDED PERSON IS HERE, WITH A PILE OF GOLD!"of$
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
 wy$="":if cr<1 cr=1
 input #msg(cr),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 edit(0):copy #6,#8
 if (n=0) and (s=0) and (e=0) and (w=0) and (rc=0) then cr=cr+3:cr=cr mod nr:cr=cr+1:goto rd.room
rm.name
 z=instr("|",lo$):if instr("\|",lo$) z=0
 ww$=lo$:if z ww$=left$(lo$,z-1)
 if z lo$=mid$(lo$,z):else lo$=" "
 if flag(32) print "lo$="lo$
 if instr("*MNT",ys$) ew=ew+((ex-zw)/2):print "[CLIP, CLOP]";
 z=instr("T",lo$):if z cr=val(mid$(lo$,z+1)):print \"[A WAVE OF NAUSEA ENGULFS YOU, THEN SUBSIDES..]":goto rd.room
 if (instr("=+",lo$)) or (ww$="OUTER SPACE") goto rd.room2
 if left$(ww$,4)<>"THE " then if left$(ww$,2)<>"A " ww$="THE "+ww$
rd.room2
 print:if instr("HQ",ww$) yx$="*"
 if (not instr(left$(zu$,1),"AB")) or (i$="LOOK") setint(1):copy #8,#0 :setint("")
 if i$<>"LOOK" then if instr("DESERT",ww$) gosub rnd.10z:if z<4 pe=pe-1:print \"YOU SWEAT IN THE HEAT.."
 if not instr("@@",lo$) goto dingy
 a=instr("074",xi$):i$="DROWN IN THE WATER!":z=10
 if cl=6 a=instr("122",xi$):i$="CHOKE IN THE VACUME!":z=15
 if a=0 print \"YOU "i$:hp=hp-5:goto dingy
 i$="":if cl<>6 and instr("074,",xi$) i$="ROW THE DINGY.."
 if cl=6 and instr("122,",xi$) i$="FIRE STEERING ROCKETS.."
 if i$="" goto dingy
 print \"YOU "i$
 if cl<6 gosub rnd.10z:if z<4 print "GROWING A BIT TIRED";:ps=ps-1
dingy
 if instr("&",lo$) then if instr("123",xi$) print \"[TICK.. TICK..]":if instr("&&-",lo$) print \hl$"[ DANGER! RAD SUIT REQUIRED ]"of$
 i$=""
 if instr("**",lo$) i$="078":zz$="**":a$="YOUR FREEZING!":zt$="COAT":z=11
 if instr("&&",lo$) i$="124":zz$="&&":a$="YOU FEEL FUNNY!":zt$="RAD SUIT":z=16 :if not instr("123",xi$) i$="123"
 if i$="" goto coat
 if instr(zz$,lo$) then if not instr(i$,xi$) print \a$:pe=pe-1:ps=ps-1:hp=hp-2
 if instr(i$,xi$) a$="YOU WISELY WEAR THE "+zt$:else a$="TOO BAD YOU DON'T HAVE A "+zt$+"!":if i$="123" a$="YOU HAVE A STRANGE FEELING THAT YOU SHOULD KNOW SOMETHING.."
 zz$=zz$+"-":if instr(zz$,lo$) print \on$;a$;of$
coat
 if hp<1 pop:goto dead
 if not instr("LABYR",ww$) if not instr("DESERT",ww$) if not instr("@@",lo$) goto rd.room4
 if cl=6 print \on$"STAR FILLED BLACKNESS ENGULFS YOU."of$:goto rd.room4
 a$="":if cp=1 a$="[COMPASS READ]"
 gosub pal:if xy>0 a$="[PALINTAR GLOWS]"
 if pc=5 a$="[RANGER TRACKING]"
 if a$<>"" print \on$;a$;of$
 if a$="" print \"You lost your sense of direction..":return
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
 print \hl$"Congratulations! You Are a Level "xp" Player!"of$:return
;
tim.chk
 zw=ex:ex=clock(1)-ew
 if ex=>ev pop:i$="QUIT":goto lnk.sub
 return
;
rest
 if mw print \m$" WON'T LET YOU!":goto advent
 gosub tim.chk:if ev-ex<260 print \"YOU DON'T HAVE ENOUGH TIME!":goto advent
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
 print \i$:gosub add.log:goto advent
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
 pop:xx$=zt$:z=zr:i$="AUTODUEL":print\xx$" APPROACHES YOU..":goto lnk.msc5
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
 if n xz=(cr<=ri)*nr+cr-ri:i$="NORTH":gosub ply.loc6
 if s xz=cr+ri-((cr>x)*nr):i$="SOUTH":gosub ply.loc6
 if e xz=cr+1-((y=0)*ri):i$="EAST":gosub ply.loc6
 if w xz=cr+((y=1)*ri)-1:i$="WEST":gosub ply.loc6
ply.loc5
 return
ply.loc6
 zx$=":"+str$(xz)+"=":yy=instr(zx$,zw$)
 if yy then if not instr(i$,wx$) wx$=wx$+i$:print "THERE IS SOMEBODY TO THE "i$
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
 if zz$="blank" or zz$="" dy$=zy$+" IS SILENT..":goto ply.loc9
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
 i$=mid$(zw$,yw,1):z=val(i$):zz$=" IS HERE":dy$=" (Civy)"
 if instr(i$,"12B") dy$=" (Outlaw)"
 if instr(i$,"34C") dy$=" (-}---)"
 if instr(i$,"67D") dy$=" (\|/)"
 if instr(i$,"89E") dy$=" (==[])"
 if z=0 then if i$<>"0" then zz$=" LIES HERE UNCONCIOUS!":return
 if dc$="LOOK" return
 if z=0 zz$=" LOOKS INNOCENT.":return
 zz$=" GREETS YOU!":if random(100)>60 zt$=zy$:x=yx:zr=z
 if vv=z then if vv>2 return
 if instr(i$,"368") then if (vv=z+1) return
 if instr(i$,"479") then if (vv=z-1) return
 if instr(i$,"01368") zz$=" IS HERE.":return
 if vv=0 then if z>2 zz$=" SNEERS AT YOU!":return
 zz$=" GLARES AT YOU!":zt$=zy$:x=yx:zr=z
 return
;
show.file
 if flag(32) print "show.file-"f$
 setint(1):copy f$:setint(""):return
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
 if pa<6 print "(YOU FEEL POORLY)"
 return
;
return
 on nocar goto dropped
xv$
 xv$="(YOU FEEL A BIT ":goto tim.chk
;
misc
 on nocar goto dropped
 gosub xv$
 if i$="travel2" goto travel2
 if i$="travel1" goto travel1
 if i$="advent3" i$=dc$:goto advent3
 if (i$="flee3") or (i$="MALFUNCTION") goto flee2
 print \"BAD i$! i$="i$". Tell Trajan please!":goto advent
;
scn.dsp
 print #3 @4,23 right$("   "+str$(cl),4)
 print #3 @13,23 right$("    "+str$(cr),4)
 print #3 @4,24 right$("   "+str$(mm),4);
 print #3 @13,24 right$("    "+str$(ep),4);
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
 gosub tim.chk
 if ev-ex<300 i$="Weaken: YOU DON'T HAVE ENOUGH TIME":print \i$:goto add.log
 input @2\"Remove how many hit points? :"i$
 xy=val(i$):if xy<1 return
 if xy>(hp-5) print \"I won't remove that many!":return
 print \"So be it":hp=hp-xy:return
;
statue
 if mf=1 return
 dy$=dx$+m$:if left$(m$,4)="THE " dy$=dx$+mid$(m$,5)
 open #1, dy$:input #1,dy$:close
 print \"THERE IS A STATUE OF "dy$" HERE!":return
;
g.o.e.
 if not instr("GARDEN OF EDEN",ww$) return
 gosub rnd.10z:if (hp<25) and (z=5) print \"(Hit points increase)":hp=hp+1
 gosub rnd.10z:if (ps<25) and (z=5) print \"(Strength increases)":ps=ps+1
 gosub rnd.10z:if (pe<25) and (z=5) print \"(Energy increases)":pe=pe+1
 gosub rnd.100a:if a<6 print \"You are tempted to just stay here.."
 if (a<6) and (pi>5) pi=pi-1:print "(You feel dumber)"
 if (a<6) and (pw>5) pw=pw-1:print "(You feel less wise)"
 gosub rnd.100a:if a<6 m=121
 return
;
guard
 gosub rnd.10z
 if instr("\|/",ww$) then if z<3 m=67
 if instr("-}-",ww$) then if z<3 m=66
 if instr("=[]",ww$) then if z<3 m=65
 if (m) or (z>cl) or (mid$(zu$,7,1)="1") or (zn=70) or (cl>5) return
 gosub rnd.10z:if mid$(zu$,2,1)="0" then if z>cl return
 print \on$"SOMETHING EVIL, STALKS..."of$
 gosub rnd.10z:if z=1 print \hl$"IT IS HERE!"of$:m=70
 return
;
space
 if (cl<>6) or (not instr("@@",lo$)) then return
 gosub rnd.100a:if a>97 i$="METEOR":gosub lnk.msc6
 gosub rnd.100a:if a<3 m=119:print \\"SOMETHING COMES!"
 return
;
horse
 if not instr("GRASSY",ww$) return
 gosub rnd.100a
 if pc=5 a=a+15
 if pc=9 a=a+10
 if a>70 print \"The tracks are quite fresh here.."
 if a>93 m=134
 return

;....SUPPLY i$=NAME OF ROUTINE IN FOLLOWING MISC PROGRAMS
lnk.lgn
 dy$=ds$+"spur.logon":link dy$,"misc"
lnk.sub
 dy$=dz$+"spur.sub":link dy$
lnk.misc
 dy$=dz$+"spur.misc":link dy$,"misc"
lnk.msc2
 dy$=dz$+"spur.misc2":link dy$
lnk.msc3
 dy$=dz$+"spur.misc3":link dy$
lnk.msc4
 dy$=dz$+"spur.misc4":link dy$
lnk.msc5
 dy$=dz$+"spur.misc5":link dy$
lnk.msc6
 dy$=dz$+"spur.misc6":link dy$
lnk.msc7
 dy$=dz$+"spur.misc7":link dy$
lnk.msc9
 dy$=ds$+"spur.misc9":link dy$
lnk.cmbt
 dy$=dz$+"spur.combat":link dy$,"misc"
;
add.log
;.. i$=log message
 open #2,"a:add.log":append #2
 print #2,"Spur.main[] "i$" @"time$:close #2:return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print \"Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return
;

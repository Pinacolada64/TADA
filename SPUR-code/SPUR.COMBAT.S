;...spur.combat.s

 public return
 public misc
 public compile

 gosub xv$
advent
 on nocar goto dropped
 if ep>(999+(xp*100)) xp=xp+1:ep=1:gosub lvl.msg
 gosub tim.chk:if ev-ex<120 print "DUSK APPROACHES..."
 if (pe<1) and (ps<1) print \"YE HAVE STARVED TO DEATH!!":hp=0:z=1
 i$=" WEAKENS YOU!":zr=0:if pt>5 zr=2
 if mid$(zu$,2,1)="1"gosub rnd.10z:if z=5 print \"THE RING"i$:pt=pt-zr:if pw>5 pw=pw-1:if pi>5 pi=pi-1
 if mid$(zu$,3,1)="1"gosub rnd.10z:if z<4 print \"THE POISON"i$:hp=hp-2 :pt=pt-zr:if hp<1 z=7
 if mid$(zu$,4,1)="1"gosub rnd.10z:if z<4 print \"THE DISEASE"i$:hp=hp-1 :pt=pt-zr:if hp<1 z=8
 if pe<7 print \"YOU'RE THIRSTY.":if pe<4 print "VERY THIRSTY!"
 if ps<7 print \"YOU'RE HUNGRY.":if ps<4 print "VERY HUNGRY!"
 if (pe<3) or (ps<3) print \"YOU ARE BECOMING FAINT!"
 if hp<1 goto dead
 if not mw zs=0:goto advent2
 if instr(".",wy$) zs=0:goto advent4
 if zs=998 zs=997:goto advent2
 i$=str$(pc):if not instr(i$,"68") then if mid$(zu$,2,1)="0" goto advent4
 if zs>0 or zq>0 goto advent4
 z=pc*10+5:if mid$(zu$,2,1)="1" z=50
 if random(100)>z zs=999
advent4
 if zs=999 print\m$" LOST SIGHT OF YOU!":goto advent2 
advent5
 gosub m.attack:if vz=1 vz=0:print \"SURPRISE ATTACK..":gosub m.attack
 if zq=0 then if instr("]",wy$):gosub rnd.10a:if a<5 print\"DOUBLE ATTACK!":gosub m.attack
 zs=0
advent2
 di=0
 zz$="YOU SEE "
 if i print zz$;it$:else it$=""
 if wp print zz$;wp$:else wp$=""
 if fd print zz$;fd$:else fd$=""
 a$=" A DEAD ":if instr(":",wy$) a$=" A WRECKED "
 if md=1 print zz$;a$;m$
 if md=2 print zz$;m$" TRACKS.."
 if wr$="" print "(Must READY weapon)":vm=0:wa=0
 if wa=8 then if vn=0 then if not instr("STORM",wr$) print "(Must USE ammo)"
 if wa=10 then if vn=0 print "(not energized)"
 print ww$
prompt
 if dc$="" then dc$="?"
 print "RETURN="dc$:yz=ev-ex
 i$=str$(yz-((yz/60)*60)):i$=right$("00"+i$,2)
 zz$=""
 rz$=n1$
 gosub to.mixed
 zz$= zz$ + "[" + rz$ + "]" : rz$=""
 zz$=zz$+ "[" +str$(yz/60)+ ":" +i$+ "][" +str$(hp)+ " hp]"
 if (wa=8) or (wa=10) zz$=zz$+"["+str$(vn)+"]"
 print zz$" Cmd:";
 x=0:if vk>1 x=1
 if vu<6 then if instr("STORM",wr$) then if mw gosub rnd.10z:if z<4 print \\"THE "wr$" ASSERTS IT'S WILL!!":i$="ATT":vk=vk-x:goto advent3
 input @2 i$
advent3
 if i$="" then i$=dc$
 dc$=i$
 if instr("ATT",i$) vq=0:goto p.attack
 if i$="LURK" vq=2:goto p.attack
 if (i$="@I") and (info(5)) then dy$=ds$+"spur.sysop":link dy$
 if (i$="FLEE") or (i$="RUN") then goto flee
 if i$="CAST" goto lnk.msc3
 if left$(i$,1)=" " print \"There was a space in your command":goto prompt
 i$="advent3":goto lnk.main
;
flee
 if mw=0 print \"Nothing to flee from!":goto advent2
 if (instr("@@",lo$)) or (instr("**",lo$)) or (instr("<<",lo$)) print \"Can't flee from here..":goto advent
 if hp>7 if instr(".",wy$) then if not instr(":",wy$) gosub rnd.10z:if z<(xp/3) print \m$" BLOCKS THE PATH!":goto advent
 if pe<1 print \"NOT ENOUGH ENERGY!":goto advent
 i$="flee3":goto lnk.main
;
p.attack
 i$="":if zs=999 zs=0
 x1=0:if hp<9 print \"[+] HP DANGEROUSLY LOW [+]  (FLEE might be wiser!)"
 if vq=2 then if (a1+a2+a3)<1 print \"NO ALLIES - NO LURK!":vq=0:goto subpi
 if vq=0 then if wr$="" print \"MUST HAVE A WEAPON READIED.":goto subpi
 if (wa=8) or (wa=10) then if not instr("STORM",wr$) then if vn<1 then if vq<>2 vn=0:print \"NO AMMO READY!"\"(Try LURKing, if you have Allies)":goto subpi
 if wr$="" wa=0
 if (not mw) print \"NO MONSTER HERE.":goto subpi
 if vq<>2 goto lurk.b
 p2=2:if pc=9 p2=3
 if hp>20 p2=p2+1
 if hp<10 p2=p2-1:if hp<5 p2=p2-1
 zz$="":if ((wa=8) or (wa=10)) then if vn<1 zz$="*":p2=p2-1
 if instr("LIGHT",wr$) zz$="*"
 if p2<1 p2=0
 if vk>p2 vk=vk-p2
 if ((wa<8) or (zz$="*")) print " YOU LURK BEHIND YOUR ALLIES.":zq=0:goto p.a1
 print " YOU FIRE OVER YOUR ALLY'S HEAD..":zq=0
lurk.b
 if vr=55 input @2\"[S]ingle, B)urst, A)uto:"i$:if not instr(i$,"BA") i$="S"
 if vn>0 vn=vn-1:if i$="B" vn=vn-4
 if vn<1 vn=0
 if i$="A" vm=vm+(vn/3)+ma:vn=0
 if wa=8 zm=zm+1
 ep=ep+1
 zw$="CRACK!SWISH!SWISH!SWISH!SWISH!BLAM!!FIZZLESIZZLESWISH!BRRRT!"
 zx$="CRACK!SLASH!BASH!!THUNK!STAB! BLAM!!BOOOM!SIZZLECRASH!BRRRT!"
 p2=3
 if wa=2 then p2=ma-wa
 if (wa=3) and (ma<6) then p2=7-ma
 if (wa=3) and (ma>5) then p2=ma-3
 if (wa=5) and (ma<6) then p2=ma
 if (wa=5) and (ma>5) then p2=10-ma
 if (wa=8) or (wa=10) then p2=wa-ma
 p2=p2+zu+xp:if p2>7 p2=7
 b=2
 if not instr("E",wy$) goto no.evil
 if (pr=2) or (pr=8) b=4
 if (pr=3) or (pr=4) b=1
no.evil
 if not instr("G",wy$) goto no.good
 if (pr=2) or (pr=8) b=1
 if (pr=3) or (pr=4) b=4
no.good
 if pc=9 b=b+2
 if (zs=997) or (zq>0) print \"SURPRISE ATTACK!";:zq=0:zs=997:p2=p2+2:if vk>b vk=vk-b
 if p2<3 print \"(bad weapon choice)":if p2<2 p2=1
 print \"ATTACK WITH "wr$\:zz$=rnd$:b=random(wd*100):b=b/100+2
 if (sw$="") goto p.a0
 if (not instr("STORM",wr$)) or (vq=2) goto p.a6
 print \"FIRE FLASHES FROM THE "wr$"!":ms=0 
 if hp<5 goto p.a2
 if mid$(zu$,6,1)="0" print "THE BLACKFLASH BURNS YOUR HANDS! (-4 hp)":hp=hp-4 :goto p.a2
 gosub gauntlet:goto p.a2
p.a6
 if wr$<>sw$ print \"THE "wr$" IS INEFFECTIVE AGAINST "m$:goto advent
 p2=10
p.a0
 zy$="":if i$="B" zy$="BRRRRT "
 if i$="A" zy$="BBBRRRRRTTT "
 if vq=0 gosub rnd.10a:if a>(ws+2) print "(EASE OF USE HELPS!)"\:goto p.a5
 gosub rnd.10a
 if a>(p2-vq) print zy$;mid$(zw$,vr,6)" - MISSED":gosub scare:goto p.a1
p.a5
 b=b*ws/10:b=(b+zv)-1:if zs=997 b=b+3
 if (wa=8) or (wa=10) b=b+vm:if i$="B" b=b+2
 b=b-vq
 z=0:if vq=0 then if pc=8:gosub rnd.10z:if z=10 print \"ASSASIN; CRITICAL HIT!":b=b*2
 if instr("E",wy$) if wr$="EXCALIBUR" print \wr$" SCREAMS IN RAGE!":b=b*2
 if instr("G",wy$) if wr$="EXCALIBUR" print \wr$" SEEMS RELUCTANT..":b=b/2
 if b>10 b=(b*4)/5
 if mw=70 then if wr$="WRAITH DAGGER" print \"POWER EXPLODES FROM THE "wr$"!" :b=b+40
 if sw$<>"" then b=b+2
 print zy$;mid$(zx$,vr,6)" - "m$" HIT!";
 if not instr(";",wy$) print \:goto no.arm
 i$=" [Light armor]":z=0:if instr(";;",wy$) i$="[=[HEAVY ARMOR]=]":z=1
 print i$;:if wa<10 b=b-(xp*2)
 if z=1 b=(b-2)-xp
 if instr(";;",wy$) goto no.arm
 if (instr("STORM",wr$)) or (instr("CANNON",wr$)) or (wa=2) then b=b+(xp)
no.arm
 if (vr=43) or (instr("FIREBALL",wr$)) gosub rnd.10z:if z=5 gosub rnd.10z :z=(z/2)*xp+1:print \"Secondary heat damage to "m$" +"z"!";:b=b+z
 if b<1 b=0
 xu$="TAKES":if right$(m$,1)="S" xu$="TAKE"
 if b print \m$" "xu$" "b" DAMAGE.":else print \"NO DAMAGE!"
 if (b>4) and (pd<15) then gosub rnd.10z:if z<6 pd=pd+1:print xv$"MORE DEXTROUS)"
 ms=ms-b:if ms<1 goto p.a2
 gosub scare
p.a1
 x1=0:b=0:zz$=rnd$:z=random(3):if z=0 z=3
 if vu<4 z=vy
p.a1a
 if z=1 then if a1 then x1$=d1$:x1=h1:b=a1
 if z=2 then if a2 then x1$=d2$:x1=h2:b=a2
 if z=3 then if a3 then x1$=d3$:x1=h3:b=a3
 if vq=2 then if b=0 z=z+1:if z>3 z=1
 if vq=2 then if b=0 goto p.a1a
 if not b goto advent
 a=0:if instr("!",x1$) a=2
 print \x1$" ATTACKS "m$" - ";:
 gosub rnd.10z:z=z-a:if z>4 print "MISSED":goto advent
 zz$=rnd$:b=(a+b)/2
 if b>1 b=random(b)+1
 if b>8 b=8
 b=b+(xp/2)+a:i$=""
 if instr(";",wy$) i$="[Light armor] ":b=(b*2)/3
 if instr(";;",wy$) i$="[=[HEAVY ARMOR]=] ":b=(b*2)/3
 ms=ms-b:print i$;"HIT!"
 if b>0 print \m$" TAKES "b" DAMAGE.":else print \"NO DAMAGE!"
 if ms>0 goto advent
p.a2
 i$="HAS":if right$(m$,1)="S" i$="HAVE"
 i$=i$+" BEEN KILLED!"
 if instr(":",wy$) i$="IS NO LONGER FUNCTIONAL!"
 print \m$" "i$:md=1
 if x1 goto p.a3
 if pw<12 then pw=pw+1:print xv$"WISER)"
 mk=mk+1
 if instr("STORM",wr$) print \"THE "wr$" SCREAMS IN GLEE!!"\
 if (mf) or (instr("<",wy$)) goto p.a3
 x$=right$("000"+str$(mw),3)+","
 if xm<15 then xm=xm+1:xm$=xm$+x$:goto p.a3
 xm$=mid$(xm$,5)+x$
 
p.a3
 i$="p.a3":goto lnk.misc

subpi
 if pi>1 then pi=pi-1:print xv$"DUMBER)"
 goto advent
;
gauntlet
 if mid$(zu$,6,1)="0" z=0:return
 print "THE GAUNTLETS TAKE HIT..";:gosub rnd.10z
 if z=1 print "DESTROYED!!":i$="zu$":zw=6:zw$="0":zt=5
 if z=1 gosub lnk.misc
 return

m.attack
 vu=vu+1
 if vu=1 if vn>0 if vz<>1 if zs<>997 if not instr("LIGHT",wr$) if zq=0 print \"MISSILE: FIRST STRIKE!"\:return
 if vu=1 if wa=5 print \"POLE WEAPON: ";:gosub rnd.10a:if a+(ma*3)+2<pd print "YOU MANAGE TO GET FIRST STRIKE!"\:return
 if vu=1 if wa=5 print "OPPS, DIDN'T GET FIRST STRIKE.."\
 if mw=120 print \m$" WAITS PATIENTLY..":return
 i$="S ":zz$="IS":if right$(m$,1)="S" i$=" ":zz$="ARE"
 if zq>0 print \m$" STAND"i$"AROUND..":return
 if zs=997 print\m$" "zz$" FURIOUS!":if (mw=65) or (mw=66) or (mw=67) then if not instr("GUARDS",m$) gosub mad.gd
 z=0:if instr("+",wy$) gosub rnd.10z:if (ms<(z+3)) or (z>8) then z=99
 if instr("++",wy$) then if z>6 then z=99
 if z=99 i$="MON.CST":gosub lnk.msc4
 gosub rnd.10z:if (not instr("#",wy$)) or (z>2) goto medusa
 print\m$" CASTS TURN TO STONE ON YOU!"
 gosub rnd.10z:if z>1 print"...IT FAILED!":return
 print "...ARGG!! YOU ARE TURNED TO STONE!"
 pop:z=6:goto dead
medusa
 a$="S ":if right$(m$,1)="S" a$=" "
 print \m$" ATTACK"a$;:x=1
 gosub rnd.10a:if a>4 then a=1
 a$=n1$:d=1:if vu<3 a=vy+1
 if not instr("-",wy$) goto no.fire
 gosub rnd.10z:zz$="FIRE!":a=2:if cl>5 zz$="LAZER FIRE!":a=5
 if z>a goto no.fire
 z=0:if instr(";;",wy$) zz$="IT'S PLASMA CANNON! ]======[]":z=4
 print \a$" WITH "zz$:zz$=rnd$:a=(random(50)/10)+5+z
 if cl>5 then if instr("LAZ.SH",ys$):print \"[ THE LAZER SHIELD FLASHES! ]" :a=a/2
 goto dragon
no.fire
 if vq=2 zz$=rnd$:a=random(3)+2:if a>4 a=2
lurk.a
 if (a=2) and (a1>0) then a$=d1$:d=2
 if (a=3) and (a2>0) then a$=d2$:d=3
 if (a=4) and (a3>0) then a$=d3$:d=4
 if vq=2 then if d=1:a=a+1:if a>4 a=2
 if vq=2 then if d=1 goto lurk.a
 print a$;
 if d=1 i$="996877889":i$=mid$(i$,pr,1):z=val(i$):z=((z+ma)/2)+3:gosub rnd.10a:if a>z print \\m$" MISSES OVER YOUR HEAD!":return
 if d=1 then if pc=5 gosub rnd.10a:if a=5 print \\"YOU DODGED THE BLOW!":return
 p1=(ma+zo-1)/2:if zs=997 p1=p1+2
 if p1<3 p1=3:else if p1>8 p1=8
 gosub rnd.10a
 if a<p1 then print " - HIT!":else print " - MISSES!":return
 gosub rnd.10a:gosub rnd.10z:a=a+z:gosub rnd.10z:a=(a+z)/3
 if d<>1 goto m.a1
 a=a+(8-ma):if zs=997 a=a+((12-ma)/2)
 if instr(".",wy$) a=a+random(5)
 yz=2+xp:if yz>8 yz=8
 gosub rnd.10z:if z<yz gosub gauntlet:if z>0 a=a-1:print " -1 HIT"
 if instr(mid$(zu$,7,1),"23") print "[WIZARDS GLOW FLASHES]":a=a-2
 xu$=" ":if right$(m$,1)="S" xu$="S "
 if sh<1 print "(A SHIELD MIGHT HELP!)":goto m.att.1
 gosub rnd.10z:if instr(left$(zu$,1),"BC") z=z-2
 i$="[":if ma>6 i$="[LITTLE BUGGER"+xu$:z=z+(ma-6)
 if ma<4 z=z-(4-ma)
 if z>yz print \i$"GOT PAST YOUR SHIELD]":goto m.att.1
 if ma=4 print "[WAP] ";
 if ma=3 print "[THUD] ";
 if ma=2 print "[CRUNCH!!] ";
 z=2+(sh/25)+random(3)
 if pc=4 z=z+2:print "PALADIN ";
 if instr(left$(zu$,1),"BC") z=z+1:print "TRAINED ";
 if z>a z=a
 zz$=rnd$:yz=1+random(10-ma):if instr(left$(zu$,1),"BC") yz=yz-1
 sh=sh-yz:a=a-z:print "SHIELD BLOCKS "z" DAMAGE ";
 z=0:if ma<6 z=7-ma:if instr(left$(zu$,1),"BC") z=z-1
 z=z*2:if random(60)<z print \"IT'S TORN FROM YOUR HAND AND SMASHED!!";:sh=0
 if sh<0 then sh=0
 print "("sh"%)":if a<1 a=0:goto no.ar
m.att.1
 yy=0
 if ar<1 print "(ARMOR MIGHT HAVE HELPED!)":goto no.ar
 zz$=rnd$:z=2+(ar/10):p1=2+random(z)
 p2=1+(ar/20)+random(3):if p2>a p2=a
 gosub rnd.10z:if ma<5 z=z-(5-ma)
 i$="[":if ma>6 z=z+(ma-6):i$="[THE LITTLE CREEP"+xu$
 if z>p1 print i$"MISSED YOUR ARMOR]":goto no.ar
 if ma=2 print "[THUD!] ";
 if ma=3 print "[UFFF] ";
 ar=ar-yz:a=a-p2:yy=1:if p2 print "ARMOR BLOCKS "p2" HITS!";:if random(100)<(yz*2) print \"IT'S PARTLY RIPPED OFF!!";:ar=ar-50
 if ar<0 then ar=0
 print " ("ar"%)"
no.ar
 if (sh<=0) and (hs) print \"SHIELD GONE.":hs=0
 if (ar<=0) and (ra) print \"ARMOR GONE.":ra=0
 if instr(".",wy$) a=a+(random(xp+1)/3)
 if a<1 return
 if pc=2 then if (hp+a)<30 gosub rnd.10z:if z=5 print \"YO! YOU REGENERATE HIT POINTS!":hp=hp+a:goto druid
 b=a:a=random(a*100):a=a/100+1:b=b-a:b=b/2:if ps>b then if b>0 ps=ps-b:print xv$"MORE FATIGUED)"
dragon
 if a>hp-1 then if a1+a2+a3>0 gosub sac.ally
 if not a goto druid
 hp=hp-a:print  \"YOU TAKE "a" DAMAGE."
 gosub rnd.10z
 if instr("*",wy$) then if z<3 print \"ARGH! YOU HAVE BEEN POISONED!" :i$="zu$":zw=3:zw$="1":zt=5:gosub lnk.misc
 gosub rnd.10z
 if instr("@",wy$) then if z<3 print \"YUK!! YOU HAVE BECOME DISEASED!" :i$="zu$":zw=4:zw$="1":zt=5:gosub lnk.misc
 gosub rnd.10z
 if instr("&",wy$) then if ep>(xp*13) then if z<3 print \"ARRGG! "m$"'S BITE DRAINS YOU!":ep=ep-(xp*13):print "(LOSS = "xp*13" EXPERIENCE)"
 if hp<1 pop:z=4:goto dead
 if (a>4) and (pd>0) then pd=pd-1:print xv$"LESS DEXTEROUS)"
druid
 if cp=1 gosub rnd.100a:if (a>54) and (a<60) then cp=0:print \"COMPASS DAMAGED!":pop:i$="clr.cmps":goto lnk.misc
 if ps<4 then wr$="":print \"YOU ARE TOO WEAK TO WIELD YOUR WEAPON!"
 return
 
m.a1
 if d=2 i$=d1$
 if d=3 i$=d2$
 if d=4 i$=d3$
 if i$="*" return
 a=a-1:zt$=i$+" THROWS DOWN ALL WEAPONS AND RUNS AWAY!"
 gosub rnd.10z:z=z-1
 if vk<800 z=z+1:if vk<400 z=z+1
 if vk>1200 z=z-1:if vk>1600 z=z-1
 if z<1 z=0
 if instr("!",i$) print "[Light Armor] ";:a=a-2:z=0
 if a>0 i$=i$+" TAKES "+str$(a)+" DAMAGE"
 if a<1 i$="No damage!"
 if (d=2) and (a1>0) wx$=d1$:print i$:a1=a1-a:if a1<1 print d1$" is dead." :d1$="*":a1=0:x=h1:h1=0:goto fre.ally
 if (d=2) and (z>a1) then print zt$:zt$="run":d1$="*":a1=0:x=h1:h1=0
 if (d=3) and (a2>0) wx$=d2$:print i$:a2=a2-a:if a2<1 print d2$" is dead." :d2$="*":a2=0:x=h2:h2=0:goto fre.ally:
 if (d=3) and (z>a2) then print zt$:zt$="run":d2$="*":a2=0:x=h2:h2=0
 if (d=4) and (a3>0) wx$=d3$:print i$:a3=a3-a:if a3<1 print d3$" is dead." :d3$="*":a3=0:x=h3:h3=0:goto fre.ally
 if (d=4) and (z>a3) then print zt$:zt$="run":d3$="*":a3=0:x=h3:h3=0
 if zt$="run" goto fre.ally
 return
;
lvl.msg
 print\"Congratulations! You Are a Level "xp" Player!":return
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:i$="QUIT":goto lnk.sub
 return
;
dead
 hp=0:xn=sn:sn=0
 i$="dead2":goto lnk.msc6

fre.ally
 print \"(Writing in news log..)"
 if (a1+a2+a3)<1 then ai=0:ai$=""
 dy$=dx$+"battle.log":open #1,dy$:append #1
 dy$="SNIFF":if i$=wx$ dy$="SACRIFICE"
 if (zt$="run") or (zt$="evil") then dy$="MORALE FAILURE"
 print #1, left$(date$,6)yr$" "time$"- "dy$
 dy$=wx$+", DIED FIGHTING "+m$+","
 if zt$="run" dy$=wx$+" FLED AFTER A HIT FROM "+m$
 if zt$="evil" dy$=wx$+" SEEING "+n1$+" IN TROUBLE,"
 print #1, dy$
 dy$="WHILE IN SERVICE TO "+n1$
 if i$=wx$ dy$="TO SAVE THE LIFE OF "+n1$+"!"
 if zt$="evil" dy$="RAN AWAY!"
 print #1, dy$
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 vq=0:zt$="":if x=0 then return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
dropped
 i$="SPUR.COMBAT":dy$=ds$+"spur.logon":link dy$,"quit3"
; ^ target ok, writes carrier dropped msg to log, quits game

show.file
 setint(1):copy f$:setint(""):return
;
rnd.10a
 zz$=rnd$:a=(random(999)/100)+1:return
rnd.10z
 zz$=rnd$:z=(random(999)/100)+1:return
rnd.100a
 zz$=rnd$:a=(random(999)/10)+1:return
;
return
 on nocar goto dropped
xv$
 xv$="(YOU FEEL A BIT ":return
;
misc
 on nocar goto dropped
 if un=1 print "spur.combat--";:gosub comp.ck
 gosub xv$
 if i$="kill.mon" x1=0:mf=0:goto p.a2
 if i$="p.attack" goto p.attack
 if i$="advent5" gosub advent5
 goto advent
;
mad.gd
 gosub rnd.10z:z=z/3+2:ms=ms+((ms/2)*z):m$="THE "+str$(z+1)+" GUARDS" :wy$="|<]>"
 print \"The guard blows on a whistle, and "z" more guards come running!"
 print "They are not amused either, by your treachery..."
 return
;
sac.ally
 i$="":x=0
 if a1>0 i$=d1$:x=h1:d1$="*":a1=0:h1=0:goto sac.a
 if a2>0 i$=d2$:x=h2:d2$="*":a2=0:h2=0:goto sac.a
 if a3>0 i$=d3$:x=h3:d3$="*":a3=0:h3=0
sac.a
 if i$="" return
 wx$=i$:a=0:zt$="":i$=""
 if random(800)+200>vk if not instr("!",wx$) print \wx$" SEES YOU ARE ABOUT TO DIE, AND RUNS AWAY!":zt$="evil":gosub fre.ally:goto sac.ally
 print \wx$", SEEING YOU ARE ABOUT TO DIE,"\"LEAPS IN FRONT TO TAKE THE DEATH BLOW!":goto fre.ally

scare
 if un=1 print "scare: vr="vr
 if (random(10)<>5) or (vu>1) return
 if (vr<>31) and (vr<>55) and (vr<>37) then return
; thunderbolt, storm crossbow or small cannon
 if (instr(":",wy$) or instr(".",wy$)) return
 print \"THE THUNDERING NOISE OF THE "wr$\"SCARES "m$" AWAY!"
 mw=0:md=2:ms=0:pop:goto advent

;....SUPPLY i$=NAME OF ROUTINE IN FOLLOWING MISC PROGRAMS
lnk.lgn
 dy$=ds$+"spur.logon":link dy$,"misc"
; ^ never called? misc label doesn't exist

lnk.sub
 dy$=dz$+"spur.sub":link dy$

lnk.misc
 dy$=dz$+"spur.misc":link dy$,"misc"
; ^ target ok, links to commands

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

lnk.main
 dy$=dz$+"spur.main":link dy$,"misc"
; ^ target ok

main.rtn
 dy$=dz$+"spur.main":link dy$,"return"
; sets xv$, returns here, continues on

compile
 if un=1 print \"Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return
;

to.mixed
 gosub to.lower
 l0$="":y=0
 for yy = 1 to len(rz$)
 x=asc(mid$(rz$,yy,1))
 if (x=32) and (len(l0$)=0) then goto tm.loop
 if (len(l0$)=0) and (x>96) and (x<123) then l0$=chr$(x-32):goto tm.loop

; if x=32 then y=1:l0$=l0$+chr$(32):goto tm.loop
;Force upper case after a non alpha character
 if (x>96) and (x<123) goto Skip.conv
 if (x>64) and (x<91) goto Skip.conv 
 y=1:l0$=l0$+chr$(x):goto tm.loop
Skip.conv
 if (y=1) and (x>96) and (x<123) then l0$=l0$+chr$(x-32):y=0:goto tm.loop
 l0$=l0$+chr$(x)
tm.loop
 next
 rz$=l0$:return
 
to.lower
 l0$=""
 for yy=1 to len(rz$)
 x=asc(mid$(rz$,yy,1)):if (x>64) and (x<91) then x=x+32
 l0$=l0$+chr$(x)
 next
 rz$=l0$:return

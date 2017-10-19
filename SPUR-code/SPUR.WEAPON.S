
; spur.weapon.s

 on nocar goto dropped

 public compile

 if flag(32) print "spur.weapon -";:gosub comp.ck
 if i$="SPECIAL" gosub special:goto shop.rtn
 if i$="SPECIAL2":gosub special:goto ship.rtn
 if i$="READY" goto rdy.wep
 i$="Bad value of i$ in spur.weapon! i$="+i$
 print i$:gosub write.lg:goto advent
;
rdy.wep
 zr=0:if mw print \"(Wiser to READY, before meeting a monster!)"
 if ps<4 print \"Not enough strength to ready a weapon!":goto advent
 zt$="":gosub pr.weapons:if xw=0 goto advent
rdy.wep2
 input @2\"Ready which Weapon number? "a$:if a$="" goto advent
 if instr(" ",a$) print \"There was a space in your entry.":goto rdy.wep2
 x=val(a$):if (x<1) or (x>xw) print \"You don't have that Weapon!":goto rdy.wep2
 y=(x*4)-3:zp=val(mid$(xw$,y)):yw=vo
 a=0:if pi>2 a=2
 if (wr$<>"") and (vo=zp) then print \"YOU ALREADY HAVE THE "wr$" READIED!"\"(You feel dumber)":pi=pi-a:goto advent
 if instr("STORM",wr$):print \\"THE "wr$" HOWLS IN RAGE!":print "'I REFUSE! YOU ARE MINE!!'":zr=vo:da$="THE "+wr$:goto spec4
 if (pc<>9) or (vk<1200) if zp=17 goto spec3
 open #1,dy$:position #1,34,zp,2
 input #1,ws$\ws,wd\wa:close
 if pc<>1 if instr("FIREBALL",ws$) wr$="" print \"Yelp! You burn your fingers!":goto advent
 vm=0:if instr("DEATH AMULET",ws$) gosub amulet
 i$=" [ BEST TARGETS ]: "
 setint(1):print \"Weapon class: ";
 if wa=2 print "Hack/Slash/Bash.":print i$"SWIFT, Small, Short";
 if wa=3 print "Poke/Jab.":print i$"HUGE, SWIFT,";
 if wa=5 print "Pole/Ranged.":print i$"MAN SIZED, Big, Short";
 if wa=8 print "Projectile (+10% surprise).":print i$"HUGE, Large";
 if wa=9 print "Proximity.":print i$"Anybody..";
 if wa=1 wa=10:print "Energy weapon!":print i$"HUGE, Large";
 if (wa=10) or (instr("STORM",ws$)) or (instr("CANN",ws$)) or (wa=2) print ", Light Armor";
 print \"Required dex: "ws+4
 if ws+4>pd print"Not dextrous enough for this weapon":setint(""):goto advent
 zz$=mid$(ws$,3,1):vr=val(zz$)*6+1:wr$=mid$(ws$,4)
 n$=wr$:i$="":gosub special:zv=yz:zu=yx
 zz=ws:if xp>1 then ws=((xp+2)*ws)/3
 print " Base damage: "wd
 zs=((ws+1)-zz)+yz+yx
 print "  Your skill: "zs
 print " Ease of use: "10-zz
 if xp=1 then if wa=8 then if not instr("STORM",wr$) print "(Get ammunition at O)llys in the Shop)"
 if(vr=43)or(instr("FIREBALL",wr$))print"(10% chance of secondary heat damage)"
 setint("")
 f$=dx$+"misc.data":open #2,f$
 if vo>0 then if vp<100 position #2,250,pn,17+(vo*3-3):print #2,vp
 vo=zp position #2,250,pn,17+(vo*3-3):input #2,vp:close
 print "Battle exp. : "vp;
 if vp<40 print " [ GREEN ]"
 if vp>39 then if vp<99 print " [ VETERAN ]":zv=zv+1:zu=zu+1
 if vp>98 print " [ ELITE ]":zv=zv+xp:zu=zu+2
 if wz$<>wr$ vn=0
 if wr$="EXCALIBUR" gosub excalibur
 wz$=wr$:print \wr$" READIED.":goto advent

amulet
 print \\\\'
WARNING!!!

Readying the Death Amulet has a 20%
possibility of instand death!!'
 a=2:if instr("076",xi$) a=1:print \"The AMULET OF LIFE reduces this to 10%!"
 input @2\"Still want to?!? Y/N" i$:if i$<>"Y" pop:goto rdy.wep2
 print \\"DEADLY POWER STIRS. IT LIVES.."
 zz$=rnd$:zz=random(99)/10+1:if zz>a wd=50:print \"YOU LIVE!":return
 if gm=1 hp=1:print \\"ARGH!! IT TURNS ON YOU, BUT GOD MODE SAVES YOU FROM DYING.":return
 print \\"ARGH!! IT TURNS ON YOU!!"\"YOU ARE TORN TO PIECES. LITTLE ONES.."
 pop:hp=0:xn=sn:sn=0:z=9:i$="dead2":goto lnk.misc
;
pr.weapons
 zt=0:xu$=""
 if (xw=0) or (xw$="") print \"No Weapons.":xw=0:xw$="":return
 dy$=dw$+"weapons"
 open #1,dy$
 print:for x=1 to xw
 zw=wc:zz$=xw$:gosub pr.sub
 position #1,34,a,2
 input #1,zz$\xu,xv\yy
 setint(1)
 zz$=mid$(zz$,4):zz$=str$(x)+") "+zz$:print zz$
 if instr("STORM",zz$) zt=zt+1:xu$=xu$+right$("00"+str$(a)+",",4)
 if key(1) then if zt$="invent" x=xw:zt$="abort"
 next:close:return

pr.sub
 y=(x*4)-3:a=val(mid$(zz$,y))
 if (a>zw) or (a<1) i$="Bad storage string! "+zz$:print \\\\i$:gosub write.lg :i$="QUIT":goto lnk.sub
 return
;
linkmain
 setint(""):dy$=ds$+"spur.logon":link dy$,"main"
lnkmain1
 setint(""):dy$=dz$+"spur.shop":link dy$,"main1"
advent
 setint(""):dy$=dz$+"spur.main":link dy$
shop.rtn
 setint(""):dy$=dz$+"spur.shop":link dy$,"return"
ship.rtn
 setint(""):dy$=ds$+"spur.ship":link dy$,"return"
dropped
 i$="SPUR.WEAPON":dy$=ds$+"spur.logon":link dy$,"quit3"
lnk.misc
; (supply i$=name of routine in spur.misc)
 dy$=dz$+"spur.misc":link dy$,"misc"
lnk.sub
; supply i$=name of routine to link to.
 dy$=dz$+"spur.sub":link dy$
;
rnd.10a
 zz$=rnd$:a=random(999):a=(a/100)+1:return
rnd.100a
 zz$=rnd$:a=random(999):a=(a/10)+1:return
;
special
;.. returns yz & yx. Also called from Shop.
 yz=0:yx=0:n$="    "+n$:n$=right$(n$,4)
 if pc=1  if instr(n$,"BALL,TAFF,BOLT") yz=2:yx=1:goto spec.1
 if pc=1 yx=-2:if instr(n$,"GGER,NIFE") yx=1
 if pc=2  if instr(n$,"ABRE,LING,ELIN,CLUB,PEAR,TAFF,TAKE, BOW,ILUM") yz=1:yx=1
 if pc=3 yz=2:yx=1:if wa=8 yz=0:yx=-1
 if pc=3  if wa=10 yx=yx+1
 if pc=4 yx=1:if wa=8 yx=-1
 if pc=5  if instr(n$,"SBOW,WORD,ABRE") yz=1:yx=1
 if pc=5  if wa=5 yz=-1:yx=-1
 if pc=6  if wa=3 yz=1:yx=1:goto spec.1
 if pc=6 yx=-1
 if pc=7  if instr(n$,"SBOW, BOW")yz=2:yx=2
 if pc=7  if (wa=2) or (wa=5) yz=-1:yx=-2
 if pc=8  if wa=3 yz=2:yx=1
 if pc=8  if instr(n$,"SBOW, BOW,LING") yz=-1:yx=-1
 if pc<>9 goto spec.1
 if instr(n$,"WORD,ANCE,ABRE") yz=2:yx=3
 if n$="IBUR" yz=4:yx=4
 if wa=8 yz=0:yx=-1
spec.1
 if pr=1  if instr(n$,"GNUM,OWER,POON, GUN,SKET,NNON, UZI,MITE,ASER,IFLE") yx=yx+1
 if pr=2  if instr(n$,"CLUB,MMER,KLES") yz=yz+3
 if pr=3  if instr(n$,"NIFE,GGER") yz=yz+1:yx=yx+2
 if pr=4  if instr(n$," BOW") yz=yz+1:yx=yx+1
 if pr=5  if instr(n$,"LING") yz=yz+1:yx=yx+2
 if pr=5  if wa=5 yz=yz+1:yx=yx+2
 if pr=6  if instr(n$,"GGER,NIFE,TTLE") yz=yz+1:yx=yx+2
 if pr=7  if instr(n$,"EAXE,KAXE,CHET,SBOW, AXE") yz=yz+1:yx=yx+1
 if pr=8  if instr(n$,"NIFE,GGER, UZI,KLES") yz=yz+2
 if pr=8  if instr(n$,"GNUM,OWER,POON, GUN,SKET,NNON, UZI") yx=yx+2
 if pr=9  if instr(n$,"SBOW, BOW,WORD") yx=yx+1
 if instr(n$,"PHASER")  if yz<1 yz=1
 if left$(i$,7)="SPECIAL" return
 if not instr("STORM",wr$)  if zt>0 zt=2:goto spec5
 if not instr("STORM",wr$) return
 if yz+yx<1 goto spec3
spec5
 if zt>1 print \\\"THE STORM WEAPON YOU IGNORED,":print "HOWLS IN JEALOUS RAGE!!":da$="THE "+wr$:goto spec4
 print \\\"THUNDERING LAUGHTER SHRIEKS FROM THE"
 print wr$"! 'I ACCEPT THEE AS":PRINT "MY SERVANT!'"
 print \"A jolt of power surges up your arm.."\:yz=yz+2:yx=yx+2:return
spec3
 if not instr("STORM",wr$) if wr$<>"EXCALIBUR" wr$="STORM WEAPON"
 da$=wr$:if instr("STORM",wr$) da$="THE "+wr$
 print \\\"A THUNDERING HOWL OF RAGE BLASTS FROM"
 print da$"! 'YOU ARE NOT MINE!!'"
spec4
 pop:print \"A BOLT OF POWER BLASTS YOU BACKWARDS!"
 gosub rnd.10a:print "YOU TAKE "a" DAMAGE!"\:hp=hp-a
 if hp<1 if gm=1 hp=1:print "GOD MODE saves you from dying."
 if hp<1 xn=sn:sn=0:z=5:i$="dead2":goto lnk.misc
;... drop weapon. zr is weapon # to be dropped
 if zr>0 goto spec7
spec6
 da$="MYSTERIOUS WEAPON"
 if not instr(",",xu$) wr$="":goto advent
 zr=val(left$(xu$,3)):if zr=zp xu$=mid$(xu$,5):goto spec6
spec7
 n$="00"+str$(zr)+",":n$=right$(n$,4)
 y=instr(n$,xw$):if y=0 wr$="":goto advent
 print \da$" DISTINGRATES!"
 dy$=dx$+"weapons":open #1,dy$
 l=len(xw$):a=val(mid$(xw$,y,3))
 xw=xw-1:if xw=0 then xw$="":goto drp.wpn2
 if y=1 then xw$=mid$(xw$,5):goto drp.wpn2
 if (y+4)>l then xw$=left$(xw$,y-1):goto drp.wpn2
 xw$=left$(xw$,y-1)+mid$(xw$,y+4)
drp.wpn2
 cb$="2":if a>10 then cb$="1"
 position #1,34,a:print #1,cb$:close
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"- THUNDER!"
 print #1, da$" DISTINTEGRATED IN RAGE"
 print #1, "WHEN INSULTED BY "n1$"!!"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 wr$="":print \"(No weapon readied..)":goto advent

excalibur
 print \'
A fiery sheen engulfs the huge sword, as sweet music hums softly from it's
terrible sharp blade..'
 return
;
show.file
 setint(1):copy f$:setint(""):return
;
write.lg
 close:open #1,"a:add.log"
 append #1:print #1,"[Spur.weapon] "i$:close:return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):ready dr$:return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return
;

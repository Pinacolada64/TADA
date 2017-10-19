
; spur.sub.s

 on nocar goto dropped

 public show3
 public quit
 public misc
 public compile

 if un=1 print "spur.sub -";:gosub comp.ck
 if i$="QUIT" goto quit
 if i$="INV" gosub invent:goto advent
 if i$="INV2" gosub invent:goto lnk.ship
 if i$="WEAR" goto wear
 if i$="EAT" goto eat
 if i$="DRINK" goto drink
 i$="Bad value of i$ in spur.sub! i$="+i$
 print i$:gosub write.lg:goto advent
;
;
wear
 gosub pr.items:if xi=0 goto advent
wear2
 input @2\"Wear which number Item? "a$:if a$="" goto advent
 if instr(" ",a$) print \"There was a space in your entry":goto wear2
 x=val(a$):if x<10 then if len(a$)>1 print \"Huh?":goto wear2
 if (x<1) or (x>xi) print \"You don't have that item.":goto wear2
 y=(x*4)-3:x=val(mid$(xi$,y))
 open #1,dy$:position #1,30,x,2
 input #1,n$\it:close
; gauntlets
 if x=68 i$="zu$":zw=6:zw$="1":zt=2:gosub lnk.misc:goto wear3
 if x=113 print \"BATTLE ARMOR WORN."\"New armor rating=125%":ar=125:goto wear3
 if x=115 goto pwr.ar
 gosub spec.itm
 if left$(n$,1) <> "A" print \"This is not an Armor!":goto advent
 if ar<100 then it=it*10:ar=ar+it:ra=1:if ar>100 then ar=100
 zz$="(Max armor rating for you is "
 if (pr=3) or (pr=5) or (pr=6) then if ar>50 print zz$"50%)":ar=50
 if (pc=8) or (pr=4) then if ar>60 print zz$"60%)":ar=60
 print "(New armor rating: "ar"%)"
wear3
 ep=ep+1:if pi<8 then pi=pi+1:gosub smart
 print \mid$(n$,3)" worn.":gosub clr.item:goto advent
;
pwr.ar
 print \"POWER ARMOR ENERGIZED!"\"Protects from nuclear back-blast for this play session!"\"New armor rating=150%"
 if not instr("pwr.ar",ys$) then if len(ys$)<240 ys$=ys$+"*pwr.ar*"
 ar=150:goto wear3
;
spec.itm
 i$=right$("00"+str$(x)+",",4)
 if not instr(i$,"074,076,078,082,097,122,123,124,138,") return
 print \"The "mid$(n$,3)" will automatically be used at the proper time."
 pop:goto advent
;
eat
 if mw print \"(Eating during a fight?!)"
 gosub pr.food:if xf=0 goto advent
eat2
 input @2\"Eat which number Item? "a$:if a$="" goto advent
 if instr(" ",a$) print \"There was a space in your entry.":goto eat2
 x=val(a$):if x<10 then if len(a$)>1 print \"Huh?":goto eat2
 if (x<1) or (x>xf) print \"You don't have that item.":goto eat2
 y=(x*4)-3:x=val(mid$(xf$,y))
 open #1,dy$:position #1,26,x,2
 input #1,gs$\gs:close
 if left$(gs$,1)<>"F" print \mid$(gs$,3)" cannot be eaten.":goto advent
 if instr("PILL",gs$) goto pill
 if instr("OLD ",gs$) goto old
 xu$="HUNGRY":gosub hun.slv:if zr>0 goto eat3
 zz=18:if pr=2 zz=22
 a=random(gs*100):a=a/100+1:a=a mod 8:if ps<zz then ps=ps+a:print "(Some strength returns..)":if pc=2 print "(Druid; heals even more!)":ps=ps+2
 zz=25:if pr=2 zz=27
 if hp<(zz+xp) hp=hp+a
 if ps<15 print \"Your hunger lessens."
 if ps>14 print \"Your appetite is satisfied.":if (pe>15) and (pt<18) then pt=pt+1:print "(You feel a bit more healthy)":if pc=2 print "(Druid; even more so!)":pt=pt+1
eat3
 ep=ep+1
 gosub clr.food:goto advent
;
drink
 if mw print \"(Drinking during a fight?!)"
 if cl=5 then if cr=105 goto fountain
 if fd$="POOL OF WATER" goto pool
 gosub pr.food:if xf=0 goto advent
drink2
 input @2\"Drink which number Item? "a$:if a$="" goto advent
 if instr(" ",a$) print \"There was a space in your entry.":goto drink2
 x=val(a$):if x<10 then if len(a$)>1 print \"Huh?":goto drink2
 if (x<1) or (x>xf) print \"You don't have that item.":goto drink2
 y=(x*4)-3:x=val(mid$(xf$,y))
 open #1,dy$:position #1,26,x,2
 input #1,gs$\gs:close
 if left$(gs$,1)<>"D" print \mid$(gs$,3)" cannot be drunk.":goto advent
 if instr("POTION",gs$) goto potion
 if instr("SERUM",gs$) goto serum
 if instr("MOONSHINE",gs$) goto moonshin
 xu$="THIRSTY":gosub hun.slv:if zr>0 goto drink3
 zz=18:if (pr=1) or (pr=9) zz=22
 a=random(gs*100):a=a/100+1:a=a mod 6:if pe<zz then pe=pe+a+1:print "(Some energy returns)":if pc=2 print "Druid; even more energy!)":pe=pe+1
 zz=25:if pr=2 zz=27
 if hp<(zz+xp) hp=hp+a
 print \"You feel refreshed."
 if pe>14 print \"...burp..."
 if (pe>15) and (ps>15) and (pt<18) then pt=pt+1:print "(You feel a bit more healthy)":if pc=2 print "(Druid; even more so!)":pt=pt+1
drink3
 ep=ep+1
 gosub clr.food:goto advent
;
fountain
 a=2:gosub messages:zz=26+xp:if pr=2 zz=zz+2
 if hp<zz hp=zz
 if ps<26 ps=26
 if pt<26 pt=26
 if pi<26 pi=26
 if pe<26 pe=26
 if pw<26 pw=26
 if pd<26 pd=26
 gosub cure.p:gosub cure.d
 if (instr("076",xi$)) and (mid$(zu$,8,1)="0") then a=3:gosub messages:i$="zu$" :zw=8:zw$="1":zt=2:gosub lnk.misc
 if instr("142",xi$) print \"(USE the vial..)"
 if a1 a1=1
 if a2 a2=1
 if a3 a3=1
 a=1:goto pool.2
;
pool
 a=0:pe=25:print \"You kneel and drink your fill.."
pool.2
 i$="":a$=" kneels and drinks.."
 if a1 then if a1<12 a1=12:print d1$;a$:if a a1=20:i$=d1$
 if a2 then if a2<12 a2=12:print d2$;a$:if a a2=20:i$=d2$
 if a3 then if a3<12 a3=12:print d3$;a$:if a a3=20:i$=d3$
 if i$<>"" print \"'SHAZAM!!' shouts "i$".."
 goto advent
;
potion
 if instr("OF SKILL",gs$) print \"You feel more skillfull with the "wr$:print "(+4 skill until READY is executed again)":if zu<7 zu=zu+4
 if instr("VORPAL",gs$) print \"You feel more deadly with the "wr$:print "(+4 damage until READY is executed again)":if zv<7 zv=zv+4
 if instr("CHARM",gs$) gosub charm
 gosub clr.food:goto advent

charm
 if mw then if instr(":",wy$) print \"Mechanical beings don't charm!":return
 if mw then if instr(".",wy$) print \m$" is unaffected by the charm potion!" :return
 if mw print \m$" suddenly takes a shine to you!":zq=2
 if not mw print \"Charm what? There is no monster here!"
 return
;
serum
 print \"Yuk, it tastes awful!":gosub cure.p
 gosub clr.food:goto advent
cure.p
 if mid$(zu$,3,1)="1" print "Poison - gone!":i$="zu$":zw=3:zw$="0":zt=2 :gosub lnk.misc
 return
;
pill
 print \"Yech, gross!":gosub cure.d
 gosub clr.food:goto advent
cure.d
 if mid$(zu$,4,1)="1" print "Disease - gone!":i$="zu$":zw=4:zw$="0":zt=2 :gosub lnk.misc
 return
old
 print \"GROSS! Now you are diseased!!"
 i$="zu$":zw=4:zw$="1":zt=2:gosub lnk.misc
 gosub clr.food:goto advent
moonshin
 print \"BAD STUFF! Now you are poisoned!"
 i$="zu$":zw=3:zw$="1":zt=2:gosub lnk.misc
 gosub clr.food:goto advent

clr.item
 xi=xi-1:if xi=0 then xi$="":return
 l=len(xi$)
 if y=1 then xi$=mid$(xi$,5):return
 if (y+4)>l then xi$=left$(xi$,y-1):return
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
 return
 
clr.food
 xf=xf-1:if xf=0 then xf$="":return
 l=len(xf$)
 if y=1 then xf$=mid$(xf$,5):return
 if (y+4)>l then xf$=left$(xf$,y-1):return
 xf$=left$(xf$,y-1)+mid$(xf$,y+4)
 return
;
show3
 on nocar goto dropped
 gosub invent:setint("")
 goto lnkmain1
;
invent
 zt$="invent":setint(1)
 g1=gh:g2=gl:gosub prt.gold
 print \"Gold - In Hand:"gd$
 if key(1) return
 print \"Items Carried:"
 gosub pr.items:if zt$="abort" return
 print \"Rations:"
 gosub pr.food:if zt$="abort" return
 print \"Weapons:"
 gosub pr.weapons:if zt$="abort" return
 print \"Spells Known:"
 gosub prspell:if zt$="abort" return
 
stat.rtn
 on nocar goto drop.1
 setint(1):print \"Allies:"\
 xu$="NONE"
 if a1+a2+a3=0 print "No Allies.":goto sniff
 print "1) POINT MAN  : ";:if a1 print d1$", hp = "a1:else print xu$
 print "2) FLANK GUARD: ";:if a2 print d2$", hp = "a2:else print xu$
 print "3) REAR GUARD : ";:if a3 print d3$", hp = "a3:else print xu$
 if key(1) return
sniff
 if a1+a2+a3=0 print \"All alone... sniff.."
 if a1+a2+a3>0 print \"Items carried by allies:":gosub al.items
 if yt$<>"*" gosub pr.guild
 setint(""):print \"Press [RETURN] ";
get.key
 a=key(0):if a=0 goto get.key
 print chr$(8,16);chr$(32,16);chr$(8,16)
 return
pr.guild
 zw$=yt$:print \"FOLLOWING GUILD MEMBERS:"\
pr.gld.a
 if len(zw$)<3 return
 i$=mid$(zw$,2,1)
 zw$=mid$(zw$,3):zm=instr("=",zw$):if not zm return
 if instr(i$,"CDE") print "UNCONCIOUS- ";
 i$=left$(zw$,zm-1):print i$
 zw$=mid$(zw$,zm+4):goto pr.gld.a
;
prspell
 if xs=0 print \"No Spells.":return
 dy$=dw$+"spells"
 open #1,dy$
 print:for x=1 to xs
 zw=sc:zz$=xs$:gosub pr.sub
 position #1,40,a
 input #1,cb$\q$,q2$,q3,q4
 setint(1)
 print right$("   "+str$(x),3)". - ";
 print q$;chr$(32,21-len(q$))" : "q3"0%"
 if key(1) x=xs:zt$="abort"
 next:close:return

pr.items
 if (xi=0) or (xi$="") print \"No Items.":xi=0:xi$="":return
 dy$=dw$+"items"
 open #1,dy$
 print:for x=1 to xi
 zw=ic:zz$=xi$:gosub pr.sub
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm n$=left$(n$,zm-1)
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xi:zt$="abort"
 next:close:return

al.items
 if (ai=0) or (ai$="") print \"No Items.":ai=0:ai$="":return
 dy$=dw$+"items"
 open #1,dy$
 print:for x=1 to ai
 zw=ic:zz$=ai$:gosub pr.sub
 position #1,30,a,2
 input #1,n$:z=instr("|",n$):if z>0 n$=left$(n$,z-1)
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=ai
 next:close:return

pr.food
 if (xf=0) or (xf$="") print \"No Rations.":xf=0:xf$="":return
 dy$=dw$+"stores"
 open #1,dy$
 print:for x=1 to xf
 zw=cg:zz$=xf$:gosub pr.sub
 position #1,26,a,2
 input #1,n$
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xf:zt$="abort"
 next:close:return

pr.weapons
 zt=0:xu$=""
 if (xw=0) or (xw$="") print \"No Weapons.":xw=0:xw$="":return
 dy$=dx$+"weapons"
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
 if (a>zw) or (a<1) i$="Bad storage string! "+zz$:print \\\\i$:gosub write.lg :goto quit
 return
;
prt.gold
 if g1<0 g1=0
 if g2<0 g2=0
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return

add.gold
 gl=gl+g2:if gl=>10000 then gl=gl-10000:gh=gh+1
 return
 
tot.gold
 g1=gh+bh:g2=gl+bl:if g2=>10000 then g2=g2-10000:g1=g1+1
 return
;
quit
 on nocar goto dropped
 i$="":print \"Experience Points: "ep
 zz$=rnd$:a=random(ep):a=a/3:if a>0 print \"SPUR awards you "a" gold"\"for your experience.":g2=a:gosub add.gold
 if a1 print \"'I WILL WATCH FOR YOUR RETURN!' shouts "d1$
 if a2 then if a1 print "'YEAH? AND WHO WILL WATCH YOU?' snickers "d2$
 if a3 print \d3$" looks sad as you leave.."
 dy$=ds$+"spur.logon"
 link dy$,"quit1"
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
lnk.ship
 setint(""):dy$=ds$+"spur.ship":link dy$,"main1"

drop.1
 pop
dropped
 i$="SPUR.SUB":dy$=ds$+"spur.logon":link dy$,"quit3"
;
smart
 print "(You feel a bit smarter)":return
;
rnd.10a
 zz$=rnd$:a=random(999):a=(a/100)+1:return
rnd.100a
 zz$=rnd$:a=random(999):a=(a/10)+1:return
;
lnk.misc
; (supply i$=name of routine in spur.misc)
 dy$=dz$+"spur.misc":link dy$,"misc"
;
misc
 on nocar goto dropped
 if i$="return" return
 goto advent
;
hun.slv
 x=0:zr=0:if a1+a2+a3<1 return
 if a2<11 then if a2>0 zr=2:zt$=d2$:zs=a2
 if a3<11 then if a3>0 zr=3:zt$=d3$:zs=a3
 if a1<11 then if a1>0 zr=1:zt$=d1$:zs=a1
 if zr=0 return
 print \zt$" SURE LOOKS "xu$"!"
 print "Give it to "zt$;:input @2"? [Y]/n :"i$
 if i$="N" goto hun.slv2
 a=2:if xf=1 a=5
 if vk<2000 vk=vk+a
 print \"'THANK YOU!' says "zt$
 if zr=1 a1=a1+4
 if zr=2 a2=a2+4
 if zr=3 a3=a3+4
 return
;
hun.slv2
 zp=xf:i$="044,045,065,066,068," ; red serum, blue pill, potion of skill, vorpal potion, charm potion
 for a=1 to 16 step 4:zz$=mid$(i$,a,4)
 if instr(zz$,xf$) zp=zp-1
 next:if zp>3 goto h1
; not low on food
 if xu$="THIRSTY" if pe>14 if hp>18 goto h1
 if xu$="HUNGRY"  if ps>14 if hp>18 goto h1
 print \zt$" UNDERSTANDS..":zr=0:return
h1
 a=2:if zp>3 if hp>18 a=5
 if pc=9 a=a+1
 if vk>a vk=vk-a
 if instr("!",zt$) zr=0:print \zt$" IS SILENT.":return
 print \zt$" LOOKS ANNOYED."
 gosub rnd.100a:if vk<1000 a=a-((1000-vk)/33)
 if a/5<zs zr=0:return
 if zr=1 d1$="*":a1=0:x=h1:h1=0
 if zr=2 d2$="*":a2=0:x=h2:h2=0
 if zr=3:d3$="*":a3=0:x=h3:h3=0
 gosub rnd.100a:if a>50 goto hun.slv3
 zw$="- [ REVOLT ]":zx$="ATTACKED":print \\\"'THEN YOU DIE, CHEAP SKATE!!' SHRIEKS "zt$"!!"\:ms=15+(xp*3):ma=4:mw=1:md=0:wy$="":wx$="":zq=0:vz=1
 if instr("!",d1$) print d1$" RUSHES TO YOUR SIDE.":goto a1
 if a1>0 gosub rnd.10a:if a+4>a1 gosub fre.ally:print "'I AM WITH YOU "zt$"' SHOUTS "d1$"!":zt$=zt$+" and "+d1$:d1$="*":a1=0:x=h1:h1=0:ms=ms*2:wy$="|]"
a1
 if a1>0 print d1$" REMAINS LOYAL!"
 if instr("!",d2$) print d2$" SHOUTS AT "zt$"!":goto a2
 if a2>0 gosub rnd.10a:if a+4>a2 gosub fre.ally:print "'I JOIN YOU "zt$"' SHOUTS "d2$"!" :zt$=zt$+" and "+d2$:d2$="*":a2=0:x=h2:h2=0:ms=ms*2:wy$="|]"
a2
 if a2>0 print d2$" REMAINS LOYAL!"
 if instr("!",d3$) print d3$" PREPARES FOR BATTLE!":goto a3
 if a3>0 gosub rnd.10a:if a+4>a3 gosub fre.ally:print "'ATTACK "n1$"!' SHOUTS "d3$"!" :zt$=zt$+" and "+d3$:d3$="*":a3=0:x=h3:h3=0:ms=ms*2:wy$="|]"
a3
 if a3>0 print d3$" REMAINS LOYAL!"
 wy$=wy$+"X":gosub rnd.10a:if a<4 wy$=wy$+";"
 if a=5 wy$=wy$+"+~"
 m$=zt$:if left$(m$,4)="THE " m$=mid$(m$,5)
 goto hun.slv4
hun.slv3
 zw$="- HUNGER":zx$="LEFT"
 print "'WELL THAN, GOODBYE!!'"
 i$=zt$+" SWIMS AWAY!":if cl=6 i$=zt$+" FIRES RETROS AND LEAVES!"
 if instr("@@",lo$) print \i$
hun.slv4
 if (a1+a2+a3)<1 then ai=0:ai$=""
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, date$" "time$" "zw$
 print #1, zt$" "zx$" "n1$
 print #1, "IN "ww$", OVER FOOD DISPUTE."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
fre.ally
 zr=0:if x=0 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
show.file
 setint(1):copy f$:setint(""):return
;
delay.a
 for a=1 to 4000:next:return
;
write.lg
 close:open #1,"a:add.log"
 append #1:print #1,"[Spur.sub] "i$:close:return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):ready dr$:return
;
compile
 if un=1 print "Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return
;

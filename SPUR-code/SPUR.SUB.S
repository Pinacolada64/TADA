
; spur.sub.s
;.. Edited with Appleworks

 on nocar goto dropped

 public show3
 public quit
 public misc
 public compile

 if flag(32) print "spur.sub -";:gosub comp.ck
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
 if x=68 i$="zu$":zw=6:zw$="1":zt=2:gosub lnk.misc:goto wear3
 open #1,dy$:position #1,30,x,2
 input #1,n$\it:close
 gosub spec.itm
 if left$(n$,1) <> "A" print \"This is not an Armor!":goto advent
 if x>60 goto power.ar
 a=0
 if pc=1 if it>2 a=1
 if pc=2 if it>3 a=1
 if (pr=3) or (pr=5) or (pr=6) if it>5 a=1
 if (pc=8) or (pr=4) if it>6 a=1
 if a print \"THE "mid$(n$,3)" IS TOO BULKY FOR YOUR KIND" :goto advent
power.ar
 f$=dx$+"misc.data":open #2,f$
 position #2,250,pn,209:input #2,a
 if ((ar=0) or (a=0)) goto no.ar
 if a>60 if ar>40 input @2\"Power armor will lose it's charge when repacked, ok? y/[N] :"i$:if i$<>"Y" close:goto advent
 open #1,dy$:position #1,30,a,2
 input #1,i$\xx:close #1
;..store armor condition
;..don't store armor condition from ship
 if a>60 goto store.pw
 f$=right$("X"+str$(a),2)
 xx=instr(f$,"X2X31024284657")
 if xx=0 close:i$="xx=0 in wear armor":print \i$:gosub write.lg:goto advent
 position #2,250,pn,233:input #2,a$
 if len(a$)<>14 a$="00000000000000"
 if flag(32) print "a$="a$
 f$=str$(ar):if ar>99 f$="99"
 f$=right$("0"+f$,2)
 if xx=1 a$=f$+mid$(a$,3):goto store.ar
 if xx=13 a$=left$(a$,12)+f$:goto store.ar
 a$=left$(a$,xx-1)+f$+mid$(a$,xx+2)
store.ar
 if flag(32) print "a$="a$
 position #2,250,pn,233:print #2,a$
store.pw
 a$=right$("000"+str$(a),3)+","
 if flag(32) print "a$="a$
 xi=xi+1:xi$=xi$+a$
 print \"YOU REPACK THE "mid$(i$,3)".."
no.ar
 position #2,250,pn,209:print #2,x
 if x=113 print \hl$"BATTLE ARMOR POWERS UP"of$
 if x=115 gosub pwr.ar
 if x>60 it=2:print "USE ARMOR POWER PAK TO FULLY ENERGIZE"
 ar=it*10
 if x<60 gosub get.ar
wear3
 close
 ep=ep+1:if pi<8 then pi=pi+1:gosub smart
 print \mid$(n$,3)" WORN.";
 if x<>68 print " (New armor rating: "ar")";
 print \
 gosub clr.item:goto advent
;
get.ar
 position #2,250,pn,233:input #2,a$
 if len(a$)<>14 return
 if flag(32) print "a$="a$
 f$=right$("X"+str$(x),2)
 xx=instr(f$,"X2X31024284657")
 if xx=0 return
 ar=val(mid$(a$,xx,2))
 if ar<1 ar=it*10
 return
;
pwr.ar
 print \hl$"POWER ARMOR ENERGIZED!"of$
 print "(Protects from nuclear back-blast)"
 if not instr("pwr.ar",ys$) if len(ys$)<240 ys$=ys$+"*pwr.ar*"
 return
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
 y=(x*4)-3:x=val(mid$(xf$,y)):b1=x
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
 if cl=5 if cr=105 goto fountain
 if fd$="POOL OF WATER" goto pool
 gosub pr.food:if xf=0 goto advent
drink2
 input @2\"Drink which number Item? "a$:if a$="" goto advent
 if instr(" ",a$) print \"There was a space in your entry.":goto drink2
 x=val(a$):if x<10 then if len(a$)>1 print \"Huh?":goto drink2
 if (x<1) or (x>xf) print \"You don't have that item.":goto drink2
 y=(x*4)-3:x=val(mid$(xf$,y)):b1=x
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
 if (instr("076",xi$)) and (mid$(zu$,8,1)="0") then a=3:gosub messages: i$="zu$":zw=8:zw$="1":zt=2:gosub lnk.misc
 if instr("142",xi$) print \"(USE the vial..)"
 if a1 a1=1
 if a2 a2=1
 if a3 a3=1
 a=1:goto pool.2
;
pool
 a=0:pe=25:print \"You kneel and drink your fill.."
pool.2
 lu$="":a$=" kneels and drinks.."
 if a1 lu$=d1$:gosub cln.ally:if a1<b-2 a1=b-2:print lu$;a$:if a a1=b+3
 if a2 lu$=d2$:gosub cln.ally:if a2<b-2 a2=b-2:print lu$;a$:if a a2=b+3
 if a3 lu$=d3$:gosub cln.ally:if a3<b-2 a3=b-2:print lu$;a$:if a a3=b+3
 if lu$<>"" if a print \"'SHAZAM!!' shouts "lu$".."
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
 if mid$(zu$,4,1)="1" print "Desease - gone!":i$="zu$":zw=4:zw$="0":zt=2 :gosub lnk.misc
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

 f$=dx$+"misc.data":open #2,f$
 position #2,250,pn,213:input #2,xx
 if sh=0 i$="  NO SHIELD":a=0
 if sh if xx=0 i$="  UNKNOWN SHIELD":a=3
 dy$=dw$+"items"
 open #1,dy$
 if sh if xx position #1,30,xx,2:input #1,i$\a
 a=a*10
 print \"READIED- "mid$(i$,3);
 x=0:i$=""
 if sh if a x=(sh*100)/a
 if x>125 if xx<60 i$="ENCHANTED"
 if x>100 if i$="" i$="EXCELLENT"
 if x>75 if i$="" i$="GOOD"
 if x>50 if i$="" i$="SERVICABLE"
 if x>25 if i$="" i$="POOR"
 if i$="" i$="TERRIBLE"
 if sh if a print ", IN "i$" CONDITION ("sh")";
 position #2,250,pn,209:input #2,xx
 if ar=0 i$="  NO ARMOR":a=0
 if ar if xx=0 i$="  UNKNOWN ARMOR":a=3
 if ar if xx position #1,30,xx,2:input #1,i$\a
 a=a*10
 print \"WORN- "mid$(i$,3);
 x=0:i$=""
 if ar if a x=(ar*100)/a
 if x>125 if xx<60 i$="ENCHANTED"
 if x>100 if i$="" i$="EXCELLENT"
 if x>75 if i$="" i$="GOOD"
 if x>50 if i$="" i$="SERVICABLE"
 if x>25 if i$="" i$="POOR"
 if i$="" i$="TERRIBLE"
 if ar if a print ", IN "i$" CONDITION ("ar")";
 close
 print \
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
 if a1 lu$=d1$:gosub ally.name
 print "Point guard: ";:if a1 print lu$" hp="a1:else print xu$
 if a2 lu$=d2$:gosub ally.name
 print "Flank guard: ";:if a2 print lu$" hp="a2:else print xu$
 if a3 lu$=d3$:gosub ally.name
 print "Rear  guard: ";:if a3 print lu$" hp="a3:else print xu$
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
ally.name
 a$=lu$:gosub cln.ally
 if instr("=",a$) if not instr("=",lu$) lu$=lu$+on$+" [MOUNT]"+of$
 if instr("@",a$) lu$=lu$+on$+" [SADDLE]"+of$
 if instr("!",a$) lu$=lu$+on$+" [DISCIPLINE]"+of$
 if instr("$",a$) lu$=lu$+on$+" [ARMOR]"+of$
 if instr("%",a$) lu$=lu$+on$+" [COMBAT]"+of$
 if instr("&",a$) lu$=lu$+on$+" [TRACKING]"+of$
 if instr("(",a$) lu$=lu$+on$+" (GOOD)"+of$
 if instr(")",a$) lu$=lu$+on$+" (EVIL)"+of$
 lu$=lu$+" Const="+str$(b)
 return
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
 zz$=rnd$:a=random(ep):a=a/3:if a>0 print \"SPUR awards you "a" gold for your experience.":g2=a:gosub add.gold
 if a1 lu$=d1$:gosub cln.ally:yx=91:f$=d1$:gosub al.quote
 if a2 lu$=d2$:gosub cln.ally:yx=95:f$=d2$:gosub al.quote
 if a3 lu$=d3$:gosub cln.ally:yx=99:f$=d3$:gosub al.quote
 dy$=ds$+"spur.logon"
 link dy$,"quit1"
;
al.quote
;.. $ is players handle, * is ally's name
 if instr(">",f$) yx=yx+2
 if instr("+",f$) yx=yx+1
 dy$=dw$+"monster.quote"
 open #1,dy$:position #1,170,yx:input #1,zz$:close
 yx=instr("$",zz$):dy$=zz$:xz=len(zz$)
 if yx>1 if yx<xz dy$=left$(zz$,yx-1):zz$=mid$(zz$,yx+1):dy$=dy$+n1$+zz$
 if yx=1 dy$=n1$+mid$(zz$,2)
 if yx=xz dy$=left$(zz$,yx-1)+n1$
 zz$=dy$
 yx=instr("*",zz$):dy$=zz$:xz=len(zz$)
 if yx>1 if yx<xz dy$=left$(zz$,yx-1):zz$=mid$(zz$,yx+1):dy$=dy$+lu$+zz$
 if yx=1 dy$=lu$+mid$(zz$,2)
 if yx=xz dy$=left$(zz$,yx-1)+lu$
 print \dy$:return
;
cln.ally
 b=15:xy$=""
 if instr(">",lu$) xy$="THE GOD ":if instr("+",lu$) xy$="THE GODDESS "
 lu$=xy$+lu$
 if instr("#",lu$) b=val(mid$(lu$,instr("#",lu$)+1,1)):b=b*3
 if instr("|",lu$) lu$=left$(lu$,instr("|",lu$)-1)
 if b<15 b=15
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
 if a2 lu$=d2$:gosub cln.ally:if a2<b-4 zt$=d2$:gosub ck.horse:if a zr=2:zs=a2
 if a3 lu$=d3$:gosub cln.ally:if a3<b-4 zt$=d3$:gosub ck.horse:if a zr=3:zs=a3
 if a1 lu$=d1$:gosub cln.ally:if a1<b-4 zt$=d1$:gosub ck.horse:if a zr=1:zs=a1
 if zr=0 return
 i$="him":if instr("+",zt$) i$="her"
 lu$=zt$:gosub cln.ally
;... store original name in xy$ (with special characters)
 xy$=zt$:zt$=lu$
 print \zt$" SURE LOOKS "xu$", give it to "i$;:input @2"? [Y]/n :"i$
 if i$="N" goto hun.slv2
 a=2:if xf=1 a=5
 if vk<2000 vk=vk+a
 print \"'THANK YOU!' says "zt$
 if zr=1 a1=a1+4
 if zr=2 a2=a2+4
 if zr=3 a3=a3+4
 return

ck.horse
 a=0:if (not instr("=",zt$)) or (instr("==[]",zt$)) a=1:return
;... Break i$ into 2 because of Appleworks quirk
 i$= "*4*14*16*20*23*24*25*39"
 i$=i$ + "*41*50*61*63*77*78*79*80*81*82*"
 a=instr("*"+str$(b1)+"*",i$)
 lu$=zt$:gosub cln.ally
 if a=0 print "("lu$" CAN NOT CONSUME THE "mid$(gs$,3)")"
 return
;
hun.slv2
; info: ignore any of these food items plus 4 more,
; then adjust honor accordingly?  i don't get it
 zp=xf:i$="044,045,065,066,068,"
 for a=1 to 16 step 4:zz$=mid$(i$,a,4)
 if instr(zz$,xf$) zp=zp-1
 next:if zp>3 goto h1
 if xu$="THIRSTY" if pe>14 if hp>18 goto h1
 if xu$="HUNGRY"  if ps>14 if hp>18 goto h1
 print \zt$" UNDERSTANDS..":zr=0:return
h1
 a=2:if zp>3 if hp>18 a=5
 if pc=9 a=a+1
 if vk>a vk=vk-a
 if instr("!",xy$) zr=0:print \zt$" IS SILENT.":return
 print \zt$" LOOKS ANNOYED."
 gosub rnd.100a:if vk<1000 a=a-((1000-vk)/33)
 if a/5<zs zr=0:return
 if zr=1 d1$="*":a1=0:x=h1:h1=0
 if zr=2 d2$="*":a2=0:x=h2:h2=0
 if zr=3:d3$="*":a3=0:x=h3:h3=0
 gosub rnd.100a:if (a>50) or (instr(">",xy$)) goto hun.slv3
 zw$="- [ REVOLT ]":zx$="ATTACKED":print \\\"'THEN YOU DIE, CHEAP SKATE!!' SHRIEKS "zt$"!!"\:ms=15+(xp*3):ma=4:mw=1:md=0:wy$="":wx$="":zq=0:vz= 1
 lu$=d1$:gosub cln.ally
 if instr("!",d1$) print lu$" RUSHES TO YOUR SIDE.":goto a1
 if a1>0 gosub rnd.10a:if a+4>a1 gosub fre.ally:print "'I AM WITH YOU "zt$"' SHOUTS "lu$"!":zt$=zt$+" and "+lu$:d1$="*":a1=0:x=h1:h1=0:ms=ms*2:wy$="|]"
a1
 if a1>0 print lu$" REMAINS LOYAL!"
 lu$=d2$:gosub cln.ally
 if instr("!",d2$) print lu$" SHOUTS AT "zt$"!":goto a2
 if a2>0 gosub rnd.10a:if a+4>a2 gosub fre.ally:print "'I JOIN YOU "zt$"' SHOUTS "lu$"!" :zt$=zt$+" and "+lu$:d2$="*":a2=0:x=h2:h2=0:ms=ms*2:wy$="|]"
a2
 if a2>0 print lu$" REMAINS LOYAL!"
 lu$=d3$:gosub cln.ally
 if instr("!",d3$) print lu$" PREPARES FOR BATTLE!":goto a3
 if a3>0 gosub rnd.10a:if a+4>a3 gosub fre.ally:print "'ATTACK "n1$"!' SHOUTS "lu$"!" :zt$=zt$+" and "+lu$:d3$="*":a3=0:x=h3:h3=0:ms=ms*2:wy$="|]"
a3
 if a3>0 print lu$" REMAINS LOYAL!"
 wy$=wy$+"X":gosub rnd.10a:if a<4 wy$=wy$+";"
 if a=5 wy$=wy$+"+~"
 m$=zt$:if left$(m$,4)="THE " m$=mid$(m$,5)
 goto hun.slv4
hun.slv3
 zw$="- HUNGER":zx$="LEFT"
 print '"WELL THEN, GOODBYE!!"'
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
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return
;

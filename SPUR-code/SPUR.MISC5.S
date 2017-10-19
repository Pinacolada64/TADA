;..spur.misc5.s
;..modified with appleworks
 on nocar goto dropped

 public show2
 public compile

 if flag(32) print "spur.misc5--";:gosub comp.ck
 if i$="V" goto verbose
 if i$="STATS" gosub status:setint(""):goto advent
 if i$="STAT2" gosub status:goto lnk.ship
 if i$="AUTODUEL" goto autoduel
 if i$="FOLLOW ME" goto come
 if i$="#" goto ranger
 if i$="FL" goto follow
 if i$="DWARF" gosub dwarf:goto l.return
 if i$="AMMO" goto ammo
 if i$="CHARM" goto charm
 i$="Bad value of i$ in Spur.misc5! i$="+i$
 print \i$:gosub add.lg:goto advent
;
dropped
 i$="SPUR.MISC5":dy$=ds$+"spur.logon":link dy$,"quit3"
;
advent
 dy$=dz$+"spur.main":link dy$
linkshop
 setint(""):dy$=dz$+"spur.shop":link dy$,"main1"
l.return
 dy$=dz$+"spur.main":link dy$,"return"
lnk.ship
 setint(""):dy$=ds$+"spur.ship":link dy$,"main1"
;
autoduel
;pass x=challenger id number
 vy=0:zm=0:vq=0
 zz=0:zv$="abortduel":yz=z:i$=str$(z):gosub mark
 zz$="'LONG LIVE "+zw$+"!'"
 if instr("AD*",ys$) goto auto.f
 if yz>1 then if vv=z goto auto.b
 if instr(i$,"479") then if (vv=z-1) goto auto.b
 if instr(i$,"368") then if (vv=z+1) goto auto.b
 if vv=0 then if yz=0 zz$="'Hail fellow civilian!'":goto auto.b
 if vv=0 then if yz<>1 zz$="'Civys.... BAH!!'":goto auto.b
 if (instr(i$,"2479")) or (instr(zx$,ww$)) then goto auto.e
auto.f
 zz$=xx$+" peers at you curiously..":goto auto.b
auto.e
 if instr("+",ww$)zz$="'Pity AUTODUEL doesn't work in '+' rooms..'":goto auto.b
 if vt>0 zz$="'We will meet later "+n1$+"!'":goto auto.b
;--duel
 zv$="autoduel":yx$="":hh=0:b=0:cw$="":sx=0:zt=0:zs=0:xy=0:xv =0
 xu=x:gosub auto.a
 z=0
 if zz>11 then zz$=xx$+" upon reflection, looks polite!":goto auto.b
 if zz<7 then if not instr(zx$,ww$) zz$="'Your too weak, come back when your grown!'":goto auto.b
 if instr(zx$,ww$) print \hl$"'How DARE you invade our turf?!?'"of$
 z=1:zz$="'I challenge you to a duel!!'"
auto.b
 print on$;zz$;of$:if zv$="autoduel" then if z=1 goto auto.c
 zv$="":goto advent
;
auto.a
 au=0:dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$:close:vz=yh
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,x
 input #1,zt$:close
 xx$=left$(n2$,1):yz=val(xx$)
 gosub mark:xx$=mid$(n2$,2)
 zz=hp+(xp*2)+((ps+pe+pd)/2):zz=zz*10
 yy=yh+(yn*2)+((cs+ce+cd)/2)
 zz=zz/yy:zz=zz-xy:return

auto.c
 if len(ys$)<220 ys$=ys$+"AD*"
 wr$="":xy=0:gosub set.lvl:gosub auto.c1
 if cl=1 then if tf$<>">:" a$=tf$:gosub auto.c1
 xy=xy-1:if xy<1 xy=0
 xv=xy:zu=xy:if xy print \"("xx$" supported by "xy" guild members)"
 dy$=ds$+"spur.duel2":link dy$,"auto.c"
auto.c1
 z=0
auto.c2
 z=z+1:if z>20 i$="SAFETY TRIP-misc5, auto.c2":goto add.lg
 i$=str$(cr)+"=":a=instr(i$,a$):if a>0 a$=mid$(a$,a)
 zz=instr("=",a$):if (a=0) or (zz=0) then return
 i$=mid$(a$,zz+1,1)
 if val(i$)<3 goto auto.c3
 if (val(i$)=yz) or (val(i$)=(yz+1)) xy=xy+1
auto.c3
 a$=mid$(a$,zz+1):goto auto.c2

mark
 zw$="CIVY":zx$="(*)(*%$"
 if (yz=1) or (yz=2) yz=1:zw$="OUTLAW"
 if (yz=6) or (yz=7) yz=6:zw$="MARK OF THE CLAW":zx$="\|/"
 if (yz=3) or (yz=4) yz=3:zw$="MARK OF THE SWORD":zx$="-}-"
 if (yz=8) or (yz=9) yz=8:zw$="THE IRON FIST":zx$="=[]"
 return
;
come
 if vv<3 print \"ONLY GUILD MEMBERS MAY USE THIS COMMAND.":goto advent
 if flag(3)+flag(6)+flag(13)=0 print \"YOU MUST BE VERIFIED BY YOUR GUILD LEADER FIRST..":goto advent
 i$=":"+str$(cr)+"=":yz=len(i$)
 if cl=1 then if not instr(i$,ta$) then if not instr(i$,tf$) print "NOBODY HERE!":goto advent
 zm=0:tg$=ta$:gosub come.g
 if cl=1 ta$=tg$:if tf$<>">:" tg$=tf$:gosub come.g:tf$=tg$
 if zm=0 print "NOBODY WANTS TO FOLLOW!"
 vz=0:goto advent
come.g
 zx$=str$(vv)
 if instr(zx$,"67") zx$="D67"
 if instr(zx$,"34") zx$="C34"
 if instr(zx$,"89") zx$="E89"
 gosub set.lvl:zw$=a$
 if not instr(i$,zw$) then if cl>1 print "NOBODY HERE!":zm=1:return
 dy$=dx$+"spur.status":open #1,dy$
come.a
 xy=instr(i$,zw$):if not xy goto come.c
 zy$=mid$(zw$,xy+yz,1):xv$=mid$(zw$,xy+1)
 zs=instr(":",xv$):xv$=left$(xv$,zs+4):zt=instr("=",xv$)
 zz$=mid$(xv$,zt+1):xu=instr(":",zz$):zz$=left$(zz$,xu-1)
 zs=instr(":",xv$):xu$=mid$(xv$,zs+1,3)
 dy$=mid$(zz$,2):if instr(zy$,zx$) gosub come.d:goto come.b
 if instr(zy$,"ABCDE") print dy$" BEING UNCONCIOUS, DOESN'T MOVE.":goto come.b
 print dy$" STARES AT YOU, AND DOESN'T MOVE."
come.b
 xy=xy+len(xv$):zw$=mid$(zw$,xy):if instr(i$,zw$) goto come.a
come.c
 close
 if cl=1 tg$=a$
 if cl=2 tb$=a$
 if cl=3 tc$=a$
 if cl=4 td$=a$
 if cl=5 te$=a$
 if cl=6 th$=a$
 return
come.d
 if len(yt$)>210 print "NO MORE CAN FOLLOW!":return
 if instr(zz$,yt$) print dy$" IS ALREADY FOLLOWING..":return
 print "TAKE "dy$"? [Y]/n :";:input @2 xz$:if xz$="N" return
 if instr(zy$,"CDE") goto come.e
 zr=val(xu$):position #1,32,zr:input #1,xx$
 if mid$(xx$,10,1)="0" print dy$" DOESN'T WANT TO FOLLOW.." :return
 print dy$" AGREES TO FOLLOW YOU..":goto come.f
come.e
 print dy$" IS UNCONCIOUS!"
 if (instr("*C",yt$)) or (instr("*D",yt$)) or (instr("*E",yt$)) print "YOU CAN ONLY CARRY ONE PERSON, "dy$" IS LEFT.":return
 xz$="HELPS YOU CARRY "+dy$:f$="IS TOO WEAK TO HELP"
 if yt$<>"*" xu=(instr("=",yt$)-1):print mid$(yt$,3,xu-2)" "xz$:goto come.f
 lu$=d1$:gosub cln.ally
 if a1>10 print lu$" "xz$:goto come.f
 if a1>0 print lu$" "f$
 lu$=d2$:gosub cln.ally
 if a2>10 print lu$" "xz$:goto come.f
 if a2>0 print lu$" "f$
 lu$=d3$:gosub cln.ally
 if a3>10 print lu$" "xz$:goto come.f
 if a3>0 print lu$" "f$
 print "YOU CAN'T CARRY "dy$" BY YOURSELF" :return
come.f
 yt$=yt$+zz$+"="+xu$+"*":zt$=i$+zz$+":"+xu$:xu=instr(zt$,a$)
 vz=len(zt$):zz$=left$(a$,xu-1):zt$=mid$(a$,xu+vz)
 a$=zz$+zt$:zm=1:return
;
show2
 on nocar goto dropped
 gosub status:setint("")
 goto linkshop
;
status
 setint(1)
 print \n1$"'s Current Stats: (BHR="hp+(xp*2)+((pe+pd+ps)/2)+((sh+ar)/4)")"\
 g1=gh:g2=gl:gosub prt.gold
 print "Gold - In Hand:"gd$
 g1=bh:g2=bl:gosub prt.gold
 print "       In Bank:"gd$
 print \"Experience Pts :"right$("   "+str$(ep),5)"   Hit Points :"right$(" "+str$(hp),3)
 print "Monsters Kills :"right$("   "+str$(mk),5)" Player Level :"right$(" "+str$(xp),3)
 a=ps*4:print \"Strength: "right$("  "+str$(ps),2)right$("    "+str$(a),4)"%   ";
 a=pt*4:print "Const'n  :"right$("  "+str$(pt),2)right$("    "+str$(a),4)"%"
 a=pi*4:print "Intel   : "right$("  "+str$(pi),2)right$("    "+str$(a),4)"%   ";
 a=pd*4:print "Dexterity:"right$("  "+str$(pd),2)right$("    "+str$(a),4)"%"
 a=pw*4:print "Wisdom  : "right$("  "+str$(pw),2)right$("    "+str$(a),4)"%   ";
 a=pe*4:print "Energy   :"right$("  "+str$(pe),2)right$("    "+str$(a),4)"%"
 print \"Shield  :    "right$("  "+str$(sh),3)"%   ";
 print "Armor    :   "right$("  "+str$(ar),3)"%"
 if instr(left$(zu$,1),"BC") i$="YES":else i$="NO"
 a=1+xp:if pc=4 a=a*2
 print "Shield skill: "a", Formal training- "i$
 i$="Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  AssassinKnight  "
 print \"Class : "mid$(i$,pc*8-7,8);
 i$="Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc     Half-Elf"
 print " Race: ";mid$(i$,pr*8-7,8)
 i$="Neutral":if (pr=2) or (pr=8) i$="Bad"
 if (pr=3) or (pr=4) i$="Good"
 print "Natural Alignment: '"i$"'.";
 i$="Evil":if vk>399 i$="Bad":if vk>799 i$="Neutral"
 if vk>1200 i$="Good":if vk>1600 i$="Saintly"
 print " Current alignment: "i$" ("vk" Honor points)"
 if vv<3 goto no.guild
 print \"GUILD FOLLOWER? ";
 if mid$(zu$,10,1)="1" print "YES":else print "NO"
no.guild
 yx=12+xp
 if pc=1 yx=yx-2
 if pc=5 yx=yx+5
 if (pc=6) or (pc=8) yx=yx+2
 if (b5=3) or (b5=9) yx=yx+2
 if instr("&",d1$+d2$+d3$) yx=yx+5
 print "Effective Tracking ability: "yx
 if mid$(zu$,3,1)="1" print \"POISONED!":else print \"Not poisoned"
 if mid$(zu$,4,1)="1" print "DISEASED!":else print "Not diseased"
 if mid$(zu$,2,1)="1" print "Ring worn.."
 if mid$(zu$,6,1)="1" print "Gauntlets worn.."
 i$=mid$(zu$,8,1):zs=instr("076,",xi$):zr=instr("076,",ai$)
 if i$="1" print "Amulet of life -  ENERGIZED!"
 if i$="0" if zs+zr>0 print "[][] AMULET OF LIFE NOT ENERGIZED! [][]":if zr>0 print "(Your ally carries it!)"
 if instr(mid$(zu$,7,1),"23") print "Wizard's Glow spell active!"
 print \"King of the Wraiths : ";
 if instr(mid$(zu$,7,1),"12") print "Dead..":else print "Alive.."
 print "SPUR : ";:if (sr) print "Alive!":else print "Dead..."
 g1=dh:g2=dl:gosub prt.gold
 print "Dwarf: ";:if (df) print "Alive!  ["gd$" gold]":else print "Dead..."
 print "Tut's Treasure: ";:if mid$(zu$,9,1)="2" print "Looted..":else print "Somewhere.."
 ex=clock(1)-ew:ex=ev-ex:if ex<0 ex=0
 print \"Hourglass: "(ex/60)" mins."
 return
;
prt.gold
 if g1<0 g1=0
 if g2<0 g2=0
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
;
ranger
 if xp>2 print \"Ranger: map":f$=dx$+"map."+str$(cl):gosub show.file
 if xp<3 print \"(Map available when you reach level 3)"
 print \"Ranger: Room # "cr:if cl>1 print "(Dwarf: level 1 only)":goto advent
 if df=0 print "Dwarf dead..":goto advent
 i$=rnd$:z=random(99)/10
 z=df+(z-5):if z<0 z=6
 print "Aproximate Dwarf location :"z:goto advent
;
follow
 if vv<3 print \"For guild members only":goto advent
 zt=3:zw=10:zw$="0"
 input @2\"Do you wish to FOLLOW fellow guild members? y/[N]:"i$
 print "FOLLOW - ";:if i$="Y" zw$="1" print "ON":else print "OFF"
 gosub zu$:goto advent
;
verbose
 zw=1:i$=left$(zu$,1):zw$="A"
 if i$="C" zw$="B"
 if i$="B" zw$="C"
 if i$="A" zw$="0"
 if instr(zw$,"AB") zz$="OFF":else zz$="ON"
 gosub zu$:print \"Room description: "zz$
 if zz$="OFF" print \on$"Note that important information is sometimes contained in Room descriptions!"of$
 goto advent
;
zu$
;... input zw=position number, zw$=new value
 zu$="-"+zu$+"-"
 zx$=left$(zu$,zw):zy$=mid$(zu$,zw+2)
 zu$=zx$+zw$+zy$:zu$=mid$(zu$,2,10)
 return
;
dwarf
 if instr("@@",lo$) print \"(The dwarf can't get you here!)":return
 if ((gh>0) or(gl>0)) print \'
A Dwarf runs in, grabs your bag of gold and disappears!'\:g1=dh:g2=dl:gosub add.gold:gh=gh+g1:dh=gh:dl=gl:gh=0:gl=0:return
 if xi=0 return
 l=len(xi$)
 a$=right$("000"+str$(og),3)+",":y=instr(a$,xi$):if y goto dwrf.get
 zz$=rnd$:b=random(xi):if b=0 then b=1
 y=(b*4)-3
dwrf.get
 xi=xi-1:if xi=0 then xi$="":goto dwrf.msg
 if y=1 then xi$=mid$(xi$,5):goto dwrf.msg
 if (y+4)>l then xi$=left$(xi$,y-1):goto dwrf.msg
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
dwrf.msg
 print \'
The dwarf, seeing you are not  carrying any gold, steals an item from you!'
 return
;
ammo
 print \"Olly greets you, 'Welcome, "n1$"!! Choose from this"\"fine list of ammunition and stuff.'"
 dy$=dw$+"items":open #1,dy$
ammo3
 x=98
 print  "[]=-=-=-=-=-=-=-=[OLLY]=-=-=-=-=-=-=-=[]"
 print \"  # Name      Rnds Dmg Weapon    Cost"\
ammo1
 position #1,30,x:input #1,cb$:if cb$="*" goto ammo1a
 input #1,it$\it:it=it*10:setint(1)
 zm=instr("|",it$):if zm=0 goto ammo1a
 zw$=mid$(it$,zm+1,2):zx$=mid$(it$,zm+3,1):zy$=mid$(it$,zm+4)
 if x>111 zw$="":zx$=""
 if x=147 zy$="MUSKET"
 if x=148 zy$="357 MAG"
 if x=149 zy$="44 MAG"
 if x=150 zy$="CANNON"
 it$=left$(it$,zm-1):it$=mid$(it$,3):if left$(zy$,1)=" " zy$=mid$(zy$,2)
 a=11:if x>146 a=15
 it$=left$(it$+"          ",a)
 it$=right$("   "+str$(x),3)+":"+it$
 it$=it$+" "+zw$
 it$=it$+" "+zx$+" "+zy$
 it$=left$(it$+"                        ",35)
 print it$"-"right$("  "+str$(it),3)
ammo1a
 x=x+1:if (x>111) or (key(1)) goto ammo4
 goto ammo1
ammo4
 if x<147 x=146:print \"            [ AMMO CARRIERS ]"\
 if (x>150) or (key(1)) print \"            [ B)ooby traps ]":goto ammo2
 goto ammo1

ammo2
 setint("")
 if xi>zo-1 print \"You have no room in your pack!":close:goto linkshop
 input @2\"Your Choice (?=List): "i$:if i$="" or i$="Q" close:goto linkshop
 if i$="?" goto ammo3
 if i$="B" goto booby
 x=val(i$):zz=0
 if x<98 zz=999
 if x>111 then if x<147 zz=999
 if x>150 zz=999
 if zz=999 print \"Enter 98-111, 147-150, 'B' or 'Q'":goto ammo2
 zt=0:gosub ammo.z:goto ammo2

ammo.z
;zt=0 is ammo, zt=1 is booby trap
 position #1,30,x:input #1,cb$:if cb$="*" return
 input #1,it$\it:it=it*10:if zt=1 it=200
 g3=gh:g4=gl:g1=0:g2=it:gosub chk.gold
 if a=0 print \"You do not have enough gold.":return
 a$=mid$(it$,3)
 if zt=0 zm=instr("|",a$):if not zm print \"This is not ammo!!":return
 if zt=0 a$=left$(a$,zm-1)
 print \"You choose "a$" for "it" gold? ";:input @0 i$
 if i$<>"Y" return
 xa$=right$("000"+str$(x),3)+","
 print \"Done!":g2=it:gosub sub.gold
 gosub ammo5:return

ammo6
 if x>145 then if zt=0 print \"(Appropriate ammo will automatically be placed in the "a$ :print "when it is purchased. Buying more than 1 "a$" will do no good)"
 xi=xi+1:xi$=xi$+xa$:return

ammo5
 if zt=1 pop:goto ammo6
 if (x<103 or x>105) then if x<>109 pop:goto ammo6
 a=201:i$="cartridge box":zz$="147"
 if x=104 a=203:i$="bandoleer":zz$="148"
 if x=105 a=205:i$="bandoleer":zz$="149"
 if x=109 a=207:i$="caisson":zz$="150"
 if not instr(zz$,xi$) pop:goto ammo6
 f$=dx$+"misc.data":open #2,f$
 position #2,250,pn,a:input #2,zz
 if zz>8 print "The "i$" is full..":close #2:pop:goto ammo6
 zz=zz+1:position #2,250,pn,a:print #2,zz:close #2
 print "Placed in the "i$". ("zz" refills in it)."
 return

booby
 setint(1):print \'
You go to the Booby Trap display...

"Ahh, note this selection of the finest traps!" beams Olly.. "For you, only 200
gold a piece! Each with its secret disarm code! Bury one of these babies with
the DIG command and it will discourage people from digging up your gold!"' :setint("")
booby.a
 print \"Cost=200. Purchase Booby Trap."
 input @2 "Disarm code [A,B,C,D,E,F,G,H,I]:"i$
 if i$="" or i$="Q" print \"You leave the booby trap display":goto ammo2
 if len(i$)>1 i$="*"
 x=instr(i$,"ABCDEFGHI")
 if x=0 print \"Olly pretends not to notice you fumbling at the keyboard":goto booby.a
 x=x+151:zt=1:gosub ammo.z:goto booby.a
;
sub.gold
 if g2>gl then gl=gl+10000:gh=gh-1
 gl=gl-g2:return
;
chk.gold
 a=0
 if g3>g1 then a=1:return
 if (g3=g1) and (g4=>g2) then a=1:return
 return
;
add.gold
 gl=gl+g2:if gl=>10000 then gl=gl-10000:gh=gh+1
 return
;
charm
 if instr("HORSE",m$) print \"The horse munches grass..":goto l.return
 gosub rnd.10z
 if instr("E",wy$) if vk<800  z=z-1:print "(Evil charm?)":if vk<400 z=z-2
 if instr("G",wy$) if vk>1200 z=z-1:print "(Good charm?)":if vk>1600 z=z-2
 if z<1 z=0
 if zq>1 z=0
 if z>2 goto charm.a
 if a1>0 if a2>0 if a3>0 goto charm.a
 i$="*"+d1$+"*"+d2$+"*"+d3$+"*":zt$="*"+m$+"*"
 if instr(zt$,i$) goto charm.a
 i$="S ":if right$(m$,1)="S" i$=" "
 print \on$;m$" WANT"i$"TO JOIN YOU!"of$;:input @2" OK? [Y]/n :"i$
 z=2:if instr("E",wy$) if vk<800 z=4
 if instr("G",wy$) if vk>1200 z=4
 if z>vk z=vk
 if i$="N" vk=vk-z:zq=0:goto charm.a
 if ms>15 ms=15
 i$=m$+"|#"+str$(ms/3):if instr("F",wy$) i$=i$+"+"
 if a1=0 d1$=i$:a1=ms+5:h1=0:goto charm.b
 if a2=0 d2$=i$:a2=ms+5:h2=0:goto charm.b
 if a3=0 d3$=i$:a3=ms+5:h3=0:goto charm.b
charm.a
 i$="ES ":if right$(m$,1)="S" i$=" "
 print \m$" SADLY WATCH"i$"YOU LEAVE..":goto charm.c
charm.b
;.. (honor given upon return to spur.main- keys on zq)
 xx$=" beams with pride,"
 if instr("F",wy$) xx$=" smiles at you sweetly,"
 print \m$;xx$" and joins your party.
 xx$="CHARM":zt$=m$+" JOINED"
 gosub news
charm.c
 goto l.return
;
news
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$" "xx$
 print #1, zt$" THE "n1$
 print #1, "PARTY IN "ww$".."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 return
;
show.file
 if flag(32) print "f$="f$
 setint(1)
 open #1,f$:if mark(1) close #1:print\"(This map not ready yet!)":return
 close #1:copy f$:setint(""):return
;
rnd.10z
 zz$=rnd$:z=random(999):z=(z/100)+1:return
;
set.lvl
 if cl=1 a$=tg$
 if cl=2 a$=tb$
 if cl=3 a$=tc$
 if cl=4 a$=td$
 if cl=5 a$=te$
 if cl=6 a$=th$
 return
;
cln.ally
 if instr("|",lu$) lu$=left$(lu$,instr("|",lu$)-1)
 return
;
add.lg
;.. i$=log message
 open #2,"a:add.log":append #2
 print #2,"Spur.misc5[] "i$" @"time$:close #2:return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
comp.ck
 print ".. ok":return
;

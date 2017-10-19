
;  Spur.duel.s - WITH AUTODUEL
 
 public duel
 public return
 public auto.c
 public compile

;... yz, xz$, zu must be preserved for spur.duel2, don't use

 on nocar goto dropped
 if un=1 print "spur.duel--";:gosub comp.ck
 yx$="":zv$="":hh=0:wr$="":xu$="":cw$="":sx=0
 zt=0:zs=0:xy=0:xv=0:vy=0:zm=0:vq=0:zq=0:xu=0:zn=0:zp=0
 if (sl=cl) and (sr=cr) goto chalspur
 goto challenge
 
duel
 on nocar goto dropped
 yx$="":if zv$="autoduel" zv$="autoduel.2"
 print \"[hp="hp" Shields: You-"sh", "xx$"-"ye"]"
 if zy$="DOWN" goto down

 input @2 \"(A],P,B,F,R,V,H,?):"i$
 if instr(" ",i$) print \"There was a space in your command":goto duel
 if i$="H" a=16:gosub messages:goto duel
 if i$="?" print \"A]ttack, Parry, Bash, Flee, Ready, Verbose ON/OFF, Help":goto duel
 if i$="R" gosub rdy.wp:goto duel
 if i$="F" goto flee
 if wr$="" goto no.wep
 if i$="P" zy$="PARRY WITH THE "+xu$+"!":zw=3:xu=xu+1:zn=0:zp=0:goto tactic
 if (i$="B") and (sh<6) print \"Not enough shield!":goto duel
 if i$="B" zy$="Shield BASH!":zw=4:zp=zp+1:xu=0:zn=0:goto tactic
 if i$="V" goto verbose
 if i$="#" then if un=1 then hp=30
 zy$="aTTacK!":zw=2:zn=zn+1:xu=0:zp=0:goto tactic

down
 input @2 \"(S],R,V,H,?):"i$
 if instr(" ",i$) print \"There was a space in your command":goto duel
 if i$="R" then zy$="Roll on the ground..":zw=5:goto tactic
 if i$="V" goto verbose
 if i$="H" a=16:gosub messages:goto duel
 if i$="?" print \"S]tand up, Roll on ground, Verbose ON/OFF, Help":goto duel
 zy$="TRY TO STAND UP..":zw=1:goto tactic

verbose
 i$="ON":zq=1-zq:if zq=0 i$="OFF"
 print \"Duel commentary - "i$:goto duel
;
no.wep
 if pi>2 pi=pi-2
 if pi<9 print\"You wisely decide you are too dumb to duel and FLEE":goto flee2
 print \"NO WEAPON READIED! (You feel dumber)":goto duel
; 
challenge
 i$="DUEL":goto lnkduel2
;
auto.c
 on nocar goto dropped
 xu=0:zn=0:zp=0
 if zv$="abortduel" zv$="":print \xx$" says: 'I accept your challenge!'"
 if not hh then print \"I CHOOSE "cw$
; turf bonus
 zz=0:if instr(zw$,ww$) zz=1:xv=xv+1:if instr("HQ",ww$) zz=3:xy=xy+2
 if zz>0 print \"TURF BONUS = ["zz"]"
 print \"Damage adds: "xy", Accuracy adds: "xv
 zr=(yn*2)+xy+xv+cd+cs+ci:print \"Initiative: "zr
 if zv$<>"" print \'I choose "Sport" duel!'
 if mid$(zt$,2,1)="1" print \"(The !#%%@# seems a bit hard to see!)"
 i$=mid$(zt$,7,1):if not instr(i$,"23") goto gvl.chk
 ye=ye+20:if yg=1 print \"(The dork has Wizard glow in effect)"

gvl.chk
 input @0\"C)ontinue duel or G)rovel? "i$
 if i$="G"gosub rnd.100z:if z>50print\"'GROVELING WILL DO YOU NO GOOD!'":i$="C"
 if i$="G" print \xx$" snickers, and waves you on.":i$="GROVEL":goto lnkduel2
 if i$<>"C" goto gvl.chk
 i$=mid$(zu$,7,1):if instr(i$,"23") print \"(Your Wizard glow adds 20 to your shield)":sh=sh+20
 if (xx$<>"THE ENFORCER") or (cw$<>"SUN-SWORD") then vt=vt+1
 h=yh:if hh gosub follow:goto duel
 gosub rdy.wp
 vw=(xp*2)+zt+zs+pd+ps+pi:print \"Your initiative: "vw:vu=4
 if vw>zr if vw-zr>10 vu=5:print \"You have initiative"
 if zr>vw if zr-vw>10 vu=3:print \xx$" has the initiative!"
 if vu=4 print \"Neither has the initiative.."
 goto duel
;
rdy.wp
 if hh print \"Thou art a Cheat and a COWARD!":pop:hp=hp-1:goto attack1
 if ps<3 print \"Not enough strength to ready a weapon!":return
 if xw=0 print \"You have No Weapons!":xu$="NO WEAPONS":return
 print \"Choose a Weapon:"\
 dy$=dx$+"weapons"
 open #1,dy$
 for e=1 to xw
 y=(e*4)-3:a=val(mid$(xw$,y))
 position #1,34,a,2
 input #1,w$
 print e". "mid$(w$,4)
 next
rdy.wp1
 input \"Weapon number you choose ? "x
 if (x<1) or (x>xw) print \"You don't have that weapon!":goto rdy.wp1
 y=(x*4)-3:a=val(mid$(xw$,y))
 position #1,34,a,2
 input #1,wr$\ws,wd\wa:close
 if instr("DEATH AMULET",wr$) gosub amulet
 wr$=mid$(wr$,4):print \wr$" readied!":xu$=wr$
 n$=wr$:yo=pc:yq=pr:zw=wa:gosub special
 print \"Weapon adds: Damage = "zt", Accuracy = "zs
 gosub set.hh
 wd=wd*5/10:x=p1*7/10:wd=wd+x
 ws=(ws+p3)/2
 if (wa=8) or (wa=10) then if not instr("STORM",wr$) then if vn<1 then print \"No ammo readied! All weapon attributes reduced by half.":zt=zt/2:zs=zs/2 :wd=wd/2:ws=ws/2:xu$="UNLOADED "+xu$

;
;... Drop thru to the follow routine
;
follow
 zv=0
 if vv=3 or vv=4 then zv=zm
 if vv=6 or vv=7 then zv=vy
 if vv=8 or vv=9 then zv=vq
 i$=yt$:z=0
follow.b
 a=instr("=",i$):if a=0 goto follow.a
 zs$=mid$(i$,2,1)
 if not instr(zs$,"CDE") zv=zv+1
 z=z+1:i$=mid$(i$,a+4)
 if instr("=",i$) then if z<6 goto follow.b
follow.a
 if zv>5 zv=5 print "(Only 5 Guild members can lend support)"
 i$="!":if zv>1 i$="s!"
 if zv>0 print "You are supported by "zv" Guild member"i$
 zt=zt+zv:zs=zs+zv
 if zv print "Guild support adds: Damage & accuracy = "zv
 return
;
amulet
 print \\\\'
WARNING!!!

Readying the Death Amulet has a 30%
possibility of instant death!!'
 a=30:if instr("076",xi$) a=15:print \"The AMULET OF LIFE reduces this to 15%!"
 input @2\"Still want to?!? Y/N: " i$:if i$<>"Y" pop:goto rdy.wp
 print \\"DEADLY POWER STIRS. IT LIVES.."
 gosub rnd.100z:if z>a wd=50:print \"YOU LIVE!":goto amulet.2
 print \\"ARGH!! IT TURNS ON YOU!!"\"YOU ARE TORN TO PIECES. LITTLE ONES.."
 close:pop:hp=0:xn=sn:sn=0:z=9:i$="dead2"
 dy$=ds$+"spur.misc6":link dy$
amulet.2
 gosub opnt.itm
 if instr("076",i$) print \"(Oh oh.. "xx$" has the Amulet of Life!)":wd=15
 return
;
chalspur
 zv=0:zu=0
 x=pe+pi+ps+pw+pt+pd:zw$="OMNIPOTENT":xx$="SPUR":sx=1:wx$="random"
 if x>90 goto chalsp.2
 print \"'Thou art too weak to challenge the omnipotent Spur!'"
 print \"You are teleported elsewhere.."
 zv$="":wr$="":zq=0:dy$=dz$+"spur.main":ready dr$:link dy$,"flee2"

chalsp.2
 print \'
A shadowed figure looms out of the dark, Large Fireball sizzling in one hand.
"Doest thou dare challenge SPUR?" ';:input @0 i$
 if i$<>"Y" goto flee2
 cs=20:ct=20:ci=20:ce=20:cw=20:cd=20
 h=10*sl:h=h+random(10):if h>51 then h=51
 a=xl*3:if a<h then h=h-a
 ya=0:yb=5000:zz$=rnd$:ye=50:yf=50
 
 dy$=dx$+"weapons"
 open #1,dy$
 w4=0:for e=1 to wc
 position #1,34,e,2
 input #1,w$\w1,w2
 if w2>w4 then w3=w1:w4=w2:cw$=w$
 next:close:cw$=mid$(cw$,4)
 gosub set.hh
 w4=w4*5/10:x=p2*7/10:w4=w4+x
 w3=(w3+p4)/2
 gosub rdy.wp:goto duel
 
attack
 gosub get.numb:i$=" STRIKE CHANCE MOD: "
 if zz=1 a=a-2:if zq=1 print xx$" TRIES TO STAND:"i$"-2"
 if zw=1 a=a+2:if zq=1 print "You TRY to stand, your"i$"-2"
 if zz=2 a=a+1:if zq=1 print xx$" ATTACKS:"i$"+1"
 if zw=2 a=a-1:if zq=1 print "YOU ATTACK, YOUR"i$"+1"
 if zz=3 a=a-2:if zq=1 print xx$" PARRYS:"i$"-2"
 if zw=3 a=a+2:if zq=1 print "YOU PARRY, YOUR"i$"-2"
 if zz=4 a=a-1:if zq=1 print xx$" BASHES:"i$"-1"
 if zw=4 a=a+1:if zq=1 print "YOU BASH, YOUR"i$"-1"
 if zw=5 a=a+2:if zq=1 print "YOU ROLL, YOUR"i$"-2"
 if zz=5 a=a-2:if zq=1 print xx$" ROLLS:"i$"-2"
 if (yx=3) or (yx=4) a=0:if zq=1 print "YOU HAVE AUTO-STRIKE"
 if (yx=13) or (yx=14) a=9:if zq=1 print xx$" HAS AUTO-STRIKE"
 print \"[Strike result]:";
 for z=1 to 7:print ".";:for w1=1 to 50:next:next:print \\
 if a>vu goto attack1
 if (instr("STORM",xu$)) or (sh>40) goto staff.0
 a=0:if pc=1 gosub rnd.100z:if z>70 a=1:if instr("cast.a",wx$) a=0
 if a=1 print \"Energy FLASHES from your fingers!!":gosub rnd.100z:w1=(z/20)+3 :if instr("STAFF",xu$) print "Your staff amplifies it!":w1=w1+3
 if a=1 print "..THUNDER rocks the chamber..":wx$=wx$+"cast.a":goto wiz.a
staff.0
 zz$=rnd$:w1=random(wd*100):w1=w1/100+1
 a=0:if yg=6 a=15:if pc=6 a=0
 if yg=8 a=8:if pc=8 a=0
 if mid$(zt$,2,1)="1" a=20
 if a>0 gosub rnd.100z:if z<a print \"LOST SIGHT OF THE !$@*@&!!":goto duel
 zx$="996877889":zz$=mid$(zx$,yi,1):a=val(zz$):a=a*10
 zx$=mid$(zx$,pr,1):yy=val(zx$):yy=yy*10
 yy=yy-a:if yy>0 yy=yy/2:gosub rnd.100z:if z<(yy+1) print \"SWUNG OVER THE !#$%@$@ HEAD!":goto duel
 gosub get.numb
 print "YOU STRIKE WITH THE "xu$"!"\:i$=" HIT CHANCE MOD: "
 if yx=11 a=a+2:if zq=1 print "YOU ATTACK, "xx$" PARRIED."i$"-2"
 if yx=5 a=a+3:if zq=1 print "BOTH PARRIED."i$"-3"
 if yx=6 a=a-2:if zq=1 print "BOTH ATTACKED."i$"+2"
 if (yx=3) or (yx=4) a=a-3:if zq=1 print xx$" DOWN,"i$"+3!"
 if zw=5 a=a+3:if zq=1 print "YOU ROLLED,"i$"-3"
 gosub rnd.100z:if yg=5 then if z>90 print \xx$" DODGED YOUR BLOW!":goto duel
 if ws+zs>a then if z>15 print "[ HIT ]"\:else print "[ MISS ]"\:goto duel
 i$=". DAMAGE MOD: "
 w1=w1+zt:if pc=8 gosub rnd.100z:if z>90 print \"CRITICAL HIT!":w1=w1+2
 if xp>yn zz=(xp-yn)+1:zz=zz/2:w1=w1+zz:if zq=1 print "LEVEL"i$"+"zz
 if yx=3 w1=w1+3:if zq=1 print xx$" KNOCKED DOWN"i$"+3"
 if yx=4 w1=w1+2:if zq=1 print "YOU ATTACK, "xx$" STANDS UP"i$"+2"
 if yx=5 w1=w1/3:if zq=1 print "BOTH PARRY"i$"0.33%"
 if yx=6 w1=w1+2:if zq=1 print "BOTH ATTACK"i$"+2"
 if yx=11 w1=(w1*3)/4:if zq=1 print "YOU ATTACK, "xx$" PARRIED"i$"0.75%"
 if zz=5 w1=(w1*3)/4:if zq=1 print xx$" ROLLS"i$"0.75%"
 if zw=3 then if yx<>5 w1=(w1*2)/3:if zq=1 print "YOU PARRY"i$"0.50%"
 if zw=4 w1=w1-2:if zq=1 print "YOU BASH"i$"-2"
 if zw=5 w1=w1/2:if zq=1 print "YOU ROLL"i$"0.50%"
 if w1>5 w1=(w1*4)/5
 if yg=4 then if ye print "(PALADIN SKILL!) ";
 if ye print "SHIELD TAKES HIT!":ye=ye-2:w1=w1-1:if yg=4 w1=w1-2
 if ye<0 then ye=0
 if w1<=0 print "NO DAMAGE!":goto duel
 if yf print "ARMOR TAKES HIT!":yf=yf-3:w1=w1-2
 if yf<0 then yf=0
 if w1<=0 print "NO DAMAGE!":goto duel
wiz.a
 if yg=2 then if h+w1<26 gosub rnd.100z:if z>90 print \"YO! "xx$" LOOKS STRONGER!!":h=h+w1:goto druid.a
 print xx$" HIT! TAKES "w1" DAMAGE!":h=h-w1
druid.a
 if h<=0 then ch=1:goto hell
 goto duel
 
attack1
 if hp<=0 then ch=0:goto hell2
 if (instr("STORM",cw$)) or (ye>40) goto staff.1
 a=0:if yg=1 gosub rnd.100z:if z>70 a=1:if instr("cast.b",wx$) a=0
 if a=1 print \"ENERGY FLASHES FROM THE FINGERS OF "xx$"!!":gosub rnd.100z :w1=(z/20)+3:if instr("STAFF",cw$) print "THE STAFF AMPLIFIES IT!":w1=w1+3
 if a=1 print "..THUNDER ROCKS THE CHAMBER..":wx$=wx$+"cast.b":goto wiz.b
staff.1
 zz$=rnd$:w1=random(w4*100):w1=w1/100+1
 a=0:if pc=6 a=15:if yg=6 a=0
 if pc=8 a=8:if yg=8 a=0
 if mid$(zu$,2,1)="1" a=20
 if a>0 gosub rnd.100z:if z<a print\"HE SWUNG, BUT LOST SIGHT OF YA!":goto duel
 zx$="996877889":zz$=mid$(zx$,yi,1):a=val(zz$):a=a*10
 zx$=mid$(zx$,pr,1):yy=val(zx$):yy=yy*10
 a=a-yy:if a>0 a=a/2:gosub rnd.100z:if z<(a+1) print \"THE !#%%@# SWINGS OVER YOUR HEAD!":goto duel
 gosub get.numb:
 print xx$" STRIKES WITH THE "cw$"!"\:i$=". HIT CHANCE MOD: "
 if yx=1 a=a+2:if zq=1 print xx$" ATTACKS, YOU PARRY"i$"-2"
 if yx=5 a=a+3:if zq=1 print "BOTH PARRY"i$"-3"
 if yx=6 a=a-2:if zq=1 print "BOTH ATTACK"i$"+2"
 if (yx=13) or (yx=14) a=a-3:if zq=1 print "YOU ARE DOWN"i$"+3"
 if zz=5 a=a+3:if zq=1 print xx$" ROLLS"i$"-3"
 gosub rnd.100z:if pc=5 then if z>90 print \\"YOU DODGED THE BLOW!":goto duel
 if w3+xv>a then if z>15 print "[ HIT ]"\:else print "[ MISS ]"\:goto duel
 i$=". DAMAGE MOD: "
 w1=w1+xy:if yg=8 gosub rnd.100z:if z>90 print \"CRITICAL HIT!":w1=w1+2
 if yn>xp zz=(yn-xp)+1:zz=zz/2:w1=w1+zz:if zq=1 print xx$"'S LEVEL"i$"+"zz
 if yx=1 w1=(w1*3)/4:if zq=1 print xx$" ATTACKS, YOU PARRY"i$"0.75%"
 if yx=5 w1=w1/3:if zq=1 print "BOTH PARRY"i$"0.33%"
 if yx=6 w1=w1+2:if zq=1 print "BOTH ATTACK"i$"+2"
 if yx=13 w1=w1+3:if zq=1 print "YOU ARE KNOCKED DOWN"i$"+3"
 if yx=14 w1=w1+2:if zq=1 print xx$" ATTACKS WHILE YOU STAND UP"i$"+2"
 if zw=5 w1=(w1*3)/4:if zq=1 print "YOU ROLL"i$"0.75%"
 if zz=3 then if yx<>5 w1=(w1*2)/3:if zq=1 print xx$" PARRIED"i$"0.50%"
 if zz=4 w1=w1-2:if zq=1 print xx$" BASHES"i$"-2"
 if zz=5 w1=w1/2:if zq=1 print xx$" ROLLS"i$"0.50%"
 if w1>5 w1=(w1*4)/5
 if pc=4 then if sh print "(PALADIN SKILL!) ";
 if sh print "SHIELD TAKES HIT!":sh=sh-2:w1=w1-1:if pc=4 w1=w1-2
 if sh<0 then sh=0
 if w1<=0 print "NO DAMAGE!":goto duel
 if ar print "ARMOR TAKES HIT!":ar=ar-3:w1=w1-2
 if ar<1 then ar=0
 if w1<=0 print "NO DAMAGE!":goto duel
wiz.b
 if pc=2 then if hp+w1<26 gosub rnd.100z:if z>90 print \"YO! YOU FEEL STRONGER!" :hp=hp+w1:ps=ps+1:goto druid.b
 print n1$" HIT! TAKES "w1" DAMAGE!":hp=hp-w1:ps=ps-1
druid.b
 if hp<=0 then ch=0:goto hell2
 if ps<3 then wr$="":print\"THY STRENGTH IS  FADING...   UNABLE  TO DEFEND THYSELF!!"
 goto duel
 
flee
 gosub get.numb:a=(a*10):if (a+pi+pw+pe)>90 goto flee2
 print \xx$' BLOCKS YOUR PATH! 
"STAND AND FIGHT YOU COWARD!!"'
 goto attack1
flee2
 print \xx$' CRIES:
"RUN YOU COWARD!!! I WILL CATCH YOU
AT A LATER DATE!"'
 yx$=n1$+" FLED!":i$="sendmail":goto lnkduel2
 
hell
 i$="hell":goto lnkduel2
hell2
 i$="hell2":goto lnkduel2

prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return

get.numb
 zz$=rnd$:zz$=rnd$:a=random(999)
 a=(a/100):return

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
 
dropped
 i$="SPUR.DUEL"
 ch=0:if zv$<>"abortduel" then zt$="CARRIER LOST":goto hell2
 dy$=ds$+"spur.logon":link dy$,"quit3"
; ^ target ok

lnk.msc4
;..supply i$
 dy$=dz$+"spur.misc4":link dy$
;
special
 i$="SPECIAL"
lnkduel2
 dy$=ds$+"spur.duel2":link dy$
;
rnd.100z
 zz$=rnd$:z=random(1000):z=z/10+1:if z>100 z=1
 return
;
opnt.itm
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,yp
 input #1,z\i$:close:return
;
return
 on nocar goto dropped
 return
;
op.tact
 yw=10:if yi=4 or yi=7 or yi=8 then yw=9
 if yi=5 or yi=6 then yw=8
 if yi=3 then yw=7
 if (zw=1) or (zw=5) then if zs$="DOWN" zs$="STANDS UP..":zz=1:return
 gosub rnd.100z
 if zs$="DOWN" then if z>50 zs$="TRIES TO STANDS UP..":zz=1:return
 if zs$="DOWN" zs$="ROLLS ON THE GROUND..":zz=5:return
 yx=50+(yw*7)+(ye/3):yx=(yx-(zo*7))-(sh/3)if yx>60 yx=60
 if ye<sh yx=yx-(sh-ye)-10
;Increase chance of bash if player continually parries (xu) or attacks (zn)
 yx=yx+(xu*3)+(zn*3)
;if player on ground, fix chance of bash.
 if (zw=1) or (zw=5) yx=30
 if yx<15 yx=15:else if yx>65 yx=65
 if ye<6 yx=0
 gosub rnd.100z:if yx>z zs$="SHIELD BASHES!":zz=4:return
 yx=50+(yw*7)+(ye/3):yx=(yx-(zo*7))-(sh/3)
;If smaller shield, more likely to parry
 if ye<sh yx=yx-(sh-ye)
;If player not on ground (zw=1 or zw=5):
;Reduce chance of parry if player continually parries (xu)
;Increace chance of parry if player continually bashes (zp)
;Reduce chance of parry if player continually attacks (zn) or no shield (ye<6)
 if zw<>1 then if zw<>5 yx=yx+(xu*5)-(zp*5)+(zn*5):if ye<6 yx=yx+20
;Reduce chance of parry if opponent on ground
 if (zw=1) or (zw=5) then yx=yx+40
 if yx<25 yx=25:else if yx>70 yx=70
 gosub rnd.100z:if yx<z zs$="PARRIES WITH THE "+cw$+"!":zz=3:return
 zs$="ATTACKS!":zz=2:return
;
tactic
 gosub op.tact:yx=0
 print \xx$" "zs$\"YOU "zy$
 if zz=1 then if zw=1 print "BOTH STAND UP.":goto duel
 if zz=2 then if zw=3 yx=1
 if zz=3 then if zw=2 yx=11
 if zz=1 then if zw=2 yx=4
 if zz=2 then if zw=1 yx=14
 if zz=2 then if zw=2 yx=6
 if zz=3 then if zw=3 yx=5
 i$=str$(zw):gosub rnd.100z:a=25
 if zz=5 then if zw=4 a=35
 if zw=5 then if zz=4 a=35
 if zz=5 then if instr(i$,"24") then if z<a print "YOU TRIP OVER "xx$"!" :yx=15:goto tac.msg
 i$=str$(zz):if zw=5 then if instr(i$,"24") then if z<a print xx$" TRIPS OVER YOU!":yx=15:goto tac.msg
 if (zz=4) or (zw=4) goto tac.bash
 goto tac.msg

tac.bash
; bash
 a=0:if zo>yw a=(zo-yw)*8
 if yw>zo a=(yw-zo)*8
 if zq=1 print "SIZE DIFFERENTIAL: "a"%"
 a=100
 xz=sh:if xz>100 xz=100
 a=a+(xz/3)
 xz=ye:if xz>100 xz=100
 a=a-(xz/3)
 if zw=4 sh=sh-3:if sh<1 sh=0
 if zz=4 ye=ye-3:if ye<1 ye=0
;if oppnt bashes and plyr doesnt parry, or plyr bashes and oppnt doesnt parry
;larger size benifits
 if (zz=4 and zw<>3) or (zz<>3 and zw=4) then a=a+(zo*8):a=a-(yw*8):if zq=1 print "LARGER PERSON BENIFITS"
;if oppnt bashes and plyr parries or oppnt parries and plyr bashes
;smaller size benifits
 if (zz=4 and zw=3) or (zz=3 and zw=4) then a=a-(zo*8):a=a+(yw*8):if zq=1 print "SMALLER PERSON BENIFITS"
;if player continually parries, shield bash gets more effective (predictable)
 if zz=4 a=(a-10)-(xu*3):if zq=1 print xx$" BASHES. -10%":if xu>2 print\"Predicts you will parry, -"xu*3"%!"
 if zw=4 a=a+10:if zq=1 print "YOU BASH. +10%"
 if zz=1 a=a+10:if zq=1 print "YOU TRY TO KEEP "xx$" DOWN! +10%"
 if zz=2 a=a+10:if zq=1 print "YOU TRY TO CATCH "xx$" OFF GUARD! +10%"
;if player continually bashes, parry gets more effective (predicitable)
 if zz=3 a=(a-10)-(zp*3):if zq=1 print \xx$" TRIES TO TRIP YOU! -10%":if zp>2 print\"Predicts you will bash, -"zp*3"%!"
 if (zz=3) and (ye<sh) xz=(sh-ye)/3:a=a-xz:if zq=1 print "PARRY: "xx$"'S SMALLER SHIELD INCREASES AGILITY +"xz"%"
 if zw=1 a=a-10:if zq=1 print xx$" TRIES TO KEEP YOU DOWN! -10%"
;if player continually attacks, bash gets more effective
 if zw=2 a=(a-10)-(zn*3):if zq=1 print xx$" TRIES TO CATCH YOU OFF GUARD! -10%" :if zn>2 print "Predicts you will attack, -"zn*3"%!"
 if zw=3 a=a+10:if zq=1 print "YOU TRY TO TRIP THE CHARGING "xx$"! +10%"
 if (zw=3) and (sh<ye) xz=(ye-sh)/3:a=a+xz:if zq=1 print "PARRY: YOUR SMALLER SHIELD INCREASES AGILITY +"xz"%"
 i$=" A BIT MORE TIRED. "
 if ce>(pe+4) a=a-10:if zq=1 print "YOU ARE"i$"-10%"
 if pe>(ce+4) a=a+10:if zq=1 print xx$" IS"i$"+10%"
 i$=" A BIT CLUMSIER. "
 if cd>(pd+4) a=a-10:if zq=1 print "YOU"i$"-10%"
 if pd>(cd+4) a=a+10:if zq=1 print xx$" IS"i$"+10%"
 i$=" A BIT WEAKER. "
 if cs>(ps+4) a=a-10:if zq=1 print "YOU ARE"i$"-10%"
 if ps>(cs+4) a=a+10:if zq=1 print xx$" IS"i$"+10%"
 i$=" INITIATIVE BONUS. "
 if vu=5 a=a+10:if zq=1 print "YOU HAVE"i$"+10%"
 if vu=3 a=a-10:if zq=1 print xx$" HAS"i$"-10%"
 gosub rnd.100z:z=z+50
 if a>140 a=140
 if a<60 a=60
 if z>(a+20) yx=13
 if z<(a-20) yx=3

tac.msg
 if (yx=3) and (zw=3) and (zz=4) print "YOU TRIP UP "xx$"! ";
 if (yx=3) and (zz<>5) print xx$" FALLS DOWN!"
 if (yx=13) and (zw=4) and (zz=3) print xx$" TRIPS YOU UP! ";
 if (yx=13) and (zw<>5) print "YOU FALL DOWN!":if xu+zp+zn>3 print \"'YOU'RE SOOO PREDICTABLE! HAHAHA!!!' SHOUTS "xx$
 if (yx=3) or (zz=5) zs$="DOWN":if zw=5 yx=15
 if (yx=13)or (zw=5) zy$="DOWN":if zz=5 yx=15
 if yx=15 zy$="DOWN":zs$="DOWN":print "BOTH ARE ON THE GROUND!":goto duel
 if (zz=4) or (zw=4) then if yx=0 print "SHIELD BASH FAILS!"
 if instr(" UP",zs$) print xx$" STANDS UP."
 if instr(" UP",zy$) print "YOU STAND UP."
 if (zz=1) or (zz=5) then if ((zw=1) or (zw=5)) goto duel
 goto attack
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):if dr$<>"" ready dr$
 return
;
compile
 if un=1 print \"Compiled.":link "k:system.seg"
comp.ck
 print " ok..":return
;

;... spur.misc3.s

 public misc
 public compile

 on nocar goto dropped

 if info(5) print "spur.misc3--";:gosub comp.ck
 free:xu$="[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 if (instr("EXAMINE",i$)) or (i$="X") goto examine
 if i$="LOOT" goto loot


cast
 if xs=0 print \"No Spells.":goto advent
 gosub prspell
cast.a
 input @2\"Cast which spell number? (?=list):"a$:if a$="" goto advent
 if a$="?" gosub prspell:goto cast.a
 if instr(" ",a$) print \"There was a space in your command.":goto cast.a
 x=val(a$):if (x<1) or (x>xs) print \"You do not know that spell.":goto cast.a
 y=(x*4)-3:l=len(xs$):x=val(mid$(xs$,y))
 xs=xs-1:if xs=0 then xs$="":goto spl.read
 if y=1 then xs$=mid$(xs$,5):goto spl.read
 if (y+4)>l then xs$=left$(xs$,y-1):goto spl.read
 xs$=left$(xs$,y-1)+mid$(xs$,y+4)
 
spl.read
 dy$=dw$+"spells"
 open #1,dy$
 position #1,40,x
 input #1,cb$\q$,q2$,q3,q4
 close
 
cst.outc
 b=20-pi:if pr=2 then b=b+2
 if b<3 then b=3
 zz$=rnd$:a=random(b*100):a=a/100+1:b=0
 if a<q3 then b=1:goto cast.spl
 gosub rnd.10
 if a<5 then b=2
 if (not b) goto spl.fail
 
cast.spl
 cs=0:c1$=left$(q2$,1):c2=val(right$(q2$,1)):c2=c2/b
 zz=0:if pc=2 then if c1$<>"M" zz=2:print \"DRUID POWER!"
 if pc=1 then if instr("STAFF",wr$) then if instr(c1$,"SWDCEI") print \"The staff trembles..":zz=1:if c1$="M" zz=4
 if c1$="S" goto cst.strn
 if c1$="W" goto cst.wisd
 if c1$="D" goto cst.dext
 if c1$="C" goto cst.cons
 if c1$="E" goto cst.engy
 if c1$="I" goto cst.intl
 if c1$="T" goto cst.xfer
 if c1$="P" goto cst.plyr
 if c1$="M" goto cst.mons
 if c1$="L" goto cst.dnlv
 if c1$="U" goto cst.uplv
 if c1$="R" goto cst.shop
 if c1$="G" goto cst.spur
 if c1$="A" goto cst.aura
 
cst.strn
 zs=20:if pr=2 zs=24
 if (b=1) and (ps<zs) then ps=ps+c2+zz:print "(You feel a bit stronger)":goto spl.succ
 if ps=>c2 then ps=ps-c2:print "(You feel a bit weaker)"
 goto spl.back
 
cst.wisd
 if (b=1) and (pw<20) then pw=pw+c2+zz:print "(You feel a bit wiser)":goto spl.succ
 if pw=>c2 then pw=pw-c2:print "(You feel a bit more foolish)"
 goto spl.back
 
cst.dext
 if (b=1) and (pd<20) then pd=pd+c2+zz:print "(You feel a bit more skillful)":goto spl.succ
 if pd=>c2 then pd=pd-c2:print "(You feel a bit more clumsy)"
 goto spl.back
 
cst.cons
 if (b=1) and (pt<20) then pt=pt+c2+zz:print "(You feel healthier)":goto spl.succ
 if pt=>c2 then pt=pt-c2:print "(You feel a bit less healthy)"
 goto spl.back
 
cst.engy
 zs=20:if pr=1 zs=24
 if pr=9 zs=22
 if (b=1) and (pe<zs) then pe=pe+c2+zz:print "(You feel a surge of energy)":goto spl.succ
 if pe=>c2 then pe=pe-c2:print "(You feel a bit tired)"
 goto spl.back
 
cst.intl
 if (b=1) and (pi<20) then pi=pi+c2+zz:gosub smart:goto spl.succ
 if pi=>c2 then pi=pi-c2:print "(You feel a bit dumber)"
 goto spl.back
 
cst.xfer
 if b=1 print \'
Your gold has been transferred to
your bank account.':bh=bh+gh:bl=bl+gl:gh=0:gl=0:goto cst.x2
 print \'
Spell has backfired.  You are now
carrying all your gold.':gh=gh+bh:gl=gl+bl:bh=0:bl=0
 
cst.x2
 if bl=>10000 then bl=bl-10000:bh=bh+1
 if gl=>10000 then gl=gl-10000:gh=gh+1
 goto advent
 
cst.plyr
 if b=2 goto cst.pl2
 gosub rnd.10:zz=23+xp:if pr=2 zz=zz+2
 if hp<zz then hp=hp+c2:goto spl.succ
cst.pl2
 if hp>c2 then hp=hp-c2
 goto spl.back
 
cst.mons
 if (not mw) print \"No monster here!":goto spl.fail
 if instr("%",wy$) print \m$" sneers at your feats of magic.":goto spl.fail
 if instr(":",wy$) print \"Mechanical devices are unaffected by magic!":goto spl.fail
;.. for casting against charmed monsters
 if (zs=997) or (zq>0) then zs=997:zq=0
 zr=5:if pc=1 then zr=6
 if instr("~",wy$) gosub rnd.10:if a>zr print m$" appears unaffected!" :goto spl.fail
 if b=2 then if pc>1 goto cst.mns2
 gosub rnd.10:if pc>1 goto wiz.a
 print "(+5 experience)":ep=ep+5:a=a+1:c2=c2+2+xp
 if instr("STAFF",wr$) print \"Power BLASTS from the staff!":a=a+1:c2=c2+4
 if not instr("STAFF",wr$) print \"Fire sizzles from your fingertips!"
wiz.a
 ms=ms-c2:if a>5 then ms=0
 print "The area glows with a erie blue light.."
 if ms<=0 goto cst.mns3
 if mw print \m$" appears to have weakened."
 goto spl.succ
cst.mns2
 ms=ms+c2:print \'
The spell appears to have made ':print m$" stronger!"
 goto spl.back
cst.mns3
 ms=0:print \"A HORRID SHRIEK COMES FROM "m$"!"
 i$="kill.mon":dy$=dz$+"spur.combat":link dy$,"misc"
;
cst.dnlv
 if mw then if instr(".",wy$) goto spl.fail
 if instr("<<",lo$) goto spl.fail
 if cl>4 goto spl.fail
 if b=2 goto cst.dn2
 if lc>cl then cl=cl+1:cs=1:goto spl.succ
 goto spl.fail
cst.dn2
 if cl<>1 then cl=cl-1:cs=1:goto spl.back
 goto spl.fail
 
cst.uplv
 if mw then if instr(".",wy$) goto spl.fail
 if instr("<<",lo$) goto spl.fail
 if cl=6 goto spl.fail
 if b=2 goto cst.up2
 if cl<>1 then cl=cl-1:cs=1:goto spl.succ
 goto spl.fail
cst.up2
 if lc>cl then cl=cl+1:cs=1:goto spl.back
 goto spl.fail
 
cst.shop
 if b=2 goto cst.shp2
 if mw then if instr(".",wy$) then if not instr(":",wy$) print\m$" CASTS 'FREEZE ADVENTURER' SPELL!":goto spl.fail
 i$=m$+" LOOKS PUZZLED AS YOU FADE FROM VIEW."
 if instr(":",wy$) i$="SENSORS ON:  "+m$+" GO NUTS AS YOU DEMATERIALIZE!"
 if mw print \i$:mw=0:mf=0:m$="":wy$=""
 cr=1:di=6:cs=1:goto spl.succ
cst.shp2
 zz$=rnd$:cr=random(nr):if cr=0 goto cst.shp2
 cs=1:goto spl.back
 
cst.spur
 if cl<>sl print \"SPUR is not on level "cl"!":goto spl.fail
 cr=sr:cs=1:print \"Prepare thyself...":goto spl.succ
 
cst.aura
 if instr("BOOTS",q$) goto boots
 if instr("*",q$) goto poison
 if instr("@",q$) goto disease
 if instr("GLOW",q$) goto wiz.glw
 if instr("DRUID HEALTH",q$) goto dru.hlth
 x=q4/10:if tm=0 then tm=mm+x+c2:else tm=tm+x+c2
 goto spl.succ
 
boots
 if instr("*BO",ys$) goto spl.fail
 print \"10 minutes added.":ev=ev+600
 if len(ys$)<240 ys$=ys$+"*BO"
 goto spl.succ
poison
 if mid$(zu$,3)="0" print \"Why? You wern't poisoned!":goto spl.fail
 print \"Poison.. gone!"
 i$="zu$":zw=3:zw$="0":zt=4:gosub lnk.misc:goto spl.succ
disease
 if mid$(zu$,4)="0" print \"Why, You don't have a disease!": goto spl.fail
 print \"You feel much better!"
 i$="zu$":zw=4:zw$="0":zt=4:gosub lnk.misc:goto spl.succ
wiz.glw
 zw=val(mid$(zu$,7,1)):if zw>1 print \"Spell already in effect!":goto spl.fail
 print \'
A shimmering glow surrounds you! (-2 damage from monsters for duration of play session, +20 effective shield size in duels)'
 if zw=0 zw=3:else zw=2
 zw$=str$(zw):zu$=left$(zu$,6)+zw$+mid$(zu$,8):goto spl.succ
dru.hlth
 print \\"A blue glow surrounds you!"\
 if hp<25 print "Hit points return":hp=25
 if ps<20 print "Strength returns":ps=20
 if pe<20 print "Energy returns":pe=20
 if pt<20 print "Health returns":pt=20
 if mid$(zu$,3,1)="1" print "Poison gone!":zu$=left$(zu$,2)+"0"+mid$(zu$,4)
 if mid$(zu$,4,1)="1" print "Disease gone!":zu$=left$(zu$,3)+"0"+mid$(zu$,5)
 if info(5) print "zu$="zu$
 goto spl.succ
;
spl.succ
 print \"Spell successful!"

spl.link
 if cs then dy$=dz$+"spur.misc":i$="travel3":link dy$
 goto advent
 
spl.back
 print \"Spell Backfired!"
 goto spl.link
 
spl.fail
 print \"Your spell fizzles...":if pi<15 print "(Prehaps, if you were smarter..)"
 goto spl.link
;
lnk.misc
; (supply i$=name of routine in spur.misc)
 dy$=dz$+"spur.misc":link dy$,"misc"
main.msc
 dy$=dz$+"spur.main":link dy$,"misc"
;
misc
 on nocar goto dropped
 if i$="return" return
 print \\\"BAD VALUE OF I$ IN SPUR.MISC3! I$="i$
advent
 dy$=dz$+"spur.main"
 link dy$
;
dropped
 i$="SPUR.SUB"
 dy$=ds$+"spur.logon"
 link dy$,"quit3"
; ^ target ok
smart
 print "(You feel a bit smarter)":return
;
rnd.10
 zz$=rnd$:a=random(999):a=a/100+1:return
;
prspell
 if xs=0 print \"No Spells.":return
 dy$=dw$+"spells"
 open #1,dy$
 print:for x=1 to xs
 y=(x*4)-3:a=val(mid$(xs$,y))
 position #1,40,a
 input #1,cb$\q$,q2$,q3,q4
 setint(1)
 print right$("   "+str$(x),3)". - ";
 print q$;chr$(32,21-len(q$))" : "q3"0%"
 if key(1) x=xs
 next:close:return
;
examine
 if instr("~*",lo$) gosub hidden:print \"Nothing else..":goto advent
 if (i$="EXAMINE") or (i$="X") i$="EXAMINE ALL"
 a$=mid$(i$,9):if a$<>"ALL" gosub exam.a:goto advent
 if it$<>"" a$=it$:gosub exam.b
 if fd$<>"" a$=fd$:gosub exam.b
 if wp$<>"" a$=wp$:gosub exam.b
 if (mw) or (md) a$=m$:gosub exam.b:if instr("#",wy$) a$="STATUE":gosub exam.b
 zt$="*":ch=2:gosub plyr.loc
 if it$+fd$+wp$="" then if mw+md=0 then if ch=2 print \"This area is empty.."
 goto advent
exam.b
 if md=2 then if a$=m$ a$=m$+" TRACKS"
 print \"EXAMINING "a$".."
exam.a
 if instr("STATUE",a$) then if instr("#",wy$) print\"It is made of stone, and is kind of ugly.":return
 if a$=it$ then ty$=i1$:goto exam2
 if a$=fd$ then ty$=ft$:goto exam2
 if a$=wp$ then ty$=wt$:goto exam2
 if m$<>"" then if instr(m$,a$) goto exam2
 zt$=a$:ch=2:gosub plyr.loc:if ch=4 goto advent
 goto exam3
exam2
 gosub rnd.100a:if a>60 print \"Your examination fails...":return
 if xz$=a$ print \"You have already examined this!":return
 xz$=a$:if m$<>"" then if instr(m$,a$) goto exam.mon
 if not instr(ty$,"MCB") goto exam3
 if ty$="M" print \"This "a$" is Magical."
 if ty$="C" print \"This "a$" is Cursed.":goto smarter
 if ty$="B" then if instr("SCROLL",a$) print\"It is a scroll of magic!":return
 if ty$="B" print \a$" is a book."
 return
exam3
 if a$<>it$ then if a$<>fd$ then if a$<>wp$ print\"You either spelled it wrong, or are seeing things..":print "('X' examines all)":return
 if a$="CRYSTAL PENDANT" print \"In small letters you see; 'PROTECTS FROM STONE SPELL!'":return
 if a$="ICE CRYSTAL" print \"In small letters you see; 'ACME ANTI-FIRE DEVICE'":return
 if instr(a$,"CROWN OF MIDASFOUNTAIN OF YOUTH") print \"It has a strange power..":return
 if a$="GOLD ROSE"print\"It looks VERY valuable, but beware the thorns!":return
 if instr("POTION",a$) print \"It is a magic potion!":return
 if instr("MOONSHINE",a$) print \"It is poison!":goto smarter
 if a$="OLD HAMBURGER" print \"It don't look very good..":goto smarter
 if instr(a$,"STRANGE WEAPONFUNNY DOLLPANDORAS BOX") print \"It looks suspicious!":goto smarter
 if instr("STORM",a$) print \"There is much power in the "a$"!":return
 if a$="TUT'S TREASURE" gosub treasure
 if i=139 a=1:gosub messages:gosub obelisk:cr=762:i$="travel2":pop:goto main.msc
 if random(100)>50 print \"Looks ok to me..":return
 print \"It looks pretty ordinary..":return

hidden
 i$=""
 if instr("~*E",lo$):e=1:i$="EAST"
 if instr("~*N",lo$):n=1:i$="NORTH"
 if instr("~*S",lo$):s=1:i$="SOUTH"
 if instr("~*W",lo$):w=1:i$="WEST"
 if (cl=6) and (cr=612) then if instr("144",xi$) print \'
A RAY OF RUBY LIGHT BLAZES FROM THE
SLIPPERS TOWARDS THE SOUTHERN WALL!':s=1:i$="SOUTH"
 if i$<>"" print \"YOUR PROBING OPENS A DOOR TO THE "i$"!"\:pop:goto advent
 a=0:if cl<>6 return
 if cr=752 a=131:i$="RED SECURITY CARD"
 if cr=93 a=124:i$="RADIATION SUIT"
 if cr=180 a=123:i$="GEIGER COUNTER"
 if cr=557 a=145:i$="BROOMSTICK"
 if a=0 return
 a$=str$(a) if (instr(a$,xi$)) or (instr(a$,ai$)) return
 print \"AHHAA! YOU FIND A "i$\
 i=a:it$=i$:i1$="T":pop:goto advent

exam.mon
 if md=0 print \m$" DOESN'T LIKE BEING EXAMINED!":return
 if md=2 print \"YEP, THEY ARE "m$" TRACKS AWRIGHT.":return
 if info(5) print "wy$="wy$"<-"
 if instr(":",wy$) print \"IT IS A TWISTED WRECK!":return
 gosub rnd.100a
 i$="YOUR SEARCH REVEALS NOTHING ON THE "+m$
 if instr("@@",lo$) i$="FISH ARE NIBBLING ON THE "+m$
 if instr("**",lo$) i$="THE "+m$+" IS QUITE FROZEN!"
 if a>40 i$="YEP. IT'S DEAD AWRIGHT.."
 if a>70 i$="THE "+m$+" IS QUITE UGLY, ACTUALLY.."
 if it$="" then if pr=7 gosub rnd.100a:if a<26 print \"YOUR DWARVISH EYES SPOT SOMETHING!":goto mon.dv
 gosub rnd.100a:if a>70 goto mon.fd
 gosub rnd.100a:if (a>15) or (it$<>"") print \i$:goto mon.des
mon.dv
 gosub rnd.100a:i=16:it$="COIN":i1$="T":iv=1
 if a>40 it$="GOLD SACK":iv=3
 if a>70 it$="DIAMOND":iv=4
 if a>90 it$="SACK OF DIAMONDS":iv=6
 print \"YOUR SEARCH REVEALS A "it$"!":return
mon.fd
 gosub rnd.100a
 if (pr=2) or (pr=8) then a=a+25
 if pr=4 a=a-25
 if pr=9 a=a-12
 if a<1 print \"YOUR ELVISH EYES WRINKLE IN DISGUST.";:a=0
 if (a<50) or (fd$<>"") print \i$:goto mon.des
 fd=69:fd$=m$+" MEAT"
 i$="OGRE'S":if pr=8 i$="ORCISH"
 if (pr=2) or (pr=8) then if a>100 print \"YOUR "i$" MOUTH WATERS!";
 print \"YOU DECIDE THE "m$" LOOKS EDIBLE! (sort of..)":return
mon.des
 gosub rnd.100a:if a>2 return
 print \"YUK! YOU PICKED UP A DISEASE FROM THE THING!"
 i$="zu$":zw=4:zw$="1":zt=4:goto lnk.misc

treasure
 if mid$(zu$,9,1)<>"0" return
 print \\'
AHAA! Whats this?!?! Your careful examination reveals a deadly trap, which you
carefully disarm..'
 gosub smarter
 pop:i$="zu$":zw=9:zw$="1":zt=4:goto lnk.misc

smarter
 print "(You feel a bit smarter)":if pi<25 then pi=pi+2
 if pi>24 then print "(but not much..)"
 return
;
l.return
 dy$=dz$+"spur.main":link dy$,"return"
;
rnd.100a
 zz$=rnd$:a=(random(999)/10)+1:return
;

loot
 if instr("loot",ys$) print \'
The SPUR gestapo frowns on taking too
many items per game session!'\:goto advent
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
 i$="Bad loot item string. zr="+str$(zr):gosub add.lg
 i$="zt$="+zt$+", n$="+n$:gosub add.lg 
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
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"- COMRADES!"
 print #1, i$" PROTECTED "n2$
 print #1, "FROM PILLAGE, IN "ww$".."
 print #1,xu$:close
 goto loot2
;
obelisk
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1,"[STARDATE]: "left$(date$,6)yr$" "time$
 print #1,n1$" JOURNIED BEYOUND"
 print #1,"JUPITER, PASSED THE PALE OF HUMANITY,"
 print #1,"AND DISAPPEARED INTO THE INFINITE.."
 print #1,xu$:close
 return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):ready dr$:return
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
 if ch>1 x=yx:gosub rd.plyr:goto ply.loc7
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
 dy$=mid$(dy$,yw+1):yy=instr(wx$,dy$):if yy goto ply.loc1
 return
ply.loc8
 if cl=1 dy$=tg$
 if cl=2 dy$=tb$
 if cl=3 dy$=tc$
 if cl=4 dy$=td$
 if cl=5 dy$=te$
 if cl=6 dy$=th$
 return
;
rd.plyr
 if zt$<>"*" then if zt$<>n2$ return
 ch=4:print \"Examine "n2$;:input @2" y/[N]:"i$
 if i$<>"Y" return
 gosub rd.plyr2:n2$=mid$(n2$,2)
 print \n2$" looks like a";
 i$=" greenhorn":if yn>1 i$="n experienced":if yn>2 i$=" veteran"
 if yn>4 i$="n elite":if yn>6 i$=" deadly"
 print i$" ";
 yg=(yg-1)*7+1:yi=(yi-1)*8+1
 i$="Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc     Half-Elf"
 i$=mid$(i$,yi,8):a=instr(" ",i$):if a i$=left$(i$,a-1)
 print i$" ";
 i$="Wizard Druid  FighterPaladinRanger Thief  Archer AssasinKnight "
 i$=mid$(i$,yg,7):a=instr(" ",i$):if a i$=left$(i$,a-1)
 print i$" in ";:p2=yh+ce+cd
 i$="poor":if p2>44 i$="fair":if p2>59 i$="good":if p2>74 i$="excellent"
 print i$" health,"\"carrying a ";
 i$="flat":if yb>100 i$="slender":if yb>200 i$="modest":if yb>500 i$="goodly"
 if yb>700 i$="fat"
 if ya>0 i$="large":if ya>1 i$="huge":if ya>2 i$="HUMGEOUS"
 print i$" gold pouch, ";:i$="no"
 if ye>0 i$="a small":if ye>25 i$="a modest"
 if ye>50 i$="a fair sized":if ye>75 i$="a big"
 print i$" shield and ";:i$="no":if yf>0 i$="little"
 if yf>40 i$="a modest amount of":if yf>70 i$="a large amount of"
 print i$" armor."
 print "Looks like "n2$" is packing ";
 i$=dx$+"spur.weapons"
 open #1,i$
 position #1,64,x
 input #1,c\a$:close
 if c=0 print "No Weapons!":return
 i$=dx$+"weapons":open #1,i$
 for e=1 to c
 y=(e*4)-3:a=val(mid$(a$,y))
 position #1,34,a,2
 input #1,w$\w1,w2\w5:if e>1 print " and ";
 if mid$(w$,4,3) ="EXC" print mid$(w$,4);
 if mid$(w$,4,3) <> "EXC" and instr("A*E*I*O*U",mid$(w$,4)) print "an" wq=1
 if wq=0 and mid$(w$,4,3) <> "EXC" print "a "mid$(w$,4);
 wq=0:next:close:print "." 
 return

rd.plyr2
 i$=dx$+"spur.users"
 open #1,i$:position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$:close:return

add.lg
;.. i$=log message
 create "a:add.log":open #2,"a:add.log"
 append #2:print #2,"[spur.misc3] "i$:close #2:return

compile
 if info(5) print \"Compiled..":link "k:system.seg"
comp.ck
 print "..ok":return
;

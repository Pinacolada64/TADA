;.. spur.misc6.s
;.. modified with Appleworks

 public compile

 on nocar goto dropped
 if flag(32) print "spur.misc6--";:gosub comp.ck
 free
 if i$="dead.a" goto dead.a
 if i$="dropdead" goto dropdead
 if i$="dead2" goto dead2c
 if i$="RANDOM" gosub random:goto lnk.m.rt
 if i$="LOCKER" goto locker
 if i$="REST" goto rest
 if i$="METEOR" gosub meteor:goto lnk.m.rt
 if i$="galad" gosub galad:goto advent
 i$="Bad value of i$ in spur.misc6! i$="+i$
 print \i$:gosub add.log
advent
 dy$=dz$+"spur.main":link dy$
lnk.misc
 dy$=dz$+"spur.misc":link dy$,"misc"
lnk.m.rt
 dy$=dz$+"spur.main":link dy$,"return"
lnk.shop
 dy$=dz$+"spur.shop":link dy$,"main1"
;
dropped
 i$="SPUR.MISC6"
dropped1
 dy$=ds$+"spur.logon":link dy$,"quit3"
;
dead.a
 gosub dead:goto dead2
;
dropdead
 gosub dead2a:gosub dead:i$="SPUR.DUEL":goto dropped1
;
dead
 mf=0:mw=0:zz$=wr$:wr$="":xt$="":xt=0:xm$="":xm=0:cp=0:dp=0
 if z<>18 print \hl$"You have not survived.."of$:else print \"You pass thru the portal..."
 dy$=dx$+"weapons"
 open #1,dy$
 if xw=0 goto dead1
 for j=1 to xw
 y=(j*4)-3:x=val(mid$(xw$,y))
 if x>10 position #1,34,x:print #1,"1"
 next
;
dead1
 close
 if d1$<>"*" then x=h1:gosub fre.ally
 if d2$<>"*" then x=h2:gosub fre.ally
 if d3$<>"*" then x=h3:gosub fre.ally
 if (not mv) return
 dy$=dx$+"spur.time"
 open #1,dy$
 position #1,12,un
 eu=eu+ex:a$=left$(date$,5)+"":if left$(cm$,5)<>a$ then eu=0
 print #1,a$,eu:close
 return
;
dead2
 on nocar goto dropped
 print \"The land fades from your eyes..."
 cl=0:cr=0:dy$=ds$+"spur.logon":link dy$,"quit1"
;
fre.ally
 if x=0 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
dead2c
 gosub dead2a:goto dead.a
dead2a
 vv=0:if z<>18 print \"oh..oh..."
 dy$=dx$+"battle.log":create dy$:open #1,dy$:append #1
 zw$="OBITUARY":if z=18 zw$="STAR CHILD"
 print #1, left$(date$,6)yr$" "time$"- "zw$
 zt$="DIED":if z=18 zt$="BECAME IMMORTAL"
 zw$=n1$+" "+zt$+" IN "+ww$+",":xu=len(zw$)
 if xu<40 print #1, zw$:goto dead2b
 print #1, n1$" "zt$
 print #1, "IN "ww$","
dead2b
 if z=1 print #1, "OF STARVATION!!"
 if z=2 print #1, "BY COMMITING SUICIDE..":goto win
 if z=3 print #1, "PICKING UP A CURSED OBJECT!"
 if z=4 print #1, "WHILE BATTLING "m$"."
 if z=5 then if wr$<>"" print #1, "KILLED BY THE "wr$"!"
 if z=6 print #1, "TURNED TO STONE BY "m$"!"
 if z=7 print #1, "FROM BEING POISONED!"
 if z=8 print #1, "FROM A STRANGE DISEASE.."
 if z=9 print #1, "KILLED BY THE DEATH AMULET!"
 if z=10 print #1,"FROM DROWNING.."
 if z=11 print #1,"FROM FREEZING TO DEATH.."
 if z=12 or z=0 print #1,"FIGHTING A DUEL.."
 if z=13 print #1,"ZAPPED BY THE SPIRIT OF THE DUNGEON!"
 if z=14 print #1,"KILLED BY THE MAGIC OF "m$"!"
 if z=15 print #1,"FROM DECOMPRESSION!"
 if z=16 print #1,"FROM RADIATION POISONING!"
 if z=17 print #1,"FROM AN ACCIDENTAL CONCUSSION"
 if z=18 print #1,"PASSING THRU THE PORTAL OF SPUR!":goto win
 if z=19 print #1,"KILLED BY A BOOBY TRAP!"
 if z=20 print #1,"BY FALLING FROM A HIS STEED!"
 if flag(7) print #1,"BUT RETURNED TO LIFE!":goto win
 if mid$(zu$,8,1)="1" print #1, "BUT WAS REVIVED BY THE AMULET OF LIFE!":goto win
 if pc=9 if vk>1600 print #1,"BUT THE SAINTLY KNIGHT WAS REVIVED BY THE GODS!!"
win
 print #1, "[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 close:if (mid$(zu$,8,1)="1") or (flag(7)) then if z<>2 i$="":goto revive
 if pc=9 if vk>1600 if z<>2 i$="SAINT":goto revive
 ai=0:ai$="":if z=6 gosub statue
;
 dy$=dx$+"spur.a1$":open #1,dy$
 position #1,64,un
 input #1,g5,g6,g7,g8,g9,g9,g0
 if z=2 print \"(Suicides lose any money saved with Vinney..)":g5=0:g6=0
 position #1,64,un
 print #1,g5,g6,g7,g8,0,g9,g0
 close:return
;
statue
 print \"(Carving your statue!)"
 dy$=dx$+m$:if left$(m$,4)="THE " dy$=dx$+mid$(m$,5)
 kill dy$:create dy$:open #1, dy$:append #1
 print #1,n1$:close:return
;
revive
 a=20:if flag(7) a=21
 if i$="SAINT" a=33
 gosub messages
 zw$="0":if not flag(7) zw=8:gosub zu$
 zw=3:gosub zu$:zw=4:gosub zu$
 if xn=0 xn=un
 sn=xn:hp=10:ps=10:pt=10:pi=25:pe=10:pw=25:pd=10:mw=0:mf=0:m$ ="":wy$=""
 di=6:cr=1:i$="travel3":goto lnk.misc
;
random
 gosub dead.al
 if not instr("*GC",ys$) gosub chk.god:if i$<>"" return
 gosub rnd.100z
 if z<15 if not instr("*GA",ys$) goto galad
 if z<32 if not instr("*ME",ys$) goto meteor
 if z<49 if not instr("*AF",ys$) goto al.find
 if z<66 if not instr("*EN",ys$) goto enforce
 if z<83 if not instr("*VN",ys$) goto djinn
 if instr("*gi",ys$) return

; Little Girl
 if len(ys$)<240 ys$=ys$+"*gi"
 i$="A little boat pulls along side..":if cl>5 i$="A little spacesuit pulls along side, retro-rockets firing."
 if instr("@@",lo$) print \i$
 print \'
A little girl  approaches  you! She  is quite skinny and very poor looking..
"Oh  please,  please, kind  person.  My grandmother  is  very  sick, and I dont
know what to do! Wont you  please  give something that I can pawn so I can  buy
her the medicine she needs?"'
 if cl>5 print \"'Now, how did SHE get here?' you wonder to yourself.."
give
 input @2\"G)ive, I)gnore, A)ttack :"i$
 if i$="A" goto girl.m1
 if i$="I" gosub rnd.10z:if z>5 goto girl.m
 if i$="I" goto girl.sad
 if i$="G" print \"The girl peers in your sack hopefully..":goto drop.itm
 goto give
drop.itm
 if xi<1 xi=0:print \"No Items!":goto give
 dy$=dw$+"items":open #1,dy$
drop.a
 print \"You are carrying:"\
 zr=xi:zs$=xi$:gosub lst.itms
drop.b
 input @2 \"Give which item? (?=list):"a$:x=val(a$):if a$="" close:goto give
 if a$="?" goto drop.a
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto drop.b
 y=(x*4)-3:a=val(mid$(xi$,y))
 if a=67 then if mid$(zu$,2,1)="1"print "Can't, you are USEing it!":goto drop.b
 if (a=73) or (a=76) print \"The girl refuses to hold it!":goto drop.b
 close:l=len(xi$):y=(x*4)-3
 print \"The little girl takes it..'OH THANK YOU!!'"\
 if hp+ps+pe+pt<40 print '
Looking at you, she sees you are not feeling too well. She gently lays a small hand on your head...'
 if hp<10 hp=hp+10:print "(Hit points return)"
 if ps<10 ps=ps+10:print "(Strength returns)"
 if pe<10 pe=pe+10:print "(Energy returns)"
 if pt<10 pt=pt+10:print "(You feel healthier)"
 if pi<27 pi=pi+2:print "(You feel more intelligent)"
 if pw<27 pw=pw+2:print "(You feel wiser)"
 if vk<2000 vk=vk+5
 dy$=dx$+"little.girl"
 open #1,dy$:input #1,z
 a=random(z):if a=0 a=z
 position #1,170,a:input #1,i$:close
 print \"She smiles a secretive little smile;"
 print "'"i$"'"\
 i$="The little girl runs off.."
 if instr("@@",lo$) i$="The little girl rows off..":if cl>5 i$="The little girl fires steering rockets, and leaves.."
 print \i$
 zr=xi:zs$=xi$:gosub drp.itm:xi=zr:xi$=zs$
 return

girl.m1
 a=10:if pc=9 a=15
 if vk>a vk=vk-a
girl.m
 print \"Suddenly, the girl seems to get bigger";
 for a=1 to 10:print "!";:gosub delay:next
 print \\\hl$"'NOW YOU DIE!!'"of$\\:gosub delay
 m=106:return
girl.sad
 print \"The poor little girl, runs away crying.."\
 if pi>3 pi=pi-2:print "(You feel a bit dumber)"
 if pw>4 pw=pw-3:print "(you feel more foolish)"
 return
;
enforce
 ex=clock(1)-ew:if info(2)=1 if (ev-ex)<300 return
 if (ev-ex)<180 return
 if len(ys$)<230 ys$=ys$+"*EN"
 pop:if instr("@@",lo$) print \"A dark craft pulls along side.."
 print \"Suddenly, you are confronted by a shadow looming out of the darkness!"
 gosub delay
 print \"'I am THE ENFORCER! How dare you invade my turf?!'"
 gosub delay
 print \'
The Shadow unsheaths a deadly looking sword.. "Now! You shall taste the wrath
of The Sun-Sword!"'
 zw$="ENFORCER":yz=1:xx$="THE ENFORCER":cw$="SUN-SWORD"
 gosub set.stat
;w4=weapon damage, w3=weapon 'to hit', xy=damage skill, xv= 'to hit' skill
 w4=9:w3=6:xy=2+(xp/4):xv=2+(xp/4):zw=2:goto lnk.duel
;
set.stat
 x=1:au=0:ys=1:yp=1:yl=cl:yr=cr:yh=hp+1
 cs=ps+1:ct=pt+1:ci=pi+1:ce=pe+1:cw=pw+1:cd=pd+1
 ya=0:yb=0:yc=0:yd=0:yf=ar:yg=pc:yi=pr:yj=ep:yn=xp
 ye=sh:if ye<1 ye=20
 ye=ye+random(30):if ye>100 ye=100
 return
;
lnk.duel
 gosub delay:print \hl$"'I CHALLANGE YOU TO A DUEL!'"of$\
 zt$=zu$:zv$="autoduel":wx$="random"
 yx$="":hh=0:b=0:wr$="":sx=0:zy$="":zs$=""
 zt=0:zs=0:vy=0:zm=0:vq=0:zq=0:zu=0
 dy$=ds$+"spur.duel":link dy$,"auto.c"
;
delay
 for a=1 to 5000:next:return
;
rnd.10z
 a$=rnd$:z=random(999):z=z/100+1:return
;
rnd.100z
 a$=rnd$:z=random(9999):z=(z/100)+1:return
;
zu$
;... input zw=position number, zw$=new value,
 zu$="-"+zu$+"-"
 zx$=left$(zu$,zw):zy$=mid$(zu$,zw+2)
 zu$=zx$+zw$+zy$:zu$=mid$(zu$,2,10)
 return
;
locker
 print \on$"PRIVATE LOCKER"of$
 gosub open.loc
loc.pmt
 input @2 \"P)ut, T)ake L)ook :"i$
 if (i$="") or (i$="Q") gosub clse.loc:goto lnk.shop
 if i$="P" goto put.loc
 if i$="T" goto tak.loc
 if i$="L" goto look
 goto loc.pmt
put.loc
 if zt>9 print \"The locker is full!":goto loc.pmt
 if xi<1 xi=0:print \"No Items!":goto loc.pmt
put.a
 print \"You are carrying:"\
 zr=xi:zs$=xi$:gosub lst.itms
put.b
 input @2 \"Put which item? (?=list):"a$:x=val(a$):if a$="" goto loc.pmt
 if a$="?" goto put.a
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto put.b
 y=(x*4)-3:a=val(mid$(xi$,y)):a$=right$("000"+str$(a),3)+","
 if instr(a$,zw$) print \"There is already one here!":goto put.b
 if a=67 then if mid$(zu$,2,1)="1"print "Can't, you are USEing it!":goto put.b
 if (a=73) or (a=76) print \"You can't put that here!":goto put.b
 l=len(xi$):y=(x*4)-3:zr=xi:zs$=xi$:gosub drp.itm:xi=zr:xi$=zs$
 zt=zt+1:zw$=zw$+a$
 print \"Ok, it is in the locker.":goto loc.pmt

tak.loc
 if xi>(zo-1) print \"You can carry no more Items.":goto loc.pmt
 if zt<1 zt=0:print \"The locker is empty!":goto loc.pmt
tak.a
 print \"The locker now contains:"\
 zr=zt:zs$=zw$:gosub lst.itms
tak.b
 input @2 \"Take which item? (?=list):"a$:x=val(a$):if a$="" goto loc.pmt
 if a$="?" goto tak.a
 if (x<1) or (x>zt) print "Thats not in the locker!":goto tak.b
 y=(x*4)-3:a=val(mid$(zw$,y)):a$=right$("000"+str$(a),3)+","
 if instr(a$,xi$) print \"You already have one!":goto tak.b
 if instr(a$,ai$) print \"Your ally already has one!":goto tak.b
 l=len(zw$):y=(x*4)-3:zr=zt:zs$=zw$:gosub drp.itm:zt=zr:zw$=zs$
 xi=xi+1:xi$=xi$+a$
 print \"Got it!":goto loc.pmt
;
look
 zr=zt:zs$=zw$:print \"The locker contains:"\
 gosub lst.itms:if zr=0 print "Nothing.."
 zr=xi:zs$=xi$:print \"And you are carrying:"\
 gosub lst.itms:if zr=0 print "Nothing.."
 goto loc.pmt
;
open.loc
 dy$=dw$+"items":open #1,dy$
 f$=dx$+"locker":open #2,f$:position #2,84,pn
 input #2,zt\zw$:return
;
clse.loc
 position #2,84,pn
 print #2,zt\zw$:close:return
;
lst.itms
 if zr<1 zr=0:return
 for x=1 to zr
 y=(x*4)-3:a=val(mid$(zs$,y))
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 next:print
 return
;
drp.itm
 zr=zr-1:if zr=0 then zs$="":return
 if y=1 then zs$=mid$(zs$,5):return
 if (y+4)>l then zs$=left$(zs$,y-1):return
 zs$=left$(zs$,y-1)+mid$(zs$,y+4)
 return

dropped
 i$="SPUR.MISC5":dy$=ds$+"spur.logon":link dy$,"quit3"
;
rest
 print \"YOU REST FOR A BIT..":gosub delay
 print \\on$"Y-A-W-N"of$"... (-4 minutes)":gosub delay
 ew=ew-240:if hp<(25+xp) hp=hp+4:print "(hp+4)"
 if ps<15 ps=ps+4:print "Some strength returns    (+4)"
 if ps>20 ps=ps-2:print "You feel a tad hungry    (-2)"
 if pe<15 pe=pe+4:print "Some energy returns      (+4)"
 if pe>20 pe=pe-2:print "You feel a tad thirsty   (-2)"
 if pt<25 pt=pt+2:print "You feel a bit healthier (+2)"
 print \"YOU FEEL RESTED..":goto advent
;
meteor
 if instr("*ME",ys$) return
 if len(ys$)<225 ys$=ys$+"*ME"
 z=info(2):if z=0 z=2
 if z>1 z=100
 i$="FLYING BANSHEE":if cl=6 then if instr("@@",lo$) i$="METEOR"
 print \on$"LOOK OUT!! "i$"!!"of$;hl$\:gosub delay
 i$=". . . . . . ,":gosub met.a
 i$=".,.,.,.,;,;":gosub met.a
 i$=",;,;,+,+;+":gosub met.a
 i$=";+o+o+*o*":gosub met.a
 i$="+*+*+*#*":gosub met.a
 i$="+#*#*#*":gosub met.a
 i$="#*0*#":gosub met.a
 i$="*#0":gosub met.a
 i$="*@":gosub met.a:gosub met.a:gosub met.a
 print \of$"YOU DODGE WILDLY!"
 gosub rnd.100z
 if pd<18 print "(Low dexterity: -10%)":z=z+10
 if pi<18 print "(Low IQ: -5%)":z=z+5
 if pe<18 print "(Low energy: -7%)":z=z+7
 if ps<18 print "(Low strength: -7%)":z=z+7
 gosub delay
 if (z<70) or (hp<4) print \\"Whew... Missed...(+50 ep)"\:ep=ep+50:return
 if hp>3 print \hl$"CRUNCH!! "hp/2" DAMAGE!"of$\:hp=hp/2
 return
met.a
 for a=1 to len(i$)
 print mid$(i$,a,1);:for zp=1 to z:next:print chr$(8);
 next:print " ";:return
;
galad
 if (instr("142",xi$)) or (instr("143",xi$)) goto galad.99
 if (instr("142",ai$)) or (instr("143",ai$)) goto galad.99
 if instr("*GA",ys$) goto galad.99
 print \"A mist forms...";:gosub open.loc:close
 if (instr("142",zw$)) or (instr("143",zw$)) print "...and vanishes...":goto galad.99
 print \
 a=24:gosub messages:gosub delay:input @2\"Your response? [Y]es, N)o :"i$
 if i$="N" print \'"Too bad.."':goto galad.9
 print\'
Her piercing eyes flash, "Ye seem confident! First let me see if Ye are worthy
by asking a simple question...':gosub delay
 zz$=rnd$:z=(random(49)/10)+1:if z>5 z=1
galad.1
 if z=1 a=25:zz$="3"
 if z=2 a=26:zz$="2"
 if z=3 a=27:zz$="1"
 if z=4 a=28:zz$="1"
 if z=5 a=29:zz$="4"
 gosub messages
galad.2
 input @0\"Your answer? [1-4] (?=repeat):"i$
 if i$="?" goto galad.1
 if not instr(i$,"1234") print \"Enter 1 thru 4":goto galad.2
 if i$=zz$ print \'"Correct! Here is thy gift!"':i=143:it$="VIAL OF GALADRIEL" :i1$="M":goto galad.9
 print \"'Sorry, that is not right! Return when Ye are worthy.'"
galad.9
 dy$=dx$+"battle.log":create dy$:open #1,dy$:append #1
 i$="FAILED":if i=143 i$="PASSED"
 print #1, left$(date$,6)yr$" "time$"- TEST"
 print #1, n1$" "i$" THE TEST OF GALADRIEL!"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
galad.99
 if len(ys$)<240 ys$=ys$+"*GA"
 return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):if dr$<>"" ready dr$
 return

al.find
 lu$="":if instr("@@",lo$) return
 if a3 lu$=d3$
 if a2 lu$=d2$
 if a1 lu$=d1$
 if len(ys$)<240 ys$=ys$+"*AF"
 if lu$="" return
 gosub cln.ally
 gosub rnd.100z:z=(z*2)+50:print \qt$"LOOK WHAT I FOUND!"qt$" shouts "lu$\
 gosub delay
 print lu$" hands you a gold sack!"
 g2=z:gosub add.gold
 g1=gh:g2=gl:gosub prt.gold
 print \"("z" gp) You now have "gd$" in Gold."
 gosub delay:print \lu$" swaggers proudly."\
 return
;
add.gold
 gl=gl+g2:if gl=>10000 then gl=gl-10000:gh=gh+1
 return
;
prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
;
chk.god
; "god check", presumably
 if len(ys$)<240 ys$=ys$+"*GC"
 i$="":a$="*"
 if a1>0 if instr(">",d1$) a$=d1$
 if a2>0 if instr(">",d2$) a$=d2$
 if a3>0 if instr(">",d3$) a$=d3$
 if a$="*" return
 lu$=a$:gosub cln.ally
;.. Good god
 if instr("(",a$) i$="GOOD"
;.. Evil god
 if instr(")",a$) i$="EVIL"
 if i$="" return
 if i$="EVIL" goto evil.god
 if vk>1600 gosub gd.beam:goto ck.hlth
 if vk>1200 gosub gd.smile:goto ck.hlth
 if vk<800 goto gd.zap
 if vk<1000 goto gd.frown
 print \lu$" OBSERVES YOU.."
ck.hlth
 if hp+ps+pt+pi+pe+pw+pd>105 return
 i$="HE":if instr("+",a$) i$="SHE"
 print \"'YE LOOK A BIT WEAK,' "i$" SAYS, AND PLACES"
 print "A HAND ON YOUR HEAD.."
 if hp<20 hp=20:print "Hit points, ";
 if ps<20 ps=20:print "Strength, ";
 if pt<20 pt=20:print "health, ";
 if pi<20 pi=20:print "I.Q., ";
 if pe<20 pe=20:print "Energy, ";
 if pw<20 pw=20:print "Wisdom, ";
 if pd<20 pd=20:print "Dexterity, ";
 print "increases.."
 return

evil.god
 if vk<400 goto gd.beam
 if vk<800 goto gd.smile
 if vk>1600 goto gd.zap
 if vk>1200 goto gd.frown
 print \lu$" OBSERVES YOU.."
 return

gd.beam
 print \lu$" BEAMS AT YOU! (Exp +50)":ep=ep+50:return
gd.smile
 print \lu$" GRINS AT YOU, "qt$"KEEP UP THE "i$" WORK, "n1$"!"qt$:return
gd.frown
 print \lu$" FROWNS, "qt$"BETTER WATCH YOUR "i$"NESS THERE, "n1$"!"qt$:return
gd.zap
 print \qt$"YOU ARE NOT "i$" ENOUGH, "n1$"!"qt$
 print lu$" GIVES YOU A BIT OF A "hl$"ZAP"of$" TO ENCOURAGE YOU!"
 gosub rnd.10z:z=z+3:if z+3>hp z=hp-3
 print \"YOU TAKE "z" DAMAGE!":hp=hp-z
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"-REMINDER"
 print #1, lu$" 'INFORMED' "n1$
 print #1, "HE WAS NOT "i$" ENOUGH,"
 print #1, "WITH A SMALL 'ZAP' TO THE POSTERIOR!"
 print #1, "[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 return
;
dead.al
 x=0:lu$="*"
 if a1>0 if a1<8 lu$=d1$:d1$="*":a1=0:x=h1:h1=0:goto dead.al2
 if a2>0 if a2<8 lu$=d2$:d2$="*":a2=0:x=h2:h2=0:goto dead.al2
 if a3>0 if a3<8 lu$=d3$:d3$="*":a3=0:x=h3:h3=0:goto dead.al2
 return
dead.al2
 if lu$="*" return
 i$=lu$:gosub cln.ally
 if not instr(">",i$) a$="The weakened "+lu$+" stumbles and falls!"
 if instr(">",i$) a$=lu$+" looks annoyed, and flies away!"
 print \a$
 gosub delay
 if (a1+a2+a3)<1 then ai=0:ai$=""
 print \\\\lu$" is dead! (wait..)"
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"-LOSS OF FACE!"
 if instr(">",i$) goto god.lv
 print #1, lu$" DIED IN "ww$","
 print #1, "FROM LACK OF NOURISHMENT! WHILE IN"
 print #1, "SERVICE TO "n1$"..."
 goto end.log
god.lv
 print #1, lu$" GREW UNHAPPY WITH "n1$","
 print #1, "AND LEFT!"
end.log
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 if vk>25 vk=vk-25:print "You feel less honorable"
 if pw>5 pw=pw-5:print "You feel foolish"
 if pi>5 pi=pi-5:print "You feel dumb"
fre.ally
 if x=0 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
djinn
 if len(ys$)<245 ys$=ys$+"*VN"
 print \"You think you see the Blue Djinn in the distance!"
 dy$=dx$+"spur.a1$":open #1,dy$
 position #1,64,un
 input #1,g5,g6,g7,g8,g9,g9,g0
 close
 if g7+g8<1 print \qt$"Good day to you "n1$"..."qt$"  [HE VANISHES!]":return
 if len(ys$)<245 ys$=ys$+"*VN"
 dy$=dx$+"thug":open #1,dy$:position #1,50,pn
 print #1,"VINNEY","VINNEY",1,20,0:close
; set thug attack flag:
 zu$=left$(zu$,4)+"1"+mid$(zu$,6)
 return

;
add.log
;.. i$=log message
 open #2,"a:add.log"
 append #2:print #2,"Spur.misc6 []"i$" @"time$:close #2:return
;
cln.ally
 if (instr("\|/",lu$)) or (instr("-}-",lu$)) or (instr("=[]",lu$)) return
 xy$=""
 if instr(">",lu$) xy$="THE GOD ":if instr("+",lu$) xy$="THE GODDESS "
 lu$=xy$+lu$:if instr("|",lu$) lu$=left$(lu$,instr("|",lu$)-1)
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print \"Compiled..":link "k:system.seg"
comp.ck
 print "..ok":return
;

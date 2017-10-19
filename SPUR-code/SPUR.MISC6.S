;.. spur.misc6.s

 public compile

 on nocar goto dropped
 if un=1 print "spur.misc6--";:gosub comp.ck
 free
 if i$="PALINTAR"gosub room.dsp:print\"Palintar returned to pack":goto advent
 if i$="dead.a" goto dead.a
 if i$="dropdead" goto dropdead
 if i$="dead2" goto dead2c
 if i$="RANDOM" gosub random:goto lnk.m.rt
 if i$="LOCKER" goto locker
 if i$="REST" goto rest
 if i$="METEOR" gosub meteor:goto lnk.m.rt
 if i$="galad" gosub galad:goto advent
 i$="Bad value of i$ in spur.misc6! i$="+i$
 print \i$:gosub write.lg
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
 if z<>18 print \"You have not survived..":else print \"You pass thru the portal..."
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
 sn=xn:hp=10:ps=10:pt=10:pi=25:pe=10:pw=25:pd=10:mw=0:mf=0:m$="":wy$=""
 di=6:cr=1:i$="travel3":goto lnk.misc
;
random
 if un<>1 goto no.test
 print "1=Girl       3=Galadriel  5=Find"
 print "2=Enforcer   4=Meteor     6=Ally"
; input @2\"Test: 1=Girl, 2=Enf 3=Galad 4=Meteor 5=Find 6=ally:"i$
 input @2\"Event (0=Random): "i$
 if i$="1" goto girl
 if i$="2" goto enforce
 if i$="3" goto galad
 if i$="4" goto meteor
 if i$="5" goto al.find
 if i$="6" goto dead.al
 print \"Random test"
no.test
 gosub rnd.100z
 if z<15 goto galad
 if z<30 goto meteor
 if z<45 goto dead.al
 if z<60 goto al.find
 if z<80 goto enforce
girl
 if instr("*gi",ys$) return
 if len(ys$)<240 ys$=ys$+"*gi"
 if cl>5 print "A little spacesuit pulls along side, retro-rockets firing."
 if instr("@@",lo$) print "A little boat pulls alongside you.."
 print \'
A little girl  approaches  you. She is quite skinny and very poor looking..
"Oh please, please, kind person.  My grandmother is very sick, and I don't
know what to do! Won't you please give something that I can pawn so I can buy
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
 print "The little girl ";:i$="runs off.."
 if instr("@@",lo$) i$="rows off.."
 if cl>5 i$="fires steering rockets, and leaves.."
 print \i$
 zr=xi:zs$=xi$:gosub drp.itm:xi=zr:xi$=zs$
 return

girl.m1
 a=10:if pc=9 a=15
 if vk>a vk=vk-a
girl.m
 print \"Suddenly, the girl seems to get bigger";
 for a=1 to 10:print "!";:gosub delay:next
 print \\\"'NOW YOU DIE!!'"\\:gosub delay
 m=106:return
girl.sad
 print \"The poor little girl runs away crying.."\
 if pi>3 pi=pi-2:print "(You feel a bit dumber)"
 if pw>4 pw=pw-3:print "(you feel more foolish)"
 return
;
enforce
 ex=clock(1)-ew:if info(2)=1 then if (ev-ex)<300 return
 if ((ev-ex)<180) or (instr("*enf",ys$)) then return
 if len(ys$)<230 ys$=ys$+"*enf"
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
 gosub delay:print \"'I CHALLENGE YOU TO A DUEL!'"\
 zt$=zu$:zv$="autoduel":wx$="random"
 yx$="":hh=0:b=0:wr$="":sx=0:zy$="":zs$=""
 zt=0:zs=0:vy=0:zm=0:vq=0:zq=0:zu=0
 dy$=ds$+"spur.duel":link dy$,"auto.c"
;
delay
 for a=1 to 3000:next:return
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
 print \"PRIVATE LOCKER"
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
 if (x<1) or (x>zt) print "That's not in the locker!":goto tak.b
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

room.dsp
 print \\\"The Palintar glows softly..."\\\
 xy=(pi+pw)*xp
 if pc=2 xy=xy+20
 if pr=3 xy=xy+30
 if pr=4 xy=xy+20
 if pr=9 xy=xy+10
 if xy<240 goto fail
 print \"A soft voice whispers..'You are now in room "cr"'"
 if cl=1 xu=12
 if cl=2 xu=15
 if cl=3 xu=10
 if cl=4 xu=7
 if (cl=5) or (cl=6) xu=20
 print "("nr" rooms total; in rows of "xu")."\

listrm4
 gosub tim.chk:if (ev-ex)<120 print "Dusk approaches..."
 print\"Room("cr"):[1-"nr", M)ap, Q)uit]";:input @2" :"i$
 if i$="M" f$="c:map."+str$(cl):gosub show.file:goto listrm4
 if i$="" or i$="Q" return
 x=val(i$)
 if x<1 print \"Please enter a number from 1-"nr", M or Q":goto listrm4 
 if x>nr print \"1-"nr" rooms only!":goto listrm4
 ready dr$
listrm2
 edit(0)
 input #msg(x),xu$,xu,xv,xy,xz,yw,yx,yy,yz,zt,zs
 if xu$="" goto listrm3
 copy #6,#8
 setint(1)
 print\"Room Number  : "x
 print"Contains     :";:if (xu+xv+xy+xz)>0 then print
 if xu print"Monster- ";:dy$=dw$+"monsters":rl=32:d=xu:gosub rd.file
 if xv print"Item- ";:dy$=dw$+"items":rl=30:d=xv:gosub rd.file
 if xy print"Weapon- ";:dy$=dx$+"weapons":rl=34:d=xy:gosub rd.file
 if xz print"Ration- ";:dy$=dw$+"stores":rl=26:d=xz:gosub rd.file
 if (xu+xv+xy+xz)<1 then print"Nothing"
 print"Openings     :";
 if yw print" North";
 if yx print" South";
 if yy print" West";
 if yz print" East";
 print\\"Room command : ";:if zt=1 print"UP";:else if zt=2 print"DOWN";:else print"NONE";
 if (zt>0) and (zs>0) print" - to #"zs:else if (zt>0) and (zs=0) print" - Shoppe":else print
 gosub rm.name:print"Room Name: "zz$
 print\"Room Description :"\
 copy #8,#0
 print\
listrm3
 if xu$="" print \"[No room here...]"
 goto listrm4

tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto cnf.qt1
 return
cnf.qt1
 mw=0:mf=0:dy$=dz$+"spur.sub":link dy$,"quit"
;
dropped
 i$="SPUR.MISC5":dy$=ds$+"spur.logon":link dy$,"quit3"
;
rm.name
 zz=instr("|",xu$):if instr("\|",xu$) zz=0
 zz$=xu$:if zz zz$=left$(xu$,zz-2)
 if left$(zz$,4)<>"THE " then if left$(zz$,2)<>"A " zz$="THE "+zz$
 return
;
rd.file
 open #1,dy$
 position #1,rl,d
 input #1,cb$\d$\f
 d$=mid$(d$,3)
 close
 if instr("monster",dy$) d$=mid$(d$,2):d=instr("|",d$):if d d$=left$(d$,d-2)
 if instr("weapon",dy$) d$=mid$(d$,2)
 print d$:return
;
show.file
 setint(1):print \s$\
 open #1,f$:if mark(1) close #1:print\"(No file!)":return
showfl2
 copy (20) #1
 if (eof(1) or key(1)) setint(""):close #1:return
 if not flag(35) goto showfl2
 print "Press [RETURN] ";:get i$:if i$=chr$(13) print " ";
 print chr$(8,16);chr$(32,16);chr$(8,16);
 if i$=" " setint(""):close #1:return
 setint(1):goto showfl2
;
fail
 print "A voice whispers, 'Thou are not enlightened enough to use the Great Palintar!'"
 input @2\"View enlightenment status? [Y]/n:"i$
 if i$="N" return
 setint(1):print \'
Required Enlightenment status is 240.
(Intelligence + Wisdom) times player
level = status, subject to following
additions:

 Druid;    plus 20
 Pixie;    plus 30
 Elf;      plus 20
 Half Elf; plus 10':setint("")

 print \"Your current status="xy
 return
;
rest
 print \"YOU REST FOR A BIT..":gosub delay
 print \\"Y-A-W-N... (-4 minutes)":gosub delay
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
 print \"LOOK OUT!! "i$"!!"\:gosub delay
 i$=". . . . . . ,":gosub met.a
 i$=".,.,.,.,;,;":gosub met.a
 i$=",;,;,+,+;+":gosub met.a
 i$=";+o+o+*o*":gosub met.a
 i$="+*+*+*#*":gosub met.a
 i$="+#*#*#*":gosub met.a
 i$="#*0*#":gosub met.a
 i$="*#0":gosub met.a
 i$="*@":gosub met.a:gosub met.a:gosub met.a
 print \"YOU DODGE WILDLY!"
 gosub rnd.100z
 if pd<18 print "(Low dexterity: -10%)":z=z+10
 if pi<18 print "(Low IQ: -5%)":z=z+5
 if pe<18 print "(Low energy: -5%)":z=z+5
 if ps<18 print "(Low strength: -5%)":z=z+5
 gosub delay
 if (z<90) or (hp<3) print \\"Whew... Missed...(+50 ep)"\:ep=ep+50:return
 if hp>2 print \"CRUNCH!! "hp/2" DAMAGE!"\:hp=hp/2
 return
met.a
 for a=1 to len(i$)
 print mid$(i$,a,1);:for zp=1 to z:next:print chr$(8);
 next:print " ";:return
;
galad
 if instr("142",xi$) or instr("143",xi$) or instr("142",ai$) or instr("143",ai$) or (instr("*GAL",ys$)) then goto galad.99
 a=24:gosub messages:gosub delay:input @2\"Your response? [Y]es, N)o :"i$
 if i$="N" print \"'Too bad..'":goto galad.9
 print \'
Her piercing eyes flash, "Ye seem confident! First let me see if ye are worthy
by asking a simple question..':gosub delay
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
 if i$=zz$ print \"'Correct! Here is thy gift!":i=143:it$="VIAL OF GALADRIAL" :i1$="M":goto galad.9
 print \"'Sorry, that is not right! Return when Ye are worthy.'"
galad.9
 dy$=dx$+"battle.log":create dy$:open #1,dy$:append #1
 i$="Fail":if i=143 i$="Pass"
 print #1, left$(date$,6)yr$" "time$"- Test"
 print #1, n1$" "i$"ed the Test Of Galadriel!"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
galad.99
 if instr("*GAL",ys$) return
 if len(ys$)>240 ys$=mid$(ys$,10)
 ys$=ys$+"*GAL":return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):if dr$<>"" ready dr$
 return

al.find
 i$="":if instr("@@",lo$) return
 if a3 i$=d3$
 if a2 i$=d2$
 if a1 i$=d1$
 if (i$="") or (instr("*AYF",ys$)) then return
 gosub rnd.100z:z=(z*2)+50:print \"'Look what I found!' shouts "i$\
 gosub delay
 print i$" hands you a gold sack!"
 g2=z:gosub add.gold
 g1=gh:g2=gl:gosub prt.gold
 print \"("z" gp) You now have "gd$" in Gold."
 if len(ys$)<240 ys$=ys$+"*AYF"
 gosub delay:print \i$" swaggers proudly."\
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
dead.al
 x=0:i$="*"
 if a1>0 if a1<8 i$=d1$:d1$="*":a1=0:x=h1:h1=0:goto dead.al2
 if a2>0 if a2<8 i$=d2$:d2$="*":a2=0:x=h2:h2=0:goto dead.al2
 if a3>0 if a2<8 i$=d3$:d3$="*":a3=0:x=h3:h3=0:goto dead.al2
 return
dead.al2
 if i$="*" return
 print \"The weakened "i$" stumbles and falls!"
 gosub delay
 if (a1+a2+a3)<1 then ai=0:ai$=""
 print \\\\i$" is dead! (wait..)"
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"-LOSS OF FACE!"
 print #1, i$" died in "ww$","
 print #1, "from lack of nourishment while in"
 print #1, "service to "n1$"..."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 if vk>20 vk=vk-20:print "You feel less honorable"
 if pw>5 pw=pw-5:print "You feel foolish"
 if pi>5 pi=pi-5:print "You feel dumb"
fre.ally
 if x=0 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
write.lg
;.. i$=log message
 create "a:add.log":open #2,"a:add.log"
 append #2:print #2,"[Spur.misc6] @ "time$" - "i$:close #2:return
;
compile
 if un=1 print \"Compiled..":link "k:system.seg"
comp.ck
 print "..ok":return
;

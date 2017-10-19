
;... spur.misc2.s
 on nocar goto dropped
 if un=1 print "spur.misc2-";:gosub comp.ck

 public servant
 public compile

 on nocar goto dropped
 if i$="ORDER" goto order
 if i$="PRAY" goto pray
 if i$="AD" gosub AD:goto advent
 if i$="wraith" goto wraith
 if i$="SCHOOL" goto school
 if i$="READ":goto read
 if i$="QUOTE" goto quote
 if (i$="Q") or (i$="QUIT") goto cnf.quit
 print \"Bad value of i$ in spur.misc2! i$="i$:goto advent
;
prt.gold
 if g1<0 g1=0
 if g2<0 g2=0
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
;
advent
 dy$=dz$+"spur.main":link dy$
  
drop.1
 pop
dropped
 i$="SPUR.MISC2":dy$=ds$+"spur.logon":link dy$,"quit3"
; ^ target ok

order
 xu=0:vy=0:xu$="NONE":xv$="":print \"Tactical deployment of servants:"\
 print "1) POINT MAN  : ";:if a1 print d1$", hp = "a1:xv$="1 ":xu=1 :else print xu$
 print "2) FLANK GUARD: ";:if a2 print d2$", hp = "a2:xv$=xv$+"2 ":xu=xu+1:else print xu$
 print "3) REAR GUARD : ";:if a3 print d3$", hp = "a3:xv$=xv$+"3 ":xu=xu+1:else print xu$
 if xu=0 print \"You don't have any servants!":goto advent
 input @2\ "Do you wish to change this? Y/N :"i$
 if i$<>"Y" goto advent
 xv$="(0 "+xv$+")":zt$=xv$
order.a
 print \"New Point man "xv$;:input @0" :"i$
 gosub ordr.ck:if xy>0 goto order.a
 if xz=0 zx$="*":zt=0:yx=0
 if xz=1 zx$=d1$:zt=a1:yx=h1
 if xz=2 zx$=d2$:zt=a2:yx=h2
 if xz=3 zx$=d3$:zt=a3:yx=h3
order.b
 print \"New Flank guard "xv$;:input @0" :"i$
 gosub ordr.ck:if xy>0 goto order.b
 if xz=0 zy$="*":zs=0:yy=0
 if xz=1 zy$=d1$:zs=a1:yy=h1
 if xz=2 zy$=d2$:zs=a2:yy=h2
 if xz=3 zy$=d3$:zs=a3:yy=h3
order.c
 print \"New Rear guard :"xv$;:input @0" :"i$
 gosub ordr.ck:if xy>0 goto order.c
 if xz=0 zz$="*":zr=0:yz=0
 if xz=1 zz$=d1$:zr=a1:yz=h1
 if xz=2 zz$=d2$:zr=a2:yz=h2
 if xz=3 zz$=d3$:zr=a3:yz=h3
 if vy<>xu print \"You didnt deploy ALL your servants!":xv$=zt$::vy=0 :goto order.a
 d1$=zx$:a1=zt:h1=yx
 d2$=zy$:a2=zs:h2=yy
 d3$=zz$:a3=zr:h3=yz
 goto order
ordr.ck
 xy=0:xz=0:if i$="0" return
 if not instr(i$,xv$) xy=1:goto ordr.ck2
 xz=val(i$):if xz=0 xy=1:goto ordr.ck2
 if xz=1 then if a1>0 goto ordr.ck3
 if xz=2 then if a2>0 goto ordr.ck3
 if xz=3 then if a3>0 goto ordr.ck3
 xy=1
ordr.ck2
 print \"Enter "xv$", please..":return
ordr.ck3
 vu=instr(i$,xv$):i$=left$(xv$,vu-1):xx$=mid$(xv$,vu+2)
 xv$=i$+xx$:vy=vy+1:return
;
servant
ally
 on nocar goto dropped
 x=0:zz$=rnd$:a=random(100)
 if a>40 goto ally6
ally2
 dy$=dx$+"allies"
 open #1,dy$
 zz$=rnd$:a=random(ac)
 if a=0 goto ally5
 position #1,26,a
 input #1,cb$\x1$\x1,x2
 if cb$<>"1" gosub sel.ally:if zr=0 goto ally5
 if cb$<>"1" goto ally8
 x1=(x1+x2)/2:x1=random(x1)+5:x2=a
 if a1>0 then if a2>0 then if a3>0 gosub sel.ally:goto ally8
 print \'
In your  concentration on  the  battle, 
you fail to see a figure  watching  the
the fight with  interest. But  now, the 
person comes foward, showing no hostile
action...'
 print \"'My name is "x1$", I have"
 print "been following you for some time"
 print "now, and if you would have me, I"
 input "would like to join you, ok?' :"i$
 x=5:if vk<6 x=0
 if not instr("Y",i$) print \"'Perhaps later..'":vk=vk-x:goto ally4
 x=0
 if a1=0 then d1$=x1$:a1=x1:h1=x2:x=1:goto ally3
 if a2=0 then d2$=x1$:a2=x1:h2=x2:x=2:goto ally3
 if a3=0 then d3$=x1$:a3=x1:h3=x2:x=3:goto ally3
ally3
 if x=0 goto ally5
 print \x1$" bows, 'Thank you! May our journey be pleasant..'"
 position #1,26,a:print #1,0:close
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"- Meeting"
 print #1, x1$" JOINED THE "n1$
 print #1, "PARTY IN "ww$".."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
ally4
 close:goto advent
ally5
 zz$=rnd$:a=random(49)/10+1
 if a<2 print \"There is a soft noise.. somewhere.."
 if a=2 print \"You sense.. something.. somebody.."
 if a=3 print \"What was that? A shuffling noise?"
 if a=4 print \"You sense somebody watching..."
 if a>4 print \"A tingling runs up your spine.."
 goto advent
;
ally6
 if gl<10 goto ally5
 gosub sel.ally:if zr=0 goto ally5
 zz$=rnd$:if random(100)>50 goto ally8
 xu=gl/3:if xu>100 xu=100
 print \"'HEY "n1$"! WHERE IS MY PAY?' asks "zt$
 print "GIVE "xu" GOLD?";:input @2" [Y]/n :"i$:if i$="N" goto ally7
 g3=gh:g4=gl:g1=0:g2=xu:gosub chk.gold
 if a=0 print \"YE DUN'T HAVE ENOUGH GOLD.":goto advent
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 print \zt$" LOOKS PLEASED...":zr=zr+2:if zr>20 zr=20
 if vk<2000 vk=vk+3
 goto ally9
ally7
 zs=3:if pc=9 zs=5
 if vk>zs vk=vk-zs
 zz$=rnd$:zs=random(100):if zs>70 print\zt$" looks grumpy..":zr=zr-3:goto ally9
 zw$="- DISPUTE":zx$=" LEFT "
 if vk<1000 zs=zs-((1000-vk)/50)
 if zs<41 zw$="- [ REVOLT ]":zx$=" ATTACKED ":print \\\"'THEN YOU DIE, CHEAP SKATE!!' SHRIEKS "zt$"!!"\:m$=zt$:ms=10+(xp*3):ma=4:mw=1:md=0:wy$="" :wx$=""
 if left$(m$,4)="THE " m$=mid$(m$,5)
 if zs>40 print \zt$" packs up, and leaves..."
 gosub fre.ally
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$;zw$
 i$=zt$+zx$+n1$+" IN":print #1,i$
 print #1, ww$", OVER GOLD DISPUTE."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 zr=0
ally9
 if zr<1 gosub fre.ally:zt$="*":zr=0:x=0
 if zt<2 d1$=zt$:a1=zr:h1=x
 if zt=2 d2$=zt$:a2=zr:h2=x
 if zt>2 d3$=zt$:a3=zr:h3=x
 if (a1+a2+a3)<1 then ai=0:ai$=""
 goto advent
ally8
 zz$=rnd$:a=(random(99)/10)+4:if a>6 goto ally10
 if zt<2 zz$="'Boy, this point man stuff is dangerous!' mumbles "+d1$
 if zt=2 zz$=d2$+" looks nervously off to the left.."
 if zt>2 zz$="'Hey! How long I gotta stay back here?' shouts "+d3$
 print \zz$+".":goto advent
ally10
 if a=7 print \zt$" stands watch while you search."
 if a=8 print \zt$" watches you pocket the gold."
 if a=9 print \zt$" looks about nervously."
 if a=10 print \zt$" leans up against the wall, waiting."
 if a=11 print \zt$" yawns and scratches."
 if a>11 print \zt$" helps you repack your items."
 goto advent
sel.ally
 zt$="":zr=0:x=0:zz$=rnd$:zt=random(29)/10+1
 if a1>0 then if zt<2 zt$=d1$:zr=a1:x=h1
 if a2>0 then if zt=2 zt$=d2$:zr=a2:x=h2
 if a3>0 then if zt>2 zt$=d3$:zr=a3:x=h3
 return
;
pray
 if un=1 print "ys$="ys$
 print \\\\"Thunder rumbles overhead and a vision appears..."\\\
 for xy=1 to 2500:next
 if instr("*prd",ys$) goto pray.3
 zz=rnd$:xy=random(10)-3
 if vk<800 xy=xy-1:if vk<400 xy=xy-2
 if vk>1200 xy=xy+1:if xy>1600 xy=xy+2
 if pc=2 xy=xy+2:print "(Druid: +20% success)"
 if pc=4 xy=xy+1:print "(Paladin: +10% success)"
 if xy<hp if xy<ps if xy<pe goto pray.1
 x=xf
 if instr("044",xf$) x=x-1
 if instr("045",xf$) x=x-1
 if instr("065",xf$) x=x-1
 if instr("068",xf$) x=x-1
 if xf$="" x=0:xf=0
 if (x>0) then print "'Thou should eateth or drinketh something.":print "Thou must be a tad slow.'":goto advent
 if not instr("*pr1",ys$) goto pray.4
 if (pc=2) or (pc=4) then if not instr("*pr2",ys$) goto pray.4
 if instr("*pr1",ys$) print \"'I have already helped thee today!"\"Buggest me oncest more and thou art toast!'":ys$=ys$+"*prd":goto advent

pray.4
 print "'Oh, very well... here is a little help!'"
 zz$=rnd$:xy=random(5)+6
 if not instr("*pr1",ys$) ys$=ys$+"*pr1":else ys$=ys$+"*pr2"
 if xy>hp hp=hp+10:print "(Your hit points increase.)"
 if xy>ps ps=ps+10:print "(Your hunger lessens.)"
 if xy>pe pe=pe+10:print "(Your thirst lessens.)"
 if xy>pt pt=pt+10:print "(You feel healthier.)"
 print \"'Now runnest thee along.'"
 if (pc=2) or (pc=4) then if not instr("*pr2",ys$) print "(Your kind may pray twice!)"
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 i$="PRAY":if instr("*pr2",ys$) i$="PIOUS "+i$
 print #1, left$(date$,6)yr$" "time$"-"i$
 print #1, "The Spirit of the Dungeons helped"
 print #1, n1$" IN "ww$".."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 goto advent
pray.1
 i$=""
 if hp>7 if ps>7 if pe>7 i$="'Thou art not in need! Dost not buggest me further!'":if vk>1200 i$="'Thou TRULY dost not need my help now.'"
 if i$<>"" print i$:goto advent
 zz$=rnd$:xy=random(11)
 i$="'Canst thou not see i am on lunch break?!'":if vk>1200 i$="'Perhaps after I finish lunch...'"
 if xy>2 i$="'Notest now, I ameth busy!'":if vk>1200 i$="'Perhaps after I finish this task...'"
 if xy>5 i$="'What ameth I? Thou's mama?!'":if vk>1200 i$="'Thou really should try to be self-reliant..'"
 if xy>8 i$="A voice whispers in your ear: 'Namby pamby weenie...'":if vk>1200 i$="'God helps those who help themselves...'"
 if vk<700 i$="'Arggh!! Cooties! Get AWAY!'"
 print \i$:goto advent
pray.3
 print \\\\\\\\'
FOOL!!! Did I not WARN you?!

You vaguely remember something about
"toast" as you are fried with a huge
lightning bolt, and sizzle to a golden
brown...'\\
 xn=sn:sn=0:z=13:hp=0
 i$="dead2":dy$=ds$+"spur.misc6":link dy$
;
show.file
 setint(1):copy f$:setint(""):return
;
sub.gold
 if g2>gl then gl=gl+10000:gh=gh-1
 gl=gl-g2:return
;
prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
;
chk.gold
 a=0
 if g3>g1 then a=1:return
 if (g3=g1) and (g4=>g2) then a=1:return
 return
;
fre.ally
 if x<1 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
AD
 if vv=0 print \"Civys can't Autoduel!":return
 print \"AUTODUEL :";
 if (vv=1) or (vv=3) or (vv=6) or (vv=8) vv=vv+1:print "ON!":return
 vv=vv-1:print "OFF":return
;

read
 if pi<6 print \"Not smart enough to read!":goto advent
 bk=0:print \"These are your books:"\
 dy$=dw$+"items"
 open #1,dy$
 for x=1 to xi
 y=(x*4)-3
 a=val(mid$(xi$,y))
 position #1,30,a
 input #1,cb$\n$
 if left$(n$,1)="B" print right$("   "+str$(x),3)". - "mid$(n$,3):bk=bk+1
 next
 if not bk print \"You have no Books!!":close:goto advent
 input @2 \"Read which Book? "x
 if x=0 close:goto advent
 if (x<1) or (x>xi) print \"You don't have that Book!!":close:goto advent
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #1,30,a,2
 input #1,n$:close
 if left$(n$,1)<>"B" print \"This is NOT a Book!!":goto advent
 if a=69 gosub elev:goto scroll.b
 if a=161 goto house
 if a=162 goto back.house
 bk$=dx$+"spur.books":gosub read.bk
 if not edit(2) print \"This Book cannot be read!"
 if instr("SCROLL",n$) gosub scroll:print \"The scroll catches fire and burns..":goto scroll.b
 print \"The book vanishes in a cloud of smoke!"

scroll.b
 x$=right$("000"+str$(a),3)+",":y=instr(x$,xi$):l=len(xi$)
 if pw<25 pw=pw+1:print \"(You feel wiser..)"
 if xt<60 then xt=xt+1:xt$=xt$+x$:goto drp.itm2
 xt$=mid$(xt$,5)+x$
 goto drp.itm2
;
scroll
 if instr("ANTI-MAGIC",n$) xs=0:xs$=""
 if instr("ENDURANCE",n$) hp=30+xp:if pr=2 hp=hp+2
 if instr("DOORWAYS",n$) goto scroll.a
 return
scroll.a
 if cl=6 print \"YOU ARE OUTSIDE THE RANGE OF THE SCROLLS POWER SOURCE!":return
 input @0\"DOORWAY IN WHICH DIRECTION? "i$
 if not instr(i$,"NSEW") print \"Enter N, S, E or W please.":goto scroll.a
 if i$="N" n=1
 if i$="S" s=1
 if i$="E" e=1
 if i$="W" w=1
 print \"The doorway is opened..":return
;
read.bk
 ready bk$
 input #msg(a),n$ 
 print \n$" reads:"\
 copy #6,#0
 ready dr$:return
;
elev
 i$=rnd$:xu=(random(890)/10)+10:xu$=str$(xu)
 input \"A voice whispers, 'Art thou true of heart?' Y/N:"i$
 i$=rnd$:xu=(random(890)/10)+10:xu$=xu$+"-"+str$(xu)
 input \"'Wilt thou use this information for Good or Evil?' G/E:"i$
 if i$="E" if vk>2 vk=vk-2
 i$=rnd$:xu=(random(890)/10)+10:xu$=xu$+"-"+str$(xu)
 print \"The voice dies away, 'read the paaaaper..'"
 print \"It reads: Your personal combination"\"to the Elevator is: "xu$
 dy$=dx$+"elevator":open #1,dy$
 position #1,pn,10:print #1,xu$:close
 input @2\"Press <CR>"i$:print \"The paper dissapears..":return

drp.itm2
 xi=xi-1:if xi=0 then xi$="":goto drp.itm3
 if y=1 then xi$=mid$(xi$,5):goto drp.itm3
 if (y+4)>l then xi$=left$(xi$,y-1):goto drp.itm3
 xi$=left$(xi$,y-1)+mid$(xi$,y+4) 
drp.itm3
 i$="travel3"
 if instr("MUMMY'S SCROLL",n$) cl=2:cr=7:goto lnk.misc
 if instr("WRAITH'S SCROLL",n$) cl=5:cr=41:goto lnk.misc
 if instr("THE HOUSE",n$) cl=7:cr=1:goto lnk.misc
 if instr("RETURN",n$) cl=1:cr=35:goto lnk.misc
 goto advent
;
wraith
 zw=7:zw$=mid$(zu$,7,1)
 if zw$="0" zw$="1"
 if zw$<>"1" zw$="2"
 gosub zu$:a=7:gosub messages
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"- Wraith Victory"
 print #1, "THE LADY OF THE MIST BECAME PART OF"
 print #1, n1$", AFTER THE DEATH OF"
 print #1, "KING OF THE WRAITHS. (+1 level)"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 if vk<1900 vk=vk+100
 xp=xp+1:cr=390:i$="travel1":goto l.m.misc
;
; feed i$=routine to link back to
l.m.misc
 dy$=dz$+"spur.main":link dy$,"misc"
;
; feed i$=routine to link to
lnk.misc
 dy$=dz$+"spur.misc":link dy$,"misc"
;
lnk.shop
 dy$=dz$+"spur.shop":link dy$,"main1"
;
zu$
;... input zw=position number, zw$=new value,
 zu$="-"+zu$+"-"
 zx$=left$(zu$,zw):zy$=mid$(zu$,zw+2)
 zu$=zx$+zw$+zy$:zu$=mid$(zu$,2,10)
 if zy=1 print "zu$="zu$
 return
;
school
 setint(1):print \'
School:

1) Read manuals (also available in Annex)
2) Change your class (3000 gold)
3) Formal shield training (cost depends on race & class)
Q)uit':setint("")
 input @2 \"Speak! :"i$
 if i$="Q" or i$="" goto lnk.shop
 if i$="1" goto school.1
 if i$="2" goto school.2
 if i$="3" goto school.3
 print \"The master glares! 'I am not playing games here!'":goto school

school.2
 a=8:gosub messages
 input \"Re-train Y/N :"i$:if i$<>"Y" goto school
 g3=gh:g4=gl:g1=0:g2=3000:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto school
schl.2a
 setint(1):print \'
"SPEAK O  honorable  student! Which  is your new calling?"

1) Wizard      4) Paladin  7) Archer
2) Druid       5) Ranger   8) Assassin
3) Fighter     6) Thief    9) Knight':setint("")
 input @2 \"Your Choice (1-9, Q) :"i$:if i$="Q" or i$="" goto school
 zp=val(i$):if (zp>9) or (zp<1) print \"Try again!":goto schl.2a
 i$="278 ,28  ,    ,    ,    ,4   ,235 ,345 ,28  "
 if instr(str$(pr),mid$(i$,zp*5-4,4)) print \"Illegal race/class combo!":goto schl.2a
 pc=zp:gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 a=6:gosub messages
 print \"You are a new person..":if xp>1 xp=xp-1:print "(Lose 1 level)"
 yg=pc:yg=(yg-1)*7+1
 zw$="WIZARD DRUID  FIGHTERPALADINRANGER THIEF  ARCHER ASSASINKNIGHT "
 zx$=mid$(zw$,yg,7):yg=instr(" ",zx$):if yg zx$=left$(zx$,yg-1)
 i$="AND BECAME A "+zx$+"!":gosub school.n:goto lnk.shop

school.1
 print \"Read:":input @2"C)haracters, T)ips, S)pells, Q)uit :"i$ 
 if i$="Q" or i$="" goto school
 if i$="C" f$=dx$+"school":gosub show.file
 if i$="T" f$=dx$+"tips":gosub show.file
 if i$="S" f$=dx$+"school.spells":gosub show.file
 goto school.1

school.3
 if instr(left$(zu$,1),"BC") print\"Ye already HAS shield training":goto school
 i$="900,750,350,300,600,650,800,750,200"
 i$=mid$(i$,pc*4-3,3):zp=val(i$)
 i$="500,700,400,600,500,500,600,600,550"
 i$=mid$(i$,pr*4-3,3):zp=zp+val(i$):zp=(zp*3)/2
 print \"Cost for your Race/Class combo: "zp" gold"
 g3=gh:g4=gl:g1=0:g2=zp:gosub chk.gold
 if a=0 print "Ye do not have enough gold.":goto school
 input "Do Ye wish shield training? Y/N :"i$:if i$<>"Y" goto school
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 a=13:gosub messages
 i$=left$(zu$,1):f$=mid$(zu$,2)
 if i$="A" i$="B"
 if i$<>"B" i$="C"
 zu$=i$+f$:i$="AND RECIEVED FORMAL SHIELD TRAINING":gosub school.n
 goto lnk.shop

school.n
 print \"Writing in news file.."
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$"-SCHOOL"
 print #1, n1$" WENT TO SCHOOL,
 print #1, i$
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close:return
;
ply.locA
 dy$=dw$+"spur.chat"
 open #1,dy$:position #1,64,yx:input #1,zz$:close:if i$="V" goto ply.locB
 if zz$="blank" or zz$="" dy$=zy$+" is silent..":goto ply.loc9
ply.locB
 yx=instr("$",zz$):dy$=zz$:xz=len(zz$)
 if yx>1 then if yx<xz dy$=left$(zz$,yx-1):zz$=mid$(zz$,yx+1):dy$=dy$+n1$+zz$
 if yx=1 dy$=n1$+mid$(zz$,2)
 if yx=xz dy$=left$(zz$,yx-1)+n1$
 zz$=dy$:dy$="'"+zz$+"'"
ply.loc9
 print dy$\:return
;
quote
 on nocar goto dropped
 input @2\"Quote: V)iew W)rite Q)uit :"i$
 if i$="V" print \"VIEW: $ will be replaced by your handle."\:yx=pn:gosub ply.locA :goto quote
 if i$="W" goto quote.1
 if i$="" or i$="Q" goto advent
 goto quote
quote.1
 setint(1):print \'
Enter your quote now, 60 char max. A $  in the  quote  will  be replaced by the
reading players handle (leave a space,  comma, etc, after the $).'
 setint(""):input @2"Enter quote now :" i$
 if len(i$)>60 print "TOO LONG!":goto quote.1
 if i$="" print "No change..":goto quote
 dy$=dx$+"spur.chat":open #1,dy$:position #1,64,pn:print #1,i$:close
 dy$=dw$+"spur.chat":open #1,dy$:position #1,64,pn:print #1,i$:close
 goto quote
;
cnf.quit
 input @0 \"Leave SPUR ? "i$
 if i$<>"Y" goto advent
cnf.qt1
 mw=0:mf=0:dy$=dz$+"spur.sub":link dy$,"quit"
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):if dr$<>"" ready dr$
 return
;
compile
 if un=1 print "ok":link "k:system.seg"
comp.ck
 print "..ok":return
;
;;.ck
 print "..ok":return
;
;
house
 for ii=1 to 1500:next:print \"You don't feel well..."
 print \'THERE IS A HIGH-PITCHED NOISE HERE!'
 gosub paws:print \"A shimmering portal appears!"
 gosub paws:print \"You are being pulled into it...";:
 gosub paws:print "THROUGH IT!"\:gosub paws:gosub crnt.lt
 print "You come out to bright light!":gosub paws
 print "Your body is still in one piece!"\"The portal vanishes!"
 goto drp.itm2
 
crnt.lt
 i=i+1:if i>14 return
 k0$=mid$("AARRGGGHHH!!!!",i,1):for ii=1 to 4
 print k0$;chr$(8);k0$;chr$(8):next:for i=1 to 200:next:print k0$;:goto crnt.lt

paws
 for i=1 to 2000:next:return

back.house
 print \\"The portal appears again!":gosub paws:print \"You go through!"
 gosub paws:print \"YOU SURVIVE!":goto drp.itm2

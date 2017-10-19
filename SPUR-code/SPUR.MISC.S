;spur.misc
;Worked on with Appleworks
;
 public misc
 public compile

misc
 on nocar goto dropped
 if flag(32) print "spur.misc--";:gosub comp.ck
 free
 if i$="thief" goto thief
 if i$="GIVE" vq=1 goto give
 if i$="TAKE" goto take
 if i$="clr.cmps" goto clr.cmps
 if i$="zu$" goto zu$
 if left$(i$,3)="GET" goto get
; p.a3 is dead monster routine
 if i$="p.a3":goto p.a3
 if i$="travel3" goto travel3
 if i$="MALFUNCTION" goto travel4
 if instr("DROP",i$) goto drop
 if i$="dead2" goto lnk.msc6
 i$="Bad value of i$ in spur.misc! i$="+i$
 print \i$:gosub log
advent
 dy$=dz$+"spur.main":link dy$
l.return
 dy$=dz$+"spur.main":link dy$,"return"
s.return
 i$="return":dy$=dz$+"spur.sub":link dy$,"misc"
msc3.ret
 i$="return":dy$=dz$+"spur.misc3":link dy$,"misc"
; feed i$=routine to link back to
l.m.misc
 dy$=dz$+"spur.main":link dy$,"misc"
cmbt.rtn
 dy$=dz$+"spur.combat":link dy$,"return"
lnk.msc6
 dy$=dz$+"spur.misc6":link dy$
;
dropped
 i$="SPUR.MISC"
dropped1
 dy$=ds$+"spur.logon":link dy$,"quit3"
;
fre.ally
 if x=0 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
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
thief
 if instr("@@",lo$) print \"(The thief can't get you here!)":goto l.return
 print \"The Thief shows up,"
 if tm=>mm print "and is scared by the magical":print "aura surrounding you." :goto l.return
 gosub rnd.10z:if (z-1)<xp gosub rnd.10z:if z>4 print "see's who you are, and quickly leaves.." :goto l.return
 if xw>1 zz$=rnd$:x=random(xw):if x=0 then x=xw
 if xw=1 x=1
 dy$=dx$+"weapons":open #1,dy$:gosub drp.wpn
 print "knocks  you down, and vanishes!!"
 print "As you gather your weapons, you see one missing!"
 goto l.return
;
take
 if (a1+a2+a3)<1 print \"You don't have any allys to take from!":goto advent
 dy$=dw$+"items":open #1,dy$
take.a
 if ai<1 ai=0:print \"Your ally(s) arn't carrying anything!":close:goto advent
 print \"You ally(s) now carry:"\
 for x=1 to ai
 y=(x*4)-3:a=val(mid$(ai$,y))
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 next:print
;
take.b
 if xi>(zo-1) print \"You can carry no more Items.":close:goto advent
 input @2\"Take which item (?=list):"a$:x=val(a$):if a$="" close:goto advent
 if a$="?" goto take.a
 if (x<1) or (x>ai) print "They don't carry that!!":goto take.b
 y=(x*4)-3:a=val(mid$(ai$,y))
 position #1,30,a,2:input #1,n$:l=len(ai$):y=(x*4)-3
tak.itm
 print \"Got it.."
 xi=xi+1:a$=right$("000"+str$(a),3)+",":xi$=xi$+a$
 ai=ai-1:if ai=0 then ai$="":goto take.b
 if y=1 then ai$=mid$(ai$,5):goto take.b
 if (y+4)>l then ai$=left$(ai$,y-1):goto take.b
 ai$=left$(ai$,y-1)+mid$(ai$,y+4)
 goto take.b
;
give
 if (a1+a2+a3)<1 print \"You don't have any allys to give to!":goto advent
 ai=len(ai$)/4
 if ai>7 print \"Your ally(s) can carry no more!":goto advent
 vq=1:goto drop.itm
drop
 input @2\"Drop? I)tem, W)eapon R)ation :"i$
 if i$="I" vq=0:goto drop.itm
 if i$="W" goto drop.wpn
 if i$="R" gosub drop.fd:goto advent
 if i$="" or i$="Q" goto advent
 goto drop

drop.itm
 dy$=dw$+"items":open #1,dy$
drop.a
 if xi<1 xi=0:print \"No Items!":close:goto advent
 print \"You are carrying:"\
 for x=1 to xi
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 next:print
drop.b
 if vq=1 then if ai>7 print\"Your ally(s) can carry no more!":close:goto advent
 zz$="Drop ":if vq=1 zz$="Give "
 print \zz$;
 input @2 "which item? (?=list):"a$:x=val(a$):if a$="" close:goto advent
 if a$="?" goto drop.a
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto drop.b
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #1,30,a,2:input #1,n$
 if (vq=0) and (a=76) then zt=3:zw=8:zw$="0":gosub zu$
 dy$="Can't, you are USEing it!"
 if a=67 then if mid$(zu$,2,1)="1" print dy$:goto drop.b
 if a=1 then if cp=1 print dy$:goto drop.b
 if vq=1 then if a=73 print \"Your ally refuses to hold it!":goto drop.b
 if a=73 print \"(You feel more normal..)"
 l=len(xi$):y=(x*4)-3:gosub drp.itm:goto drop.b

drp.itm
 if vq=0 print \"Dropped...":else print \"Your ally now has it.."
drp.itm2
 if vq=1 ai=ai+1:a$=right$("000"+str$(a),3)+",": ai$=ai$+a$
 xi=xi-1:if xi=0 then xi$="":goto drp.itm3
 if y=1 then xi$=mid$(xi$,5):goto drp.itm3
 if (y+4)>l then xi$=left$(xi$,y-1):goto drp.itm3
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
drp.itm3
 if a=145 goto broom
 return

broom
 if not mw return
 if (cl<>6) or (cr<>582) then return
 if (instr("144",xi$)) or (instr("144",ai$)) return
 i=144:it$="RUBY SLIPPERS":i1$="T":a=22:goto message

clr.cmps
 vq=0:x$="001,":y=instr(x$,xi$):l=len(xi$)
 if y=0 goto advent
 gosub drp.itm:goto advent

drop.wpn
 print \"You are carrying:"\
 dy$=dx$+"weapons"
 open #1,dy$

 if xw=0 print "No Weapons!!":close:goto advent
 for x=1 to xw
 y=(x*4)-3
 a=val(mid$(xw$,y))
 position #1,34,a,2
 input #1,n$
 print right$("   "+str$(x),4)". - "mid$(n$,4)
 next:print

 input @2\"Which weapon number? "a$:x=val(a$):if a$="" close:goto advent
 if (x<1) or (x>xw) print "You're NOT carrying that!!":close:goto advent
 print \"Weapon dropped...":gosub drp.wpn:goto advent

drp.wpn
 l=len(xw$)
 y=(x*4)-3:a=val(mid$(xw$,y))
 xw=xw-1:if xw=0 then xw$="":goto drp.wpn2
 if y=1 then xw$=mid$(xw$,5):goto drp.wpn2
 if (y+4)>l then xw$=left$(xw$,y-1):goto drp.wpn2
 xw$=left$(xw$,y-1)+mid$(xw$,y+4)
drp.wpn2
 cb$="2":if a>10 then cb$="1"
 position #1,34,a
 print #1,cb$
 close:wr$="":return
;
rnd.10z
 a$=rnd$:z=random(999):z=z/100+1:return
;
zu$
;... input zw=position number, zw$=new value,
;... zt=calling program:1=main, 2=sub, 3=misc(gosub), 4=misc3, 5=combat
 zu$="-"+zu$+"-"
 zx$=left$(zu$,zw):zy$=mid$(zu$,zw+2)
 zu$=zx$+zw$+zy$:zu$=mid$(zu$,2,10)
 if zt=1 goto l.return
 if zt=2 goto s.return
 if zt=4 goto msc3.ret
 if zt=5 goto cmbt.rtn
 return
;
get
 zm=instr("|",it$):if zm>0 it$=left$(it$,zm-1)
 if i$="GET" i$="GET ALL"
 i$=mid$(i$,5):zz$=""
 if i$<>"ALL" gosub get.b goto advent
 zt$="$":if wp$+it$+fd$="" then if mw+md=0 zt$=""
 if wp$<>"" i$=wp$:gosub get.c
 if it$<>"" i$=it$:gosub get.c
 if mw+md+mf>0 then i$=m$:gosub get.c
 if fd$<>"" i$=fd$:gosub get.c
 if instr("#",wy$) i$="STATUE":gosub get.c
 wx$="*":gosub get.plyr
 if zt$="" if cl=3 if cr=3 print \"THE ROCK IS TOO LARGE!":goto advent
 if zt$="" print \"THERE IS NOTHING HERE!"
 goto advent
get.c
 if md=2 then if i$=m$ i$=i$+" TRACKS"
 print \"GETTING "i$".."
get.b
 if i$=m$ goto get.mon
 if md=2 then if instr(m$,i$) print "YOU HEAR LAUGHTER AS YOU TRY TO GET THE "i$:return
 if instr("STATUE",i$) then if instr("#",wy$) print "THE STATUE IS MUCH TOO HEAVY!":return
 if (i$=it$) or (i$=fd$) then if instr("073",xi$) print "IT IS TURNED TO GOLD!":zz$="midas":if hp>5 print "(You feel drained..)":hp=hp-2:if pt>5 pt=pt-1
 if i$=wp$ goto get.wpn
 if i$=it$ goto get.itm
 if i$=fd$ goto get.fd
 wx$=i$:zt$="":gosub get.plyr:if zt$<>"" return
 if cl=3 if cr=3 if instr("STONE",i$) print \"THE ROCK IS TOO LARGE!":return
 print \i$" is NOT here."\"('GET' gets all..)":return

strange
 print \"ARGG!! It is booby trapped! It blows up!"\\\\\\\"BOOOMM!!"
 goto hp.5
pandora
 print \"FOOL!! YOU SHOULD NOT DO THAT!!":print \"STRANGE SMOKE BILLOWS OUT!"
 if ep>100 print \"You loose "ep-100" experience!":ep=100
 if pt>5 print "Your constitution is reduced to 5!":pt=5
hp.5
 if pi>5 pi=pi-5 print "You feel dumber!"
 if hp>5 print "You take "hp-5" damage!":hp=5
 return
;
get.mon
 if mw print m$" WON'T LET YOU!":if instr("HORSE",m$) print "(Try using a lasso)"
 if mw return
 if not instr("MEAT",fd$) if md=1 print "THE "m$" IS TOO MESSED UP TO GET!" :return
 if md=1 print "YOU HACK UP THE "m$" INTO "m$" STEAKS.."
 return

get.wpn
 if wt$="C" then d$=wp$:d=wv:goto cursed
 if pd<8 print "(Dexterity too low)"
 if (xw>(zo-5)) or (pd<8) print \"You can carry no more Weapons.":close:return
 if wp=17 goto excalibur
excal.r
 xw=xw+1:a$=right$("000"+str$(wp),3)+",":xw$=xw$+a$
 close
 dy$=dx$+"weapons"
 open #1,dy$
 position #1,34,wp
 print #1,"0"
 close:wp=0:wp$="":i$="it":goto gotit

excalibur
 if vk<1200 if pc=9 print \"A VOICE BOOMS, 'THOU ARE NOT WORTHY!'";
 if (pc<>9) or (vk<1200) print \"YOU CAN NOT PULL THE SWORD OUT!":close:return
 print \"THE SWORD SLIDES OUT OF THE STONE!"
 dy$=dx$+"battle.log":create dy$:open #2,"battle.log":append #2
 print #2, left$(date$,6)yr$" "time$"- EXCALIBUR!"
 print #2, n1$" PULLED EXCALIBUR"
 print #2, "OUT OF THE STONE!!"
 print #2,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close #2
 goto excal.r

get.itm
 if i=41 goto rose
 if (i=70) or (i=72) goto strange
 if i=71 goto pandora
 if i=81 print \"You can only USE this..":return
 if i=139 print \"The "it$" is MUCH large to get!":return
 if i1$="C" then d$=it$:d=iv:goto cursed
 if zz$="midas" a=random(30)+10:goto get.itm4
 if i=86 gosub treasure
 if instr("COIN",it$) a=random(20)+1:goto get.itm4
 if instr("DIAMOND",it$) a=random(30)+1:goto get.itm4
 if instr("GOLD",it$) a=random(15)+1:goto get.itm4
 if instr("SILVER",it$) a=random(10)+1:goto get.itm4
 if instr("JEWEL",it$) a=random(8)+1:goto get.itm4
 if pt<9 print \"You are too sickly to carry it!":return
 if xi>(zo-1) print \"You can carry no more Items.":return
 xi=xi+1:a$=right$("000"+str$(i),3)+",":xi$=xi$+a$
 if i=73 print \"You feel funny.."
 i$="it":if right$(it$,1)="S" i$="'em"
 print \"Got "i$"..":goto get.itm5

rose
 i$=rnd$:a=random(16)+12:if a<pd print \'
Whew! You are dextrous enough to avoid the poisoned stickers!':a=80:goto get.itm4
 if gm=1 print \"GOD MODE protects you from the poison.":a=80:goto get.itm4
 print \"Akk! You prick your finger!":print \"Poison!!":if hp>5 hp=hp-5
 zw=3:zw$="1":zt=3:gosub zu$:a=80:goto get.itm4

treasure
 zz$=mid$(zu$,9,1):if zz$="2" return
 if zz$="1" a=1000:pop:print \\"BINGO! SUCH WEALTH!!"\:zw=9:zw$="2":zt=3:gosub zu$:goto get.itm4
 print \"(Ain't you heard of the Mummy's curse?!?!)"\:pop:goto pandora

get.itm4
 g2=iv*a:gosub add.gold
 g1=gh:g2=gl:gosub prt.gold
 print \\"("iv*a" gp) You now have "gd$" in Gold."
 if zz$="midas food" goto get.fd1
get.itm5
 a$=right$("000"+str$(i),3)+","
 i=0:it$=""
 if xt<60 then xt=xt+1:xt$=xt$+a$:return
 xt$=mid$(xt$,5)+a$:return

get.fd
 if (instr("FOUNTAIN",fd$)) or (instr("POOL",fd$)) print \"You can only DRINK this.":return
 if zz$="midas" a=random(30)+10:iv=1:zz$="midas food":goto get.itm4
 if ft$="C" then d$=fd$:d=sv:goto cursed
 if (xf>(zo-1)) print \"No room left in your pack.":return
 xf=xf+1:a$=right$("000"+str$(fd),3)+",":xf$=xf$+a$
get.fd1
 i$="it":if right$(fd$,1)="S" i$="'em"
 fd=0:fd$=""
 if xo<20 then xo=xo+1:xo$=xo$+a$:goto gotit
 xo$=mid$(xo$,5)+a$

gotit
 print "Got "i$".."
 return

cursed
 if d=0 then d=10
 print \d$" is Cursed!":a=random(d):d=d-a:pi=pi-a:hp=hp-d
 if hp<=0 if gm=1 hp=1: print "GOD MODE saves you from dying."
 if hp<=0 then pop:xn=sn:sn=0:z=3:i$="dead2":goto lnk.msc6
 print xv$"dumber..)":if pi<0 then pi=0
 print "(Try examining things first!)"
 return
;
get.plyr
 free:tg$=ta$:gosub ply.locD
 if cl=1 then if tf$<>">:" tg$=tf$:gosub ply.locD
 if zt$="*" print "'BACK OFF WEIRDO!'"
 wx$="":return

ply.locD
 vs=cl:vx=cr
 zw$="":zx$=":"+str$(cr)+"=":yz=len(zx$)
 gosub ply.loc8
 yy=instr(zx$,zw$):if not yy return
ply.loc1
 yw=yz+yy:xz=0
ply.loc2
 xz=xz+1:if mid$(zw$,xz+yw,1)=":" goto ply.loc3
 if xz+yw>(len(zw$)) return
 goto ply.loc2
ply.loc3
; zy$=name
 zy$=mid$(zw$,yw+1,xz-1)
 zz$=mid$(zw$,yw,1):yx=val(zz$)
 a$=" SKUTTLES OUT OF REACH!"
 if yx<1 then if zz$<>"0" a$=" WON'T FIT IN YOUR SACK.."
 if (wx$="*")or(wx$=zy$) then print zy$;a$:zt$="*":if left$(a$,2)=" W" zt$="="
 zw$=mid$(zw$,yw+1):yy=instr(zx$,zw$):if yy goto ply.loc1
 return
ply.loc8
 if cl=1 zw$=tg$
 if cl=2 zw$=tb$
 if cl=3 zw$=tc$
 if cl=4 zw$=td$
 if cl=5 zw$=te$
 if cl=6 zw$=th$
 return
;
p.a3
 mf=0:mw=0:if vp<99 vp=vp+1
 if m$<>"THE DWARF" goto p.a4
 g1=dh:g2=dl:gosub prt.gold
 print \"UPON KILLING "m$", YOU CLAIM HIS TREASURE OF "gd$" GOLD!"
 gosub add.gold:gh=gh+g1:df=0:dh=0:dl=500: m$="DWARF"
 goto advent

p.a4
 if m=70 print \"A SHADOW FLIES AWAY!"
 i$="ES ":if right$(m$,1)="S" i$=" "
 if instr("<",wy$) print \m$" TWITCH"i$"STRANGELY!"
 gosub set.pa
 a=pa:b=ma:gosub set.prob
 if x1=0 then x=5-p1:else x=(6-p1)/2
 if (hp+x)<26 then hp=hp+x
 a=wa:b=ma:gosub set.prob
 if (instr("X",wy$)) or (instr(":",wy$)) then goto no.gold
 zz$=rnd$:g2=p1*25:g2=g2+random(50)+10
 if instr(">",wy$) g2=g2*2:if instr(">>",wy$) g2=g2*2
 print \"YOU FIND "g2" GOLD PIECES ON "m$"!"
 gosub add.gold
no.gold
 if not instr(":",wy$) goto no.robot
 gosub rnd.10z:if z>5 print \"No salvagable parts":goto no.salvg
 if i=0 i=146:it$="SALVAGE PARTS":i1$="T"
no.salvg
 if wa<>10 goto no.robot
 gosub rnd.10z
 if z>4 print \"The power pak on "m$" was destroyed..":goto no.robot
 print \"The power pak on "m$" is still energized!"\"Recharge your "wr$;
 input @2"? [Y]/n:"i$
 if i$<>"N" gosub delay.a:print \\hl$"ZZZZTTT"of$\:gosub delay.a:vn=vl
no.robot
 if m=120 a=17:gosub message
 gosub rec.ammo:i$="A SEARCH REVEALS A SECRET HOLE, "
 if instr("->",lo$) print \i$"EAST!":e=1
 if instr("<-",lo$) print \i$"WEST!":w=1
 if left$(m$,4)="THE " m$=mid$(m$,5)
 if val(left$(m$,1))>0 m$=mid$(m$,3)
 dy$=dz$+"spur.misc2":zn=m:if m=93 i$="wraith":link dy$
 if not instr("@@",lo$) gosub rnd.10z:if z>5 link dy$,"servant"
 goto advent
;
rec.ammo
 if (instr("STORM",wr$)) or (wa<>8) or (zm<3) then return
 if not instr("BOW",wr$) then if not instr("SLING",wr$) then if not instr("BLOWGUN",wr$) return
 if zm<2 return
 a$=rnd$:z=random(zm)+1:if z>zm z=zm
 print \"YOU RECOVER "z" AMMO ROUNDS."\
 vn=vn+z:if vn>vl vn=vl
 return
;
set.prob
 if a>b then p1=a-b:else p1=b-a
 if p1>5 then p1=10-p1
 p2=p1*2:p2=10-p2+(p1=0)
 return
;
set.pa
 pa=ps+pd+pt+pi+pw+pe
 pa=pa/16:if pa>9 pa=9
 if pa<6 print "(You feel poorly)"
 return
;
travel3
 if (cl=1) and (cr=89) then a=18:gosub message:cl=5:cr=41:goto travel4
 if di<>6 goto no.shop
 if (cl=6) and (instr("FR",lo$)) then cr=584
 if (cr=1) and (cl=6) then dy$=ds$+"spur.ship":mf=0:cr=792:link dy$
 if ((cr=584) and (cl=6)) or (cr=1) then dy$=dz$+"spur.shop":mf=0:cr=0:link dy$
no.shop
 if (cl=6) and (di=5) then mf=0:i$="WIN":dy$=dz$+"spur.misc7":link dy$
 if di=5 cl=cl-1:cr=rt
 if di=6 cl=cl+1:cr=rt
travel4
 f$=dx$+"d.level"+str$(cl):open #1,f$
 input #1,ln$,nr,ri:close #1
 if (not nr) i$="Undefined level! f$="+f$:print \i$:gosub log:cl=1:cr=1 :di=6:goto travel3
 print \"YOU HAVE ENTERED "ln$"!":i$="room.level"+str$(cl)
 du$=dw$:dy$=dw$+i$:open #1,dy$:a=mark(1):close:if a du$=dx$
 dr$=du$+i$:ready dr$
 if i$<>"MALFUNCTION" i$="travel1":if di=7 i$="travel2"
 goto l.m.misc
;
drop.fd
 if flag(32) print "xf$="xf$
 gosub pr.food:if xf=0 return
drop.fd2
 input @2\"Drop which ration Item? "a$:if a$="" return
 x=val(a$):if (x<1) or (x>xf) print \"You don't have that item.":goto drop.fd2
 y=(x*4)-3:a$=mid$(xf$,y,3)
 if flag(32) print "a$="a$
 print \"Dropped"\
 if a$="016" gosub d.sugar
 xf=xf-1:if xf=0 then xf$="":return
 l=len(xf$):if y=1 then xf$=mid$(xf$,5):return
 if (y+4)>l then xf$=left$(xf$,y-1):return
 xf$=left$(xf$,y-1)+mid$(xf$,y+4):return

d.sugar
 if not instr("GRASSY",ww$) print "Dropping here does no good":return
 a$=rnd$:if random(100)>50 print "Hmpth.. nothing..":return
 print hl$"A horse gallops up to gobble down the sugar!"of$
 m=134:m$="THE HORSE":wy$="AC":ma=3:ms=10:zq=1:mw=1
 return
;
pr.food
 if xf=0 print \"No Rations."\:return
 dy$=dw$+"stores"
 open #1,dy$
 print:for x=1 to xf
 y=(x*4)-3:a=val(mid$(xf$,y))
 position #1,26,a,2
 input #1,n$
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xf
 next:close:return
;
delay.a
 for a=1 to 4000: next:return
;
log
 open #1,"c:spur.log":append #1:print #1,i$:close:return
;
message
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):if dr$<>"" ready dr$
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print \"Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return
;

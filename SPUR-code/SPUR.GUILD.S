;.... spur.guild.s

 on nocar goto dropped
 public compile
 if info(5) print \"spur.guild--";:gosub comp.ck

 if yx$="*ANNEX*" print \"VISITOR ACCESS, DON'T GIVE OR TAKE ANYTHING!!"

 zm=0:yz=1
 if instr("\|/",ww$) xu$="Mark of the Claw":zy$="CLAW."
 if instr("-}--",ww$) xu$="Mark of the Sword":zy$="SWORD"
 if instr("=[]",ww$) xu$="Iron Fist":zy$="FIST."
 if (vv=6) or (vv=7) or (info(5)) then if instr("\|/",ww$) zm=1:yz=28
 if (vv=3) or (vv=4) or (info(5)) then if instr("-}--",ww$) zm=2:yz=27
 if (vv=8) or (vv=9) or (info(5)) then if instr("=[]",ww$) zm=3:yz=29
 if (zm=0) print\"A gruff guard informs you that you  are not a member of the "xu$\"and politely throws you out..":goto advent
 if flag(yz)=0 then if not info(5) print \"A guard politely informs you that the Guildmaster has not yet given you"\"access. 'Sorry, try again later..'":goto advent
 if mw print \"The guards prevent "m$" from following you in.."

 setint(1):print \"Lurch the butler meets you at the door. 'Greetings "n1$"! Welcome"\"to The "xu$".' He hands you a warmed brandy and leads you inside."
 if pe<15 pe=pe+4:print "(Energy: +4)"
 if flag(25) print \"'Always honored to welcome the GM Of The "zy$"!'"
 setint(""):dy$=dx$+"guild":open #2,dy$

menu.a
 gosub tim.chk:if (ev-ex)<120 print "Dusk approaches..."
 yz=ev-ex
 i$=str$(yz-((yz/60)*60)):i$=right$("00"+i$,2)
 zz$="["+str$(yz/60)+":"+i$+"] "+xu$
 print \zz$": C,F,I,B,V,W,Q,?";:input @2":"i$
 if i$="C" goto chalk.bd
 if i$="F" goto food
 if i$="I" goto item
 if i$="B" print \"Lurch takes you to the treasury.":gosub read.gld:goto bank
 if i$="V" print \"Lurch shows you the Guild Log..":goto show.lg
 if i$="W" print \"You open up the weapon box.":goto weapon
 if i$="Q" or i$="" goto advent
 if i$<>"?" print\"Lurch snickers..":goto menu.a
 print \'
C=Chalk board, where you may read/write a one line message.
F=Food locker, where you may deposite or take food items.
I=Item locker, where you may deposite or take items.
B=Bank, where you may deposit or take gold.
V=View the Guild transaction log.
W=Weapons box.'
 print "Q=Leave The "xu$
 goto menu.a

;
show.file
 setint(1):print \s$\:copy f$:setint(""):return
;
bank
 print \"R)eview P)ay T)ake":Input @2 "-> "i$
 if i$="" or i$="Q" gosub writ.gld:goto menu.a
 if i$="R" goto review
 if i$="P" goto pay
 if i$="T" goto withdraw
 print \"Lurch looks bored..":goto bank

review
 gosub rev.b:gosub rev.c:goto bank
rev.b
 g1=g5:g2=g6:gosub v.prt.g:print \"In Guild :"gd$" gold":return
rev.c
 g1=gh:g2=gl:gosub v.prt.g:print \"In sack  :"gd$" gold":return

pay
 if g5>9 print \"Sorry, the treasary is full!":goto bank
 gosub rev.c
 input @2 \"Give to Guild fund->"gd$
 if (gd$="") or (gd$="Q") print \"Lurch rolls his eyes...":goto bank
 gosub v.val.g:if a=0 print \"Lurch stares at the wall..":goto bank
 gosub v.spl.g:g3=gh:g4=gl:gosub v.chk.g:if a=0 print \"You don't have that much!":goto bank
 gosub v.put.g:vu=0
 print \"Lurch thanks you.":zx$="GAVE":zw$=gd$+" GOLD":gosub add.lg
 vw=(val(gd$)/100):if vk<(2000-vw) vk=vk+vw
 i$="Put "+zw$+" in treasury. vw="+str$(vw):gosub sys.log
 goto review
;
withdraw
 gosub rev.b
 input @2 \"Take - How much? "gd$
 if (gd$="") or (gd$="Q") goto bank
 gosub v.val.g:if a=0 print \"Lurch smiles..":goto bank
 gosub v.spl.g:g3=g5:g4=g6:gosub v.chk.g:if a=0 print \"We don't have that much!":goto bank
 gosub v.tak.g:print \"Lurch hands it to you."
 vw=(val(gd$)/100)+1:if vk>vw vk=vk-vw
 zx$="TOOK":zw$=gd$+" GOLD":gosub add.lg
 i$="Took "+zw$+" from treasury. vw="+str$(vw):gosub sys.log
 goto review
;
read.gld
 position #2,256,zm
 input #2,g5,g6
 return
;
writ.gld
 position #2,256,zm
 print #2,g5,g6
 return
;
;.. take gold from players hands and put in Guild
v.put.g
 g5=g5+g1
 g6=g6+g2:if g6=>10000 then g6=g6-10000:g5=g5+1
 if g2>gl then gl=gl+10000:gh=gh-1
 gh=gh-g1:if gh<1 gh=0
 gl=gl-g2:if gl<1 gl=0
 return

;.. take from account
v.tak.g
 if g2>g6 then g6=g6+10000:g5=g5-1
 g5=g5-g1:g6=g6-g2
 gh=gh+g1
 gl=gl+g2:if gl=>10000 then gl=gl-10000:gh=gh+1
 return

;.. returns gd$ for printout of gold
v.prt.g
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return

;.. returns g1 and g2 from gd$
v.spl.g
 gd$=right$("00000000"+gd$,9)
 g1=val(left$(gd$,5)):g2=val(right$(gd$,4))
 return

;.. compares g3 to g1 and g4 to g2 to see g3 & g4 are at least as large
v.chk.g
 a=0
 if g3>g1 then a=1:return
 if (g3=g1) and (g4=>g2) then a=1:return
 return

v.val.g
 l=len(gd$)
 for i=1 to l:a=instr(mid$(gd$,i,1),"0123456789")
 if (not a) then i=l:next:return
 next:return
;
;
tim.chk
 if yx$="*ANNEX*" return
 ex=clock(1)-ew:if ex=>ev pop:goto cnf.qt1
 return
cnf.qt1
 close:mw=0:mf=0:dy$=dz$+"spur.sub":link dy$,"quit"
;
advent
 close:i=0:zv$="":i$="guild":vs=cl:vx=cr:dc$="?"
 print \"You return to the street.."
 if yx$="*ANNEX*" yx$="" dy$=ds$+"spur.annex":link dy$
 dy$=dz$+"spur.main":link dy$
;
dropped
 close
 dy$=ds$+"spur.logon"
 link dy$,"quit3"
;
item
 print \"Lurch shows you to the Items room.."
item.a
 input @2\"G)ive or T)ake item? :"i$ 
 if i$="G" goto give
 if (i$="") or (i$="Q") goto menu.a
 if i$<>"T" goto item.a

take
 if xi>(zo-1) print \"You can carry no more Items.":goto item.a
 position #2,256,zm,32:input #2,xv\xv$
 if xv<1 print \"The Guild doesn't have anything!":goto item.a
 dy$=dw$+"items"
 open #1,dy$
take.b
 print \"The Guild now has:"\
 for x=1 to xv
 y=(x*4)-3:a=val(mid$(xv$,y))
 position #1,30,a,2
 input #1,n$:zz=instr("|",n$):if zz>0 n$=left$(n$,zz-1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 next:print

take.a
 input @2\"Take which item number? "a$:x=val(a$)
 if (a$="") or (a$="Q") close #1:goto item.a
 if a$="?" goto take.b
 if (x<1) or (x>xv) print "We don't have that!!":goto take.a
 y=(x*4)-3:a=val(mid$(xv$,y))
 a$=right$("000"+str$(a),3)+","
 if instr(a$,xi$) print \"You already carry that!":goto take.a
 if instr(a$,ai$) print \"Your ally already has one!":goto take.a
 position #1,30,a,2
 input #1,n$:zz=instr("|",n$):if zz>0 n$=left$(n$,zz-1)
 l=len(xv$):y=(x*4)-3
 
tak.itm
 close #1
 zw$=mid$(n$,3)
 if vk>3 vk=vk-3
 print \"Lurch hands you the "zw$:zx$="TOOK":gosub add.lg
 xi=xi+1:a$=right$("000"+str$(a),3)+",":xi$=xi$+a$
 xv=xv-1:if xv=0 then xv$="":goto tak.a
 if y=1 then xv$=mid$(xv$,5):goto tak.a
 if (y+4)>l then xv$=left$(xv$,y-1):goto tak.a
 xv$=left$(xv$,y-1)+mid$(xv$,y+4)
tak.a
 position #2,256,zm,32:print #2,xv\xv$
 goto item.a
;
give
 position #2,256,zm,32:input #2,xv\xv$
 if xv>4 print \"There is no more room!":goto item.a
stop
drop.itm
 if xi=0 print \"'Alas, you have no Items!'":goto item.a
 dy$=dw$+"items"
 open #1,dy$
drp.b
 print \"You are carrying:"\
 for x=1 to xi
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #1,30,a,2
 input #1,n$:zz=instr("|",n$):if zz>0 n$=left$(n$,zz-1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 next:print

drp.a
 input @2 \"Give which item number? "a$:x=val(a$)
 if (a$="") or (a$="Q") close #1:goto item.a
 if a$="?" goto drp.b
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto drp.a
 y=(x*4)-3:a=val(mid$(xi$,y)):a$=right$("000"+str$(a),3)+","
 if a=67 then if mid$(zu$,2,1)="1" print\"Can't, you are USEing it!":goto drp.a
 i$="067,073,074,076,097,080,082,096,097,122,123,124,131,132,"
 i$=i$+"133,134,135,138,140,142,143,144,145,"
 if instr(a$,i$) print \"Lurch isn't allowed to take it!":goto drp.a
 position #1,30,a,2
 input #1,n$:zz=instr("|",n$):if zz>0 n$=left$(n$,zz-1)
 l=len(xi$):y=(x*4)-3

drp.itm
 close #1
 if vk<2000 vk=vk+3
 print \"Lurch thanks you..":zw$=mid$(n$,3):zx$="GAVE":gosub add.lg
 
drp.itm2
 xv=xv+1:a$=right$("000"+str$(a),3)+",":xv$=xv$+a$
 position #2,256,zm,32:print #2,xv\xv$
 xi=xi-1:if xi=0 then xi$="":goto item.a
 if y=1 then xi$=mid$(xi$,5):goto item.a
 if (y+4)>l then xi$=left$(xi$,y-1):goto item.a
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
 goto item.a
;
food
 print \"Lurch takes you to the food locker.."
food.a
 input @2\"G)ive or T)ake food? :"i$ 
 if i$="G" goto give.f
 if (i$="") or (i$="Q") goto menu.a
 if i$<>"T" goto food.a

take.fd
 if (xf>(zo-1)) print \"No room left in your pack.":goto food.a
 position #2,256,zm,116:input #2,xv\xv$
 if xv<1 print \"'Alas, the pantry is empty!'":goto food.a
 dy$=dw$+"stores"
 open #1,dy$
tk.fd.1
 print \"The Guild now has:"
 print:for x=1 to xv
 y=(x*4)-3:a=val(mid$(xv$,y))
 position #1,26,a,2
 input #1,n$
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xv
 next

tk.fd.2
 input @2\"Take which food number? "a$:x=val(a$)
 if (a$="") or (a$="Q") close #1:goto food.a
 if a$="?" goto tk.fd.1
 if (x<1) or (x>xv) print "We don't have that!!":goto tk.fd.2
 y=(x*4)-3:a=val(mid$(xv$,y))
 a$=right$("000"+str$(a),3)+","
 if instr(a$,xf$) print \"You already carry that!":goto tk.fd.2
 position #1,26,a,2
 input #1,n$:close #1
 xv=xv-1:if xv=0 then xv$="":goto get.fd
 l=len(xv$)
 if y=1 then xv$=mid$(xv$,5):goto get.fd
 if (y+4)>l then xv$=left$(xv$,y-1):goto get.fd
 xv$=left$(xv$,y-1)+mid$(xv$,y+4)
get.fd
 xf=xf+1:a$=right$("000"+str$(a),3)+",":xf$=xf$+a$
 if xo<20 then xo=xo+1:xo$=xo$+a$:goto gotfd
 xo$=mid$(xo$,5)+a$
gotfd
 zw$=mid$(n$,3):zx$="TOOK"
 print \"Lurch hands you the "zw$".":gosub add.lg
 position #2,256,zm,116:print #2,xv\xv$
 if vk>2 vk=vk-2
 goto food.a
;
give.f
 position #2,256,zm,116:input #2,xv\xv$
 if xv>7 print \"'Sorry, our pantry is full!'":goto food.a
pr.food
 if xf=0 print \"'Alas, you have no rations!'":goto food.a
 dy$=dw$+"stores"
 open #1,dy$
pr.food
 print \"You now carry:"\
 print:for x=1 to xf
 y=(x*4)-3:a=val(mid$(xf$,y))
 position #1,26,a,2
 input #1,n$
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xf
 next

drp.fd
 input @2\"Give which ration number? "a$:x=val(a$)
 if (a$="") or (a$="Q") close #1:goto food.a
 if a$="?" goto pr.food
 if (x<1) or (x>xf) print "You're NOT carrying that!!":goto drp.fd
 y=(x*4)-3:a=val(mid$(xf$,y))
 position #1,26,a,2
 input #1,n$:close #1
 xv=xv+1:a$=right$("000"+str$(a),3)+",":xv$=xv$+a$
clr.food
 xf=xf-1:if xf=0 then xf$="":goto givfd
 l=len(xf$)
 if y=1 then xf$=mid$(xf$,5):goto givfd
 if (y+4)>l then xf$=left$(xf$,y-1):goto givfd
 xf$=left$(xf$,y-1)+mid$(xf$,y+4)
givfd
 zw$=mid$(n$,3):zx$="GAVE"
 print \"Lurch puts the "zw$" on the shelf.":gosub add.lg
 position #2,256,zm,116:print #2,xv\xv$
 if vk<2000 vk=vk+2
 goto food.a

chalk.bd
 print \"You wander over and read the small chalk board.."
 position #2,256,zm,156:input #2,a$,xv$
 print \"It reads.. FROM "a$":"\\"'"xv$"'"
 input @2\"Write over message? y/[N]:"i$
 if i$<>"Y" goto menu.a
chalk.a
 print \"Write new message, 75 char max."
 print '
....:....|....:....|....:....|....:....|....:....|....:....|....:....|....:'
 input @3 xv$:if xv$="" print \"You write nothing..":goto menu.a
 if len(xv$)>75 print \"Too long! Lurch snickers..":goto chalk.a
 position #2,256,zm,156:print #2,n1$,xv$
 goto menu.a
;
show.lg
 f$=dx$+zy$+".LOG":gosub show.file
 if flag(25) input @2\"Clear log? y/[N]:"i$
 if i$="Y" gosub kill.lg
 goto menu.a
;
add.lg
 if left$(zw$,1)="0" then if len(zw$)>1 zw$=mid$(zw$,2):goto add.lg
 dy$=dx$+zy$+".LOG":create dy$:open #1,dy$:append #1
 print #1, left$(date$,6)yr$" "left$(time$,8)
 print #1, n1$" "zx$" "zw$
 print #1,"[]=-=-=-=-=-=-=["zy$"]=-=-=-=-=-=-=[]":close #1:return
;
kill.lg
 dy$=dx$+zy$+".LOG"
 kill dy$:create dy$:open #1,dy$
 print #1, "           LOG OF THE "zy$
 print #1, "           Date: "left$(date$,6)yr$
 print #1, "[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close #1:return
;
weapon
 position #2,256,zm,235:input #2,x
 if x<1 print\"There is no weapon in the box.":input@2"Put in a weapon? y/[N]:"i$:if i$<>"Y" goto menu.a
 if x<1 goto give.wep
 dy$=dx$+"weapons":open #1,dy$
 position #1,34,x:input #1,a$\a$:close #1
 a$=mid$(a$,4)
stop
 print "There is a "a$" here.":input @2"Take it? y/[N]:"i$
 if (i$<>"Y") or (yx$="*ANNEX*") goto menu.a
 if xw>5 print \"You can carry no more weapons!":goto menu.a
 xa$=right$("000"+str$(x),3)+","
 a=instr(xa$,xw$):if a print "You already have one!":goto menu.a
 xw=xw+1:xw$=xw$+xa$:position #2,256,zm,235:print #2,0
 print \"Lurch hands you the "a$
 zx$="TOOK":zw$=a$:gosub add.lg
 i$="Took "+zw$+"from weapon box":gosub sys.log
 if vk>5 vk=vk-5
 goto menu.a

give.wep
 if yx$="*ANNEX*" goto menu.a
 if xw<1 print \"You don't have any!":goto menu.a
 wr$="":dy$=dx$+"weapons":open #1,dy$
 print \"Give which weapon:"\
 for i=1 to xw:y=(i*4)-3:x=val(mid$(xw$,y))
 position #1,34,x:input #1,cb$\w$:w$=mid$(w$,4)
 print i". "w$
 next
sel.wep
 input @2\"Which : "i$:if i$="" or i$="Q" close #1:goto menu.a
 x=val(i$)
 if (x<1) or (x>xw) print "You don't have that!":goto sel.wep
 y=(x*4)-3:x=val(mid$(xw$,y))
 vw=10:if vk<vw vw=vk
 if x=17 print "'I will not take that!!'":vk=vk-vw:goto sel.wep
 position #1,34,x:input #1,cb$\w$\s,d,v
 xw=xw-1:w$=mid$(w$,4)
 if xw=0 then xw$="":goto wr.weap
 l=len(xw$)
 if y=1 then xw$=mid$(xw$,5):goto wr.weap
 if (y+4)>l then xw$=left$(xw$,y-1):goto wr.weap
 xw$=left$(xw$,y-1)+mid$(xw$,y+4)
wr.weap
 position #2,256,zm,235:print #2,x
 print \"Lurch carefully places the "w$" in the box."
 close #1:zx$="GAVE":zw$=w$:gosub add.lg
 i$="Put "+zw$+" in weapon box":gosub sys.log
 if vk<2000 vk=vk+5
 goto menu.a
;
sys.log
;.. i$=log message
 open #1,"a:add.log":append #1
 print #1,"Spur.guild] "i$" @"time$:close #1:return
;
compile
 if info(5) print \"Compiled..":link "k:system.seg"
comp.ck
 print "ok":return
;

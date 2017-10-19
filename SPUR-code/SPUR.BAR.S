
; spur.bar.s

 on nocar goto dropped
 public compile
 public restart

 yw=7:yx=7:yy=1:yz=1:zv$="":d6$=""
 gosub set.var
 print \"You stand inside the door of a smoky bar.."
 print "A faded sign says; [ WALL BAR & GRILL ]"
 if vw y=9:x=1:gosub screen
 d4$="ASCII":if vw>0 d4$="ANSI":if vw=2 d4$="PROTERM"
 i$="Mode = "+d4$:gosub add.lg:d4$=""

 gosub restart1

 d4$="Mundo checks your books..":d5$="":gosub msg:gosub read.a1$
 d4$="":gosub msg
 if (g7>0) or (g8>0) d4$="He 'escorts' you over to Vinney!":gosub msg:yy=1:yw=9 :goto mundo.ck
 if vw gosub ansi.prompt

move
 vu=0:yw=yx:yy=yz:gosub rest.rm
 gosub tim.chk:if (ev-ex)<120 d4$="Dusk approaches...":d5$="":gosub msg
 if vw=0 goto ascii
 if zp<>hp i$=right$(" "+str$(hp),2):zp=hp:x=1:y=17:gosub screen:print i$;
 x=24:y=17:gosub screen
ascii
 if vw=0 print \hp" hp) Move N,S,E,W,Q :";
 get i$:if vw=0 print ""
 if d4$<>"" d4$="":d5$="":gosub msg
 if asc(i$)=13 d4$="KEYS ARE HOT, DO NOT PRESS <CR>":d5$="":gosub msg:goto move
 if (not instr(i$,"NSEWQ")) or (len(i$)>1) d4$="Bad entry!":d5$="":gosub msg :goto move
 if i$="N" yy=yy-1:if yy<1 gosub door.chk
 if i$="S" yy=yy+1
 if i$="E" yw=yw+1
 if i$="W" yw=yw-1
 if i$="Q" goto advent
 if (yy<1) or (yy>4) goto bad.move
mundo.ck
 gosub rest.rm:gosub set.man
 if mid$(zt$,yw,1)="o" gosub fight:goto move
 if mid$(zt$,yw,1)<>" " goto bad.move
 gosub prt.room
 if yy=1 if yw=5 gosub home:goto thug
 if yy=1 if yw=9 gosub home:i$="vinney":dy$=ds$+"spur.bar3":link dy$
 if yy=2 if yw=2 gosub home:goto skip
 if yy=3 if yw=9 gosub home:goto slave
 if yy=4 if yw=5 gosub home:dy$=ds$+"spur.bar2":link dy$
 if yy=4 if yw=9 gosub home:goto zelda
 goto move
bad.move
 d4$="Laughter fills the bar, as you"
 d5$="try to walk thru solid objects":gosub msg
 if hp>5 hp=hp-1
 goto move

rest.rm
 zw$="|o[]     []o|"
 zx$="|           |"
 zy$="|--+     []o|"
 zz$="|oo!     []o|"
 return

set.man
 if yy=1 zt$=zw$
 if yy=2 zt$=zx$
 if yy=3 zt$=zy$
 if yy=4 zt$=zz$
 return

prt.room
 i$="*"
 if vw=1 i$=chr$(2)
 if vw=2 i$=chr$(16)+"@"+chr$(14)
 if vw x=yx:y=yz+10:gosub screen:print " ";:x=yw:y=yy+10:gosub screen:print i$;
 yx=yw:yz=yy
 zt$=left$(zt$,yw-1)+"*"+mid$(zt$,yw+1)
 if yy=1 zw$=zt$:else if yy=2 zx$=zt$
 if yy=3 zy$=zt$:else if yy=4 zz$=zt$
 if vw=0 print \"+----+ +----+"\zw$\zx$\zy$\zz$\"+-----------+"
 return

thug
 print \"The Blue Djinn sits behind the table"
 print "'What do you want?' he hisses"
thug.1
 input @2"H)ire, L)eave, I)nsult :"i$
 if i$="L" or i$="" d6$="He looks relieved..":goto restart
 if i$="H" goto hire
 if i$="I" goto bouncer
 print '
The Blue Djinn looks amused..':goto thug.1
hire
 print \"Who do you wish me to mess up?"
 input @2"Player number (?=list) :" i$
 if i$="?" gosub plr.list:goto hire
 x=val(i$):if (x=0) or (x>np) goto thug.2
 gosub rd.plyr
 if (n2$="") or (ys=0) goto thug.2
 print \"You want me to beat up "n2$"?";
 input @2" Y/N: "i$
 if i$<>"Y" print \"'Well, make up your mind!'":goto thug.1
 zr=yn*500:print \"'For a level "yn" opponent, the"
 print "price is "zr" gold. Ok?";:input " Y/N "i$
 if i$<>"Y" d6$="He snickers..":goto restart
 g3=gh:g4=gl:g1=0:g2=zr:gosub chk.gold
 if a=0 d6$="Ye do not have enough gold.":goto restart
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 print \"He writes up the contract.."
 zw=5:zw$="1"
;... input zw=position number, zw$=new value
 dy$=dx$+"spur.status":open #1,dy$:position #1,32,x:input #1,i$
 i$="-"+i$+"-"
 zx$=left$(i$,zw):zy$=mid$(i$,zw+2)
 i$=zx$+zw$+zy$:i$=mid$(i$,2,10)
 position #1,32,x:print #1,i$:close
 input @2\"Do you wish to remain unknown? Y/N:"i$
 zw$="SOMEBODY":if i$<>"Y" then zw$=n1$
 dy$=dx$+"thug":open #1,dy$:position #1,50,x
 print #1,zw$,n1$,pn,xp,0:close
 d6$="The Blue Djinn bows, 'The agreement shall be carried out..'"
 goto restart

thug.2
 print \"The Blue Djinn scowls.":goto thug.1
;
slave
 print \"Fat Olaf, the slave trader is behind the table"
 print "'VOT KIN I DU VER YA?'"
slave.a
 input @2\"B)uy, S)ell, M)aintain, L)eave :"i$
 if i$="B" goto buy
 if i$="S" goto sell
 if i$="M" goto maint
 if (i$="L")or (i$="") d6$="Olaf watches you leave.":goto restart
 print \"KUD YE SPEK UP YUNGUN?"\:goto slave.a

buy
 if a1 then if a2 then if a3 print \"YU HAV 3 ALREADY!!":goto slave.a
 xu=0:gosub show.slv:if xu=0 print \"SURRY, ALD SOLT UT!":goto slave.a
buy.a
 input @2\"BUY VICH UN? :"i$:if i$="" goto slave.a
 zz=val(i$):if zz=0 print \"'HUH?'":goto slave.a
 if zz>x print \"'WHOA, DUN'T AVE THAT MANY!'":goto buy.a
 dy$=dx$+"allies":open #1,dy$
 position #1,26,zz:input #1,cb$\x1$\x2,x3:close
 if cb$<>"1" print \"'HE IS NUT VER SALE!'":goto buy.a
 x=x2*100:if instr("!",x1$) x=x*2:print \"(ELITE ALLY!)"
 print \"'VELL, "x1$" IZ A VINE SPECIMEN,"
 print "BUT VER YE, IT WILL ONLY BE "x
 input @2"GALD! HOKEY?' Y/N "i$:if i$<>"Y" print \"'VELL, TOO BAD!'":goto buy.a
 g3=gh:g4=gl:g1=0:g2=x:gosub chk.gold
 if a=0 print \"YE DUN'T HAV ENOUGH GALD.":goto buy.a
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 dy$=dx$+"allies":open #1,dy$
 position #1,26,zz:print #1,0:close
 if a1=0 d1$=x1$:a1=x2+5:h1=zz:goto buy.b
 if a2=0 d2$=x1$:a2=x2+5:h2=zz:goto buy.b
 d3$=x1$:a3=x2+5:h3=zz
buy.b
 print \"'VINE! MAY HE SERVE YE WELL!":goto slave.a

sell
 gosub your.slv
sell.a
 input @2\"VICH SERVANT DO YE WISH TO SELL? "i$
 if i$="" or i$="Q" print \"Olaf shrugs":goto slave.a
 z=val(i$)
 if (z<1) or (z>3) print \"'COM COM, 1 TEU 3!' (<CR> aborts)":goto sell.a
 zt$=""
 if z=1 then if a1>0 zt$=d1$:zr=a1:zs=h1
 if z=2 then if a2>0 zt$=d2$:zr=a2:zs=h2
 if z=3 then if a3>0 zt$=d3$:zr=a3:zs=h3
 if zt$="" print \"'I TINK YE MUST BE DRINKING TEU MOCH!'":goto sell.a
 if zs=0 print \"'OLAF DOZ NOT BUY FREE SPIRITS!!'":goto sell.a
 gosub slv.srch:if zz=0 print \"'I DUN'T WONT HIM!'":goto sell.a
 zr=zr*50:if instr("!",zt$) zr=zr*2
 print \"'HE DUN'T LOOK TOO GOOD, BUT"
 print "I GUS I CUN GIVE YE "zr" GALD.'"
 input @2 "HOKAY? Y/N :" i$:if i$<>"Y" print \"'HOH VELL..'":goto sell.a
 g2=zr:gosub add.gold:gosub prt.gold
 dy$=dx$+"allies":open #1,dy$
 position #1,26,zz:print #1,1:close
 if z=1 d1$="*":a1=0:h1=0
 if z=2 d2$="*":a2=0:h2=0
 if z=3 d3$="*":a3=0:h2=0
 if vk>10 vk=vk-10
 print \"'HOKAY VINE! DUNKAH'":goto slave.a

maint
 gosub your.slv
maint.a
 input @2\"VICH SERVANT DO YE VITCH TO STRENGTHEN? "i$
 if i$="" or i$="Q" print \"Olaf shrugs":goto slave.a
 z=val(i$)
 if (z<1) or (z>3) print \"'COM COM, 1 TEU 3!' (<CR> aborts)":goto maint.a
 zt$=""
 if z=1 then if a1>0 zt$=d1$:zr=a1:zs=h1
 if z=2 then if a2>0 zt$=d2$:zr=a2:zs=h2
 if z=3 then if a3>0 zt$=d3$:zr=a3:zs=h3
 if zt$="" print \"'I TINK YE MUST BE DRINKING TEU MOCH!'":goto maint.a
 if zs=0 x2=15:zz=1:goto maint.b
 gosub slv.srch
maint.b
 if (zz<1) or (x2-zr<1) print \"'I CON DU NUTIN VER HIM!'":goto maint.a
 zz=(x2-zr)*20:print \"'IT VIL COST YE "zz" GALD!"
 input @2"HOKEY?' Y/N :" i$:if i$<>"Y" print \"Olaf shrugs..":goto maint.a
 g3=gh:g4=gl:g1=0:g2=zz:gosub chk.gold
 if a=0 print \"YE DO NOT HOV ENOUGH GALD.":goto maint.a
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 if z=1 a1=x2
 if z=2 a2=x2
 if z=3 a3=x2
 if vk<2000 vk=vk+5
 print \"Olaf does something mysterious..."
 print \"'DER!! NAOW IZ BEDDER!!":goto slave.a

show.slv
 print \"Servants for sale:"\
 x=1:dy$=dx$+"allies":open #1,dy$
show.s2
 position #1,26,x:input #1,cb$\x1$\x2,x3
 setint(1)
 if cb$="1" xu=1:print x") "x1$", strength = "x2
 if (cb$="") or (x>100) or (key(1)) close:return
 x=x+1:goto show.s2

your.slv
 print \"Your current servants:":z=0
 if a1 print "1) "d1$", strength = "a1:z=1
 if a2 print "2) "d2$", strength = "a2:z=1
 if a3 print "3) "d3$", strength = "a3:z=1
 if z=0 print \"Olaf chuckles.. 'YU DUN'T AVE ANY!'":pop:goto slave.a
 return

slv.srch
;... input zt$=name to search for, zs=record #. Returns zz=# if found
 zz=0:dy$=dx$+"allies":open #1,dy$
 position #1,26,zs
 input #1,cb$\x1$\x2,x3
 if x1$=zt$ zz=zs
 close:return

zelda
 print \"Madam Zelda hovers over a ball"
zelda.1
 print \"'What Doooo.. you wish?'"
 input @2"S)tudy a player, R)esurrect monsters :"i$
 if i$="" or i$="Q" d6$="'Gooo away, you bother my cat..'":goto restart
 if i$="S" goto zelda.3
 if i$="R" goto zelda.4
 goto zelda.2
zelda.3
 input @2\"Study - Player number (?=list) :" i$
 if i$="?" gosub plr.list:goto zelda.3
 x=val(i$):if (x=0) or (x>np) goto zelda.2
 if x=pn print \"'I suggest you ussssse a mirror!'":goto zelda.1
 gosub rd.plyr
 if (n2$="") or (ys=0) goto zelda.2
 print \"You want me to reeead "n2$"?";
 input @2" Y/N: "i$
 if i$<>"Y" print \"'Wellll, make up your mind!'":goto zelda.2
 input \"'It will cost you 1000 gold, ok?' Y/N :"i$
 if i$<>"Y" print \"'Hmpppth..'":goto zelda.1
 g3=gh:g4=gl:g1=0:g2=1000:gosub chk.gold
 if a=0 print \"Ye doooo not have enough gold.":goto zelda.1
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 print \"She hunkers down over the ball.."
 print "'I SEEEEEE......."\
 print n2$" on dungeon level "yl"."
 print "With "yh" hit points, a strength"
 print "of "cs", intelligence of "ci","
 print "dexterity of "cd", energy of "ce","
 print "constitution of "ct", wisdom of "cw"."
 print n2$" has achieved level "yn
 print "in the land, has "ye"% shield, and"
 print yf"% armor. Instruments of death...'"
 gosub pr.weapons
zelda.5
 print \"Zelda stares at you. Her cat stares too.":goto zelda.1
zelda.2
 print \"'Are yooouu trying to be cute?'":goto zelda.1
zelda.4
 print \"Resurrect monsters for"
 input @2"Player number (?=list) :" i$
 if i$="?" gosub plr.list:goto zelda.4
 x=val(i$):if (x=0) or (x>np) goto zelda.2
 if x=pn print \"'I suggest you NOT do that!'":goto zelda.1
 gosub rd.plyr
 if (n2$="") or (ys=0) goto zelda.2
 print \"You want me to bring "n2$"'S"
 input @2"monsters alive? Y/N: "i$
 if i$<>"Y" print \"'Wellll, make up your mind!'":goto zelda.2
 input \"'It will cost you 6000 gold, ok?' Y/N :"i$
 if i$<>"Y" print \"'Hmpppth..'":goto zelda.1
 g3=gh:g4=gl:g1=0:g2=6000:gosub chk.gold
 if a=0 print \"Ye doooo not have enough gold.":goto zelda.1
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 input @2\"'Dooo you wish to be unknown? Y/N:"i$
 if i$="Y" i$="SOMEBODY":else i$=n1$
 print \"Zelda and her cat really get weird..."
 dy$=dx$+"spur.monsters"
 open #1,dy$:position #1,44,x
 print #1,0\"":close
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, "       ** MONSTER REVIVAL **"
 print #1, "ZELDA CAST 'MONSTER LIFE' ON MONSTERS"
 print #1, "IN THE DUNGEON OF "n2$"!"
 print #1, "SPELL PAID FOR BY "i$
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 print \"'It issssss done!'":goto zelda.5
;
skip
 i$="SKIP":dy$=ds$+"spur.bar2":link dy$

fight
 if vw d4$="":d5$="":gosub msg:x=1:y=18:gosub screen
 input @2\"'Are you trying to pick a fight?' (Y/N) " i$
 if i$<>"Y" print "'Well then, WATCH it!'":return
 pop
bouncer
 d4$="At a signal, Mundo the bouncer knocks you over the head with a baseball"
 d5$="bat, and throws you out in the street..":gosub msg
 if hp>6 hp=hp-5
 goto advent

door.chk
 if yw<>7 return
 pop
advent
 i=0:zv$=""
 d4$="You return to the street..":d5$="":gosub msg
 dy$=dz$+"spur.main":link dy$
;
dropped
 i$="SPUR.BAR"
 dy$=ds$+"spur.logon"
 link dy$,"quit3"
;
plr.list
 print \"List of players in Game"
 input @2 \"Match letters or CR for all: "i$
 x=1:dy$=dx$+"spur.users":a=1
 open #1,dy$
 gosub plrlist5
 
plrlist1
 position #1,130,x
 input #1,n$,l1,b1,b2,b3,b4
 setint(1)
 if (not l1) goto plrlist4
 if not instr(i$,n$) goto plrlist4
 setint(1)
 
plrlist2
 n$=mid$(n$,2)
 print right$("  "+str$(b1),3)"  ";
 print left$(n$+"               ",14)
 
plrlist4
 x=x+1:if (x>np) or (key(1)) close:return
 goto plrlist1

plrlist5
 print \\" #   Adventurer"
 print "---  ---------------"
 return
;
add.gold
 gl=gl+g2:if gl=>10000 then gl=gl-10000:gh=gh+1
 return
 
sub.gold
 if g2>gl then gl=gl+10000:gh=gh-1
 gl=gl-g2:return

prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
 
chk.gold
 a=0
 if g3>g1 then a=1:return
 if (g3=g1) and (g4=>g2) then a=1:return
 return
;
rd.plyr
 dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$:close
 n2$=mid$(n2$,2)
 return
;
pr.weapons
 dy$=dx$+"spur.weapons"
 open #1,dy$:position #1,64,x
 input #1,zz\xu$:close
 if zz=0 print \"No Weapons.":return
 dy$=dx$+"weapons"
 open #1,dy$
 print:for x=1 to zz
 y=(x*4)-3:a=val(mid$(xu$,y))
 position #1,34,a,2
 input #1,xv$:print mid$(xv$,4)
 next:close:return
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto cnf.qt1
 return
cnf.qt1
 mw=0:mf=0:dy$=dz$+"spur.sub":link dy$,"quit"
;
;...zt$="whatever" and gosub spin.curs.
spin.curs
 for xv=1 to len(zt$)
 print "!";chr$(8);"/";chr$(8);"-";chr$(8);"\";chr$(8);"!";chr$(8);
 print mid$(zt$,xv,1);:next
 return
;
read.a1$
 dy$=dx$+"spur.a1$":open #1,dy$
 position #1,64,un
 input #1,g5,g6,g7,g8,g9,g9,g0
 close:return
;
writ.a1$
 dy$=dx$+"spur.a1$":open #1,dy$
 position #1,64,un
 print #1,g5,g6,g7,g8,pn,g9,g0
 close:return
;
restart
 gosub restart1:goto move
restart1
 gosub set.var:if vw=0 goto restart2
 y=10:x=1:gosub screen
 i$="o":a$="*"
 if vw=1 i$=chr$(1):a$=chr$(2)
 if vw=2 i$=chr$(16)+"A"+chr$(14):a$=chr$(16)+"@"+chr$(14)
 print "+----+ +----+"
 print "|"i$"[]     []"i$"|   N"
 print "|           | W-+-E"
 print "|--+     []"i$"|   S"
 print "|"i$;i$"!     []"i$"|("a$"=YOU)"
 print "+-----------+"
 if vw gosub ansi.prompt
restart2
 if d6$<>"" d4$=d6$:d6$="":gosub msg
 gosub rest.rm:gosub set.man:gosub prt.room
 return
;
ansi.prompt
 x=4:y=17:gosub screen:print "hp) Move N,S,E,W,Q :"
 return

;
;vw: 0=ASCII, 1=ANSI, 2=PROTERM
;f$=CONTROL character
;sc$=screen clear
;xx$=clear to end of line
;d4$=message line 1
;d5$=message line 2
;d6$=return message from routines
;(zp used to detect difference in HP)

set.var
 free:vw=0:f$="":sc$="":xx$="":d4$="":d5$="":zp=0
 if flag(29)=0 vw=1
 if flag(30)=0 vw=2
 if vw=0 goto home
; *[ set Proterm ]*
 if vw=2 f$=chr$(30):sc$=chr$(12):xx$=chr$(25):goto home
; *[ set ANSI ]*
 f$=chr$(27):sc$=f$+"[2J":xx$=f$+"[K":goto home

;
;  X=horizontal, Y=vertical position
screen
 if vw=0 print \:return
 if y>4 poke 37,y-1:poke 36,x-1:if info(0)=0 return
 if vw=2 print #4 f$;chr$(31+x);chr$(31+y);
 if vw=1 print #4 f$"["y";"x"f";
 return

; d4$=message line 1, d5$=message line 2
msg
 if vw x=1:y=19:gosub screen
 print d4$;xx$
 print d5$;xx$
 return

home
 if info(0) print #4 sc$;
 if vw=0 return
 home:return
;
add.lg
;.. i$=log message
 create "a:add.log":open #1,"a:add.log"
 append #1:print #1,"[SPUR.BAR] "i$:close:return
;
compile
 if un=1 print "Compiled..":link "k:system.seg"
 return
;
 ;


; spur.bar2.s

 on nocar goto dropped
 public compile

 if i$="SKIP" goto skip

 print \"Guss the Barkeep smiles at you"
 print "'HAAY... DUDE! Like wats happenin?'"
bar.a
 input @2\"T)alk, L)eave :" i$
 if i$="T" goto bar.b
 if (i$="") or (i$="L") or (i$="Q") print \"'Later... dude!'":goto move
bar.b
 print \"'Soooo... Whats new in the Land of OZ?'"
 input @2"'Like, ya wanna F)lip some coins, B)lackjack, or W)hat?' :" i$
 if i$="F" print \"'AWWRIGHT 'M Man!' Guss thumps a bag of gold on the bar!" :goto flip
 if i$="B" print \"'AWWRIGHT!' Gus plops a strange hat on his head, and deals..":goto blackjack
 if i$="" or i$="Q" goto bar.a
 if i$<>"W" print \"Guss looks puzzled..":goto bar.b
 print \"So, what's on yer mind "n1$"?"
 input @2 \"->" i$
 if i$="" or i$="Q" goto bar.a
chat.chk
 gosub tim.chk:if (ev-ex)<120 print "Dusk approaches..."
 gosub rnd100xv
 if i$="?" i$="'Could you be a bit more clear?'":goto chk.3
 if not instr(" ",i$) if xv>60 i$="'Most peculiar..'":goto chk.3
 i$=i$+" "
chk.1
 gosub rnd100xv:if len(i$)<3 goto chk.2
 xu=len(i$):zz=instr(" ",i$)
 zt$=" "+left$(i$,zz):if un=1 print "'"zt$"' ";
 if instr(zt$," SHIT FUCK ASS HOLE HELL CUNT ") then if xv>20 i$="Guss is shocked by your foul mouth..":goto chk.3
 if instr(zt$," HOW WHY WHERE WHAT WHEN WHO ") if xv>50 i$="'An interesting question..'":goto chk.3
 if instr(zt$," SHUTUP JERK FAGGOT KISS KICK KILL HIT BEAT HELL GEEK UGLY PUSSY ") gosub fight:i$="'Hmpth..'":goto chk.3
 if instr(zt$," DURA SPUR LAND MONSTER AMULET ") then if xv>50 i$="Guss looks nervous, 'Watch what you say..'":goto chk.3
 if instr(zt$," RING EXCALIBUR GUILD EVIL GOOD GOLD ") then if xv<50 i$="'Stay healthy, keep your nose clean and you will find out!'":goto chk.3
 gosub rnd100xv
 if instr("HELP",i$)if xv>50 i$="'One must help one's self..'":goto chk.3
 if instr("?",i$) if xv>75 i$="'Why do you ask?'":goto chk.3
 if instr("?",i$) if xv>66 i$="'What kind of question is that?'":goto chk.3
 if instr("?",i$) if xv>50 i$="'I waz wondering that myself..'":goto chk.3
 if instr("?",i$) if xv>25 i$="'Beats me..'":goto chk.3
 if xu>zz+1 i$=mid$(i$,zz+1):goto chk.1
chk.2
 gosub rnd100xv:i$=""
 if xv>10 i$="Guss looks at you, 'You don't say!'"
 if xv>25 i$="Guss looks thoughtfull.."
 if xv>40 i$="Guss refills your glass, listening.."
 if xv>55 i$="'Um-hmmm...'"
 if xv>70 i$="'Say! How do ya suppose they get frosting in those twinkies?'"
 if xv>90 i$="Guss stares off into space.."
 if i$="" i$="'yep..'"
chk.3
 print \i$
 i$=rnd$:input @2\"->" i$
 if i$="" or i$="Q" i$="":goto bar.a
 goto chat.chk
;
flip
 gosub tim.chk:if (ev-ex)<120 print "Dusk approaches..."
 print \"("gh*10000+gl" gp)"
 if gh>1 print \"'Yer too rich for me!'":i$="" goto bar.a
 input @2\"'How much ya wanna bet?' "i$:if i$="" or i$="Q" i$="":goto bar.a
 zz=val(i$):if zz=0 goto bar.a
 g3=gh:g4=gl:g1=0:g2=zz:gosub chk.gold
 if a=0 print \"'Hey dude, you don't have that much!'":goto flip
 if zz>1000 print \"'1000 max, my friend..'":goto flip

flip.a
 input "Call it sam! H)eads, T)ails " i$
 if i$<>"H" then if i$<>"T" print \"'Huh?'":goto flip.a
 print \"Gus flips a coin.."\
 zt$="  _":gosub spin.curs:zt$=rnd$:zt$="H":if random(1000)>500 zt$="T"
 if zt$="H" print \\"'HEADS!'":else print \\"'TAILS!'"
 if zt$=i$ print \"'You win!'":gosub add.gold:goto flip
 print \"'Too bad..'":gosub sub.gold:goto flip
;
drop.bj
 i$="Dropped carrier in blackjack":gosub add.lg
 gosub tran.gd1:recall "a:spur.var":gosub tran.gd2
dropped
 i$="SPUR.BAR2":kill "a:spur.var"
 dy$=ds$+"spur.logon":link dy$,"quit3"
;
show.file
 setint(1):print \s$\:copy f$:setint(""):return
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
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto cnf.qt1
 return
cnf.qt1
 kill "a:spur.var"
 mw=0:mf=0:dy$=dz$+"spur.sub":link dy$,"quit"
;
;...zt$="whatever" and gosub spin.curs.
spin.curs
 for xv=1 to len(zt$)
 print "!";chr$(8);"/";chr$(8);"-";chr$(8);"\";chr$(8);"!";chr$(8);
 print mid$(zt$,xv,1);:next
 return
;
;*********************
;*
;*    Black Jack
;*     Ver. 1.4
;*
;*********************
;  By K. Echstenkamper
; Brought to you by:
; The Fighting Falcon
; 516-944-9821 300/1200

blackjack
 store "a:spur.var":gosub tran.gd1
 i$="BLACKJACK IN :"+str$(gh*10000+gl)+" gp":gosub add.lg
 on nocar goto drop.bj

bj.start
 gosub zero.set:poke 120,0:xz=10000-zw
 gosub timchkbj:if (ev-ex)<120 print "Dusk approaches..."
 print \"("gh*10000+gl" gp)"
 if gh>1 print \"'Yer too rich for me!'":i$="" goto bj.end
 input @2\"'How much ya wanna bet?' "i$:if i$="" or i$="Q" goto end.bj
 b=val(i$):if b=0 goto end.bj
 g3=gh:g4=gl:g1=0:g2=b:gosub chk.gold
 if gh+gl<1 print \"'Hey dude, broke eh? Maybe later..'":goto end.bj
 if a=0 print \"'Hey dude, you don't have that much!'":goto bj.start
 if b>500 print \"'500 gold. Table limit, my friend..'":goto bj.start
 if b<25 print \"'Last of the big spenders!'"

set.num
 rnd$:gosub getnum:gosub bj.comm:zx=a:wr$=i$
 rnd$:gosub getnum:gosub bj.comm:zz=a:ww$=i$:xu=1
 rnd$:gosub getnum:gosub:bj.comm:zv=a:wx$=i$
 rnd$:gosub getnum:gosub bj.comm:zu=a:wy$=i$:xu=0
 zt=zx+zz:zs=zv+zu
 if zt>21 goto set.num
 if zs>21 goto set.num
 if zs=21 print \"Blackjack! I win! Most excellent!'":g2=b:gosub sub.gold:goto bj.start
 if zt=21 print \"'Blackjack! You win! Bogus!'":g2=b*2:gosub add.gold:goto bj.start
 goto bj.set1

bj.comm
 if a=11 and xu then i$="   Ace   ":zm=zm+1:return
 if a=11 then i$="   Ace   ":xs=xs+1:return
 if a=10 then i$="Face Card":return
 if a=9 then i$="  Nine   ":return
 if a=8 then i$=" Eight   ":return
 if a=7 then i$=" Seven   ":return
 if a=6 then i$="  Six    ":return
 if a=5 then i$="  Five   ":return
 if a=4 then i$="  Four   ":return
 if a=3 then i$=" Three   ":return
 if a=2 then i$="  Two    ":return

bj.set1
 gosub show.card:input @0 \\"|H|it |D|ouble |S|tand:" i$
 if i$="H" goto bj.set2
 if i$="S" goto com.turn
 if i$="D" g2=b*2:gosub chk.gold:if a=0 print\"Yo! Dude! You don't have the gold to do that!":goto bj.set1
 if i$<>"D" print\"'I think your shorts must be too tight..'":goto bj.set1
 b=b*2:rnd$:gosub getnum:zt=zt+a
 gosub bj.comm:gosub draw.card:if zt>21 and xs then zt=zt-10:xs=xs-1
 print"  You have "zt
 if zt>21 then print\"You busted! Radical!'":g2=b:gosub sub.gold:goto bj.start
 goto com.turn

bj.set2
 rnd$:gosub getnum:gosub bj.comm:zt=zt+a:print\"You draw a":gosub draw.card
 if zt>21 and xs then zt=zt-10:xs=xs-1
 if zt>21 print\"'You busted! Radical!'":g2=b:gosub sub.gold:goto bj.start
 print\"  You have "zt:input\"Would you like another Hit? (Y/N):"i$
 if i$ <>"Y" goto com.turn
 goto bj.set2

bj.result
 if zt=zs print \"  --- Push ---":goto bj.end
 if zs>21 print\\"'You win! Most henious'":g2=b:gosub add.gold:goto bj.end
 if zs>zt print\\"'I win! Tubuler!'":g2=b:gosub sub.gold:goto bj.end
 if zt>zs print\\"'You win! Most bogus..'":g2=b:gosub add.gold

bj.end
 print\"You had    = "zt
 print\"Gus had   = "zs\:goto bj.start

com.turn
 gosub dealer.hand

com.cards
 xu=1
 if zs>16 goto bj.result
 print\"Gus draws a":rnd$:gosub getnum:gosub bj.comm:gosub draw.card :zs=zs+a:if a>10 then zm=1
 if zs>21 and zm then zs=zs-10:zm=zm-1
 print\"  Gus has "zs:goto com.cards

getnum
 ds$="":ds$=ds$+RND$:a=random(1000):a=random(10)+1:if a=1 then a=11:return
 return

bj.stats
 setint(1):copy f$:return

show.card
 if zx<10 then zr=zx
 if zz<10 then zq=zz
 if zv<10 then zp=zv
 print\" _____________  _____________"
 print "|"zr"            ||"zq"            |"
 print "|             ||             |"
 print "|             ||             |"
 print "|  "wr$  "  ||  "ww$  "  |"
 print "|             ||             |"
 print "|             ||             |"
 print "|_____________||_____________|"

 print\"You have "zt:zr=0:zq=0
 print " _____________  _____________"
 print "|"zp"            ||             |"
 print "|             ||  * * * * *  |"
 print "|             || * * * * * * |"
 print "|  "wx$  "  ||  * * * * *  |"
 print "|             || * * * * * * |"
 print "|             ||  * * * * *  |"
 print "|_____________||_____________|"

 print \"Gus showing "zv:zp=0:return

draw.card
 if a<10 then zo=a
 print " _____________"
 print "|"zo"            |"
 print "|             |"
 print "|             |"
 print "|  "i$  "  |"
 print "|             |"
 print "|             |"
 print "|_____________|"
 zo=0:return

dealer.hand
 if zv<10 then xp=zv
 if zu<10 then zn=zu
 print\" _____________  _____________"
 print "|"xp"            ||"zn"            |"
 print "|             ||             |"
 print "|             ||             |"
 print "|  "wx$  "  ||  "wy$  "  |"
 print "|             ||             |"
 print "|             ||             |"
 print "|_____________||_____________|"

 print \"Gus showing "zs:xp=0:zn=0:return

zero.set
 zx=0:zz=0:zv=0:zu=0
 zt=0:zs=0:zr=0
 zq=0:zp=0:zo=0:xp=0
 zn=0:xs=0:zm=0
 xu=0:xz=0:return

timchkbj
 ex=clock(1)-ew:if ex<ev return
 pop:gosub tran.gd1:recall "a:spur.var":gosub tran.gd2
 goto cnf.qt1

end.bj
 gosub tran.gd1:recall "a:spur.var":gosub tran.gd2
 on nocar goto dropped
 goto bar.b

tran.gd1
 i$="a:temp":kill i$:create i$:open #1,i$:print #1,gh,gl:close
 return

tran.gd2
 open #1,"a:temp":inpõt #1,gh,gl:close
 i$="BLACKJACK OUT :"+str$(gh*10000+gl)+" gp"
 goto add.lg

;
skip
 print \"Skip sweats over a hot grill, muttering under his breath.."
skip.a
 print \"'Whatyla have mack?'"
 input @2"H)ash - 5g, C)offee - 1g :"i$
 if i$="" or i$="Q" print \"'Yeah, well... taker ezy..'"\:if not instr("*sk",ys$) if len(ys$)<240 ys$=ys$+"*sk"
 if i$="" or i$="Q" goto move
 if not instr(i$,"H*C") print \"'Eh? What?'":goto skip.a
 if instr("*sk",ys$) print \"Skip suddenly looks annoyed.. 'Hey B-O-Z-O! Are you a tad slow or what?'":goto bouncer
 if i$="H" g2=5:else g2=1
 if instr(i$,zv$) print \"'You just had the last of it!'":goto skip.a
 g3=gh:g4=gl:g1=0:gosub chk.gold
 if a=0 print \"'Ye don't got enough gold.'"\:goto move
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 zv$=zv$+i$
 if i$="H" print \"The hash is greazy, but hot and nourshing."
 if i$="C" print \"The steaming mug of coffee is strangly satisfying."
 if hp<25 then hp=hp+4:print "(hp+4)"
 if i$="H" then if ps<23 ps=ps+3:print "(Strength +4)"
 if i$="C" then if pe<23 pe=pe+3:print "(Energy +4)"
 if pt<23 then pt=pt+4:print "(Constitution +4)"
 goto skip.a
;
fight
 input @2\"'Are you trying to pick a fight?' (Y/N) " i$
 if i$<>"Y" print "'Well then, WATCH it!'":return
 pop
bouncer
 print \'
At a signal, Mundo the bouncer knocks you over the head with a baseball bat,
and throws you out in the street..':if hp>6 hp=hp-5
 goto advent
;
rnd100xv
 zw$=rnd$:xv=random(9999)/100
 return
;
move
 kill "a:spur.var"
 dy$=ds$+"spur.bar":link dy$,"restart"
;
advent
 i=0:zv$="":kill "a:spur.var"
 print \"You return to the street.."
 dy$=dz$+"spur.main":link dy$
;
add.lg
;.. i$=log message
 create "a:add.log":open #1,"a:add.log"
 append #1:print #1,"[SPUR.BAR2] "i$:close:return
;
compile
 if un=1 print "Compiled..":link "k:system.seg"
 return
;
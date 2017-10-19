
;... spur.misc7.s
 on nocar goto dropped
 if un=1 print "spur.misc7-";:gosub comp.ck

 public compile

 on nocar goto dropped
 if i$="WIN" goto win
 if i$="djinn" gosub thug:goto main.ret
 if i$="DIG" gosub dig.a:goto main.ret
 print \"Bad value of i$ in spur.misc7! i$="i$:goto advent

win
 on nocar goto dropped
 print \"A voice echoes in your ear.."
 if not instr(mid$(zu$,7,1),"12") print \"'Thou may not leave my land until the King of the Wraiths is slain!'":goto advent
 a=0:if xi=0 xi$=""
 i$=right$("000"+str$(og)+",",4)
 if instr(i$,xi$) print \"'Ye have found the Object I have sought!'":goto win2
 print \"'Ye does not have The Holy Grail! Ye may not pass!'":goto nowin
win2
 if mid$(zu$,9,1)="2" print \"'Ye have found Riches enough to pass through!'": goto win5
 print \"'Ye has not found the riches of TUT!"
 print "Ye may not pass through!'":goto nowin
win5
 print \"CONGRATULATIONS! YOU HAVE WON!!"\"Adding to conqueror's list.."
 i$="***[ "+a1$+"/"+n1$+" ]***":yz=18-(len(i$)/2):if yz<1 then yz=1
 h$=left$("                    ",yz)+i$
 i$="[]"+mid$(h$,3):h$=left$(i$+"                        ",35)+"[]"
 dy$=dx$+"spur.winners":open #1,dy$:append #1:print #1,h$:close
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1,"[*][*][*][*][*][*] [*][*][*][*][*][*]"
 print #1, left$(date$,6)yr$" "time$"- ULTIMATE VICTORY!"
 print #1, n1$" CONQUERED LAND OF SPUR!"
 print #1,"[*][*][*][*][*][*] [*][*][*][*][*][*]"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 print \"Writing in System Sub Board News.."

;..FOLLOWING WRITES IN DRIVE SPEC C4: FOR SYSTEM SUBBOARD NEWS

 f$="C4:B6.NEWS":kill f$:create f$:open #1,f$:append #1
 print #1,"[][][][][][][][][] [][][][][][][][][]"
 print #1,"[]      NEWS FROM LAND OF SPUR     []"
 print #1,"[]          [ "left$(date$,6)yr$" ]           []"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 print #1,h$
 print #1,"[] WAS VICTORIOUS IN LAND OF SPUR! []"
 print #1,"[][][][][][][][][] [][][][][][][][][]"\:close
 x=mn:mn=mn+1
 open #1,"c4:data3"
 y=mark(1):if y close:goto no.file
 position #1,8,6:print #1,x:close
no.file
 flag(7)=1:goto linkwin
;
nowin
 print\'
An invisible barrier holds you back! A
voice comes from the gloom and says:

"You have not found the key to SPUR!
 You may NOT pass through!"'
 goto advent
;
thug
 gosub thug.2
 if mid$(zu$,5,1)="1" gosub dig.a:gosub thug.2
 return

thug.2
 m=74:zu$=left$(zu$,4)+"0"+mid$(zu$,6)
 i$="THE BLUE DJINN "
 if instr("SPACE",ww$) i$=i$+"FLIES ALONG SIDE IN A SPACE SUIT!":else i$=i$+ "ROWS UP TO YOUR DINGY!"
 if instr("@@",lo$) print \i$:else print \"THE BLUE DJINN STARES AT YOU!"
 dy$=dx$+"thug":open #1,dy$:position #1,50,pn
 input #1,xv$,zt$,zt,zs,zp:close
 if zp=0 print \xv$" HAS HIRED ME TO ATTACK YOU!"
 if zp=1 print \xv$" ASKS THAT I RETURN THE COMPLIMENT!"
 if zp=2 print \"'WELL? I HOPE YOU HAVE THE GOLD!'"
thug.1
 print \"B)uy off F)ight";:if xv$<>zt$ print " A)sk name";
 if zp<>2 print " D)ig up gold";
 input @2" :"i$
 if zt<1 or zt>np i$="F"
 if i$="F" or i$="" print \"'ENGARDE!'":goto thg.news
 if i$="B" goto hire
 if i$="A" then if xv$<>zt$ goto name
 if zp<>2 then if i$="D" goto thug.dig
 print\"The Blue Djinn looks amused as you fumble at the keyboard.":goto thug.1

thug.dig
 print \"'VERY WELL, YOU MAY DIG UP YOUR GOLD!'"
 dy$=dx$+"thug":open #1,dy$:position #1,50,pn
 print #1,xv$,zt$,zt,zs,2:close
 zu$=left$(zu$,4)+"1"+mid$(zu$,6)
 return

hire
 zr=zs*500+100:print "'I will leave, and attack "xv$
 print "instead, for "zr" gold. Ok?";:input " Y/N:"i$
 if i$<>"Y" print \"He snickers..":goto thug.1
 g3=gh:g4=gl:g1=0:g2=zr:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto thug.1
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 print \"He writes up the contract.."
 zw=5:zw$="1"
;... input zw=position number, zw$=new value
 dy$=dx$+"spur.status":open #1,dy$:position #1,32,zt:input #1,i$
 i$="-"+i$+"-"
 zx$=left$(i$,zw):zy$=mid$(i$,zw+2)
 i$=zx$+zw$+zy$:i$=mid$(i$,2,10)
 position #1,32,zt:print #1,i$:close
 input @2\"Do you wish to remain unknown? Y/N:"i$
 xx$="SOMEBODY":if i$<>"Y" then xx$=n1$
 dy$=dx$+"thug":open #1,dy$:position #1,50,zt
 print #1,xx$,n1$,pn,xp,1:close:m=0
 print \"The Blue Djinn bows, 'The agreement shall be carried out..'"
 goto thg.news

name
 zr=zs*100
 print "I will reveal the name, for "zr" gold. Ok?";:input " Y/N:"i$
 if i$<>"Y" print \"He snickers..":goto thug.1
 g3=gh:g4=gl:g1=0:g2=zr:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto thug.1
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 xv$=zt$:print \"The name of my employer is "zt$"!"
 goto thug.1

thg.news
 dy$=dx$+"battle.log":create dy$:open #1,dy$:append #1
 print #1, left$(date$,6)yr$" "time$": HIRED THUG"
 i$="WAS":if m=0 i$="WAS TO BE"
 print #1, n1$" "i$" ATTACKED BY THE"
 print #1, "BLUE DJINN, IN "ww$","
 if m=0 print #1,"BUT "n1$" BOUGHT HIM OFF!"
 print #1, "ATTACK PAID FOR BY "xv$"."
 print #1, "[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
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
dig.a
 if xp=1 print\"Must be at least 2nd level to use this command":return
 if (cl>5 or instr("@",lo$)) print \"Can't do that here":return
 dy$=dx$+"bury."+str$(cl):open #1,dy$
 if mark(1) print\"(Creating file)":close #1:create dy$:open #1,dy$
 position #1,30,cr
 input #1,zw$,zx$,zy$,zz$,zv$
dig.b
 gosub tim.chk:if ev-ex<120 print "DUSK APPROACHES..."
 input @2\"Dig where: N)orth, S)outh, E)ast, W)est, C)enter :"xx$
 xv$="*":if xx$="" goto wr.bury
 if xx$="N" xv$=zw$
 if xx$="S" xv$=zx$
 if xx$="E" xv$=zy$
 if xx$="W" xv$=zz$
 if xx$="C" xv$=zv$
 if xv$="*" print "Huh?":goto dig.b
 gosub tim.chk:a=180:a$="your hands"
 if instr("151",xi$) a=60:a$="the shovel"
 if (ev-ex)<(a+1) print \"Not enough time to dig!":goto wr.bury
 print \"You dig with "a$", (-"str$(a/60)" minutes.)"
 ew=ew-a:for a=1 to 2000:next
 i$="DIG: Level "+str$(cl)+", room "+str$(cr)+" "+xx$:gosub add.lg
 i$=left$(xv$,1):xu$=mid$(xv$,2):xv$=""
 if (i$="" or i$="0" or xu$="") print \"Nothing...";:goto dig.d
; if i$="1" gosub fnd.food:goto dig.c
 if i$="2" gosub fnd.item:goto dig.c
 if i$="3" gosub fnd.gold:goto dig.c
 goto dig.b

dig.c
 if xv$="" print \"Nothing...";:goto dig.d
 i$="":gosub bury.add:goto dig.b

dig.d
 input @2 \"Bury something here? Y/n:"i$
 if i$="N" goto dig.b

dig.e
 input @2 \"Bury which? G)old, I)tem :"i$
 if i$="G" goto bry.gold
 if i$="I" goto bury.itm
 goto dig.d

bry.gold
 g1=gh:g2=gl:gosub prt.gold:print "["gd$"] ";
 input @2"Bury how much gold? :"i$
 zr=val(i$):if zr<0 print \"Number too large!":goto bry.gold
 if zr=0 goto dig.e
 g2=(zr/10)*10:if zr>g2 print "(Gold rounded down to "g2")"
 g3=gh:g4=gl:g1=0:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto dig.d
 if zr>9000 print "9000 max, please.":goto bry.gold
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 i$="3"+str$(zr/10):gosub bury.add:print \"Done!"
 i$="Bury "+str$(zr)+" gold":gosub add.lg
 goto dig.b

bury.itm
 dy$=dw$+"items":open #2,dy$
drop.a
 if xi<1 xi=0:print \"No Items!":close #2:goto dig.b
 print \"You are carrying:"\
 for x=1 to xi
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #2,30,a,2
 input #2,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 n$=mid$(n$,3):print right$("   "+str$(x),3)". - "n$
 next:print
drop.b
 input @2\"Bury which item? (?=list):"a$:x=val(a$):if a$=""close #2:goto dig.b
 if a$="?" goto drop.a
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto drop.b
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #2,30,a,2:input #2,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 n$=mid$(n$,3)
 if a=76 then zu$=left$(zu$,7)+"0"+mid$(zu$,9):if un=1 print "zu$="zu$
 dy$="Can't, you are USEing it!"
 if a=67 then if mid$(zu$,2,1)="1" print dy$:goto drop.b
 if a=1 then if cp=1 print dy$:goto drop.b
 i$="067,073,074,076,097,080,082,096,097,122,123,124,131,132,"
 i$=i$+"133,134,135,138,140,142,143,144,145,"
 a$=right$("00"+str$(a),3)
 if instr(a$,i$) print \"Restricted item, can't bury!":goto drop.b
 if a=73 print \"(You feel more normal..)"
 l=len(xi$):y=(x*4)-3
 xi=xi-1:if xi=0 then xi$="":goto drp.itm3
 if y=1 then xi$=mid$(xi$,5):goto drp.itm3
 if (y+4)>l then xi$=left$(xi$,y-1):goto drp.itm3
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
drp.itm3
 print \n$" buried!":close #2
 if left$(n$,10)="BOOBY TRAP" print \"DISARM LETTER IS '"right$(n$,1)"'"
 i$="2"+str$(a):gosub bury.add
 i$="Bury "+n$:gosub add.lg
 goto dig.b

bury.add
; first digit=type:1=food,2=item,3=gold
 if xx$="N" zw$=i$
 if xx$="S" zx$=i$
 if xx$="E" zy$=i$
 if xx$="W" zz$=i$
 if xx$="C" zv$=i$
 return

wr.bury
 position #1,30,cr
 print #1,zw$,zx$,zy$,zz$,zv$:close #1
 return

fnd.item
 dy$=dw$+"items":rl=30:d=val(xu$):gosub rd.file
 if left$(d$,10)="BOOBY TRAP":gosub booby:goto fnd.itm2
 yz=instr("|",d$):if yz>0 d$=left$(d$,yz-1)
 a$=right$("000"+xu$,3)+",":i$=xi$+ai$
 if (instr(a$,i$)) or (instr(a$,xt$)) then return
fnd.itm2
 print \"YOU FIND "d$",";
 input " GET IT? Y/n:"i$:if i$="N" pop:goto dig.b
 if pt<9 print \"You are too sickly to carry it!":pop:goto dig.b
 if xi>(zo-1) print \"You can carry no more Items.":pop:goto dig.b
 xv$=d$
 xi=xi+1:a$=right$("000"+str$(d),3)+",":xi$=xi$+a$
 if d=73 print \"You feel funny.."
 i$="it":if right$(d$,1)="S" i$="'em"
 print \"Got "i$".."
 a$=right$("000"+str$(d),3)+","
 if xt<60 then xt=xt+1:xt$=xt$+a$:return
 xt$=mid$(xt$,5)+a$
 i$="Got "+d$:gosub add.lg
 return
 
fnd.gold
 g2=val(xu$)*10:xv$=str$(g2)+" gold!"
 print \"You find "xv$;
 input " Take it? Y/n:"i$:if i$="N" pop:goto dig.b
 gosub add.gold:g1=gh:g2=gl:gosub prt.gold
 i$="Got "+xv$:gosub add.lg
 return

rd.file
 open #2,dy$:position #2,rl,d:input #2,cb$\d$\f
 dp$=left$(d$,1):d$=mid$(d$,3):f=f mod 10
 if cb$<>"1" then d$="":d=0:f=0
 close #2:return

booby
 print \\\\"ACK! A BOOBY TRAP!!!":for vu=1 to 2000
 print \"You have 1 chance in about 10 seconds to press the disarm key!"\
 vu=0:vy=10:print vy
disarm.a
 zz=key(0):if zz goto disarm.b
 vu=vu+1:if vu<62 goto disarm.a
 if vy<2 print \"TOO LATE!":goto kaboom
 vy=vy-1:print vy:vu=0:goto disarm.a
disarm.b
 free:i$=chr$(zz):print i$
 if instr(i$,right$(d$,1)) print \"DISARMED!":return
 print \"WRONG!"
kaboom
 dy$=dx$+"battle.log":create dy$:open #2,"battle.log":append #2
 print #2, left$(date$,6)yr$" "time$"- KABOOM!"
 print #2, n1$" SET OFF A BOOBY TRAP"
 print \\\\\\"KABOOOOOM!!!"\\\\\
 print #2, "IN "ww$"!"
 print #2,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close #2
 free:xv$="*"
 pop:i$=rnd$:zz=random(5)+6:print \"You take "zz" damage"
 hp=hp-zz:if hp>0 return
 print \"Opps..."
 pop:i$="":gosub bury.add:gosub wr.bury
 hp=0:xn=sn:sn=0:z=19
 i$="dead2":goto lnk.msc6
;
linkwin
 z=18:hp=0:xn=sn:sn=0:i$="dead2":goto lnk.msc6
advent
 dy$=dz$+"spur.main":link dy$
main.ret
 dy$=dz$+"spur.main":link dy$,"return"
lnk.sub
 dy$=dz$+"spur.sub":link dy$
lnk.msc6
 dy$=dz$+"spur.misc6":link dy$
; 
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:i$="QUIT":goto lnk.sub
 return

drop.1
 pop
dropped
 i$="SPUR.MISC7":dy$=ds$+"spur.logon":link dy$,"quit3"
;
add.lg
 open #2,"a:add.log":append #2
 print #2,"Spur.misc7: "i$" @"time$
 close #2:return
;
compile
 print "Compiled..":if un=1 link "k:system.seg"
comp.ck
 print "ok":return
;

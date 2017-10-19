
;     Spur.Shop

 public main1
 public return
 public compile

main
 if un=1 print "spur.shop--";:gosub comp.ck
 gosub set.pa
 if cl=7 print \"[Attempt at entering shop]:"\'A sign on the door says:

"Shoppe closed due to lack of interest on this level.  Look for our stores in
levels 1-5!!!"'\:goto exit
 print \"Entering the SPUR shoppe area"\
 
main1
 on nocar goto dropped
 free:gosub tim.chk:if (ev-ex)<120 print \"Dusk approaches..."
 yz=ev-ex
 i$=str$(yz-((yz/60)*60)):i$=right$("00"+i$,2)
 zz$="["+str$(yz/60)+":"+i$+"]"
 print \zz$;" Lvl "cl", Shoppe";:input " (?=Menu):"i$
 if i$="SCHOOL" dy$=ds$+"spur.misc2":link dy$
 if i$="LOCKER" dy$=dz$+"spur.misc6":link dy$
 if left$(i$,2)="EL" goto elevator
 if i$="?" f$=dx$+"shop.menu":gosub show.file:goto main1
 if left$(i$,1)="J" goto clan
 if i$="W" goto armory
 if i$="B" goto bank
 if i$="V" goto wizard
 if left$(i$,1)="S" dy$=dz$+"spur.misc5":link dy$,"show2"
 if left$(i$,1)="I" dy$=dz$+"spur.sub":link dy$,"show3"
 if i$="O" i$="AMMO":dy$=dz$+"spur.misc5":link dy$
 if left$(i$,1)="Q" goto quit0
 if i$="T" goto termin
 if i$="P" goto pawn.shp
 if i$="H" then f$=dx$+"spur.help":gosub show.file:goto main1
 if i$="C" then f$=dx$+"spur.winners":gosub show.file:goto main1
 if i$="A" then f$=dx$+"spur.log":gosub show.file:goto main1
 if i$="L" gosub plr.list:goto main1
 if (i$="E") or (i$="U") goto exit
 if i$="G" goto general
 if (i$="@I") and ((info(5)) or (un=dm)) then dy$=ds$+"spur.sysop":link dy$
 if instr(" ",i$) print \"There was a space in your command":goto main1
 print \"Huh?":goto main1
;
exit
 cr=1:if cl=6 cr=584
 dy$=dz$+"spur.misc":i$="travel3":di=7:link dy$,"misc"
;
plr.list
 gosub plr.sub:return

plr.sub
 print \"List of players in Game"
 input @2 \"Match letters or CR for all: "i$
 x=1:dy$=dx$+"spur.users"
 a=1:dr$=dx$+"room.level"+str$(a):ready dr$
 open #1,dy$
 gosub plrlist5
 
plrlist1
 position #1,130,x
 input #1,n$,l1,b1,b2,b3,b4
 input #1,n1,n2,n3,n4,n5,n6
 input #1,g1,g2,f,f,f,f,f,f,f1,f2,m,m1
 setint(1)
 if (not l1) goto plrlist4
 if not instr(i$,n$) goto plrlist4
 if x=pn then b2=cl:lo$="Shoppe":m=mm:f2=mk:b4=hp:f1=ep:n1=ps:n2=pt:n3=pi :n4=pe:n5=pw:n6=pd:g1=gh:g2=gl:goto plrlist2
 if b3=0 then lo$="Shoppe":goto plrlist2
 if a<>b2 then dr$=dx$+"room.level"+str$(b2):ready dr$:a=b2
 input #msg(b3),lo$,f
 setint(1)
 
plrlist2
 zw$=left$(n$,1):yz=val(zw$):zr=instr(zw$,"ABBCCCDDE"):if zr then yz=zr-1
 zw$=": Civy"
 if (yz=1) or (yz=2) zw$="-OUTLAW"
 if (yz=3) or (yz=4) zw$=" -}----"
 if (yz=6) or (yz=7) zw$=": \|/"
 if (yz=8) or (yz=9) zw$=": ==[]"
 n$=mid$(n$,2)
 print right$("  "+str$(b1),3)"  ";
 print left$(n$+"               ",14);
 vy=instr("|",lo$)
 if vy then if not instr("\|/",lo$) then lo$=left$(lo$,vy-1)
 print right$("  "+str$(b2),3)"-"lo$;zw$
 
plrlist4
 x=x+1:if (x>np) or (key(1)) close:return
 goto plrlist1

plrlist5
 print \\" #   Adventurer      Dungeon Level/Room"
 print   "---  --------------- ------------------"
 return
;
armory
 print \'
Wouldst thou be interested in
[P]rotection or [W]eaponry? ';
 input @2 i$
 if i$="P" goto protect
 if i$="W" goto weapons0
 print \"Good journey to you!":goto main1

weapons0
 dy$=dx$+"weapons":open #1,dy$
 position #1,34,0:input #1,nw
weapons
 print \"Speak "n1$"!"
 input @2\"Wouldst Thou [B]uy or [S]ell? "i$
 if i$="B" goto buy.wep
 if i$="S" goto sel.wep
 print \"Bye. Come again!":goto wp.exit
;
buy.wep
 if xw<6 goto buy1
 print \'
I am sorry, but you have no room for
more weapons.  Do you wish to sell a
weapon? ';:input @0 i$
 if i$<>"Y" goto wp.exit
 goto sel.wep
 
buy1
 wr$="":print \'
Excellent! Choose Thee well!! From mine hands I have crafted this list of fine
weapons!'
buy2
 input @2\"Your Choice (?=List): "i$
 if i$="?" gosub wep.list:goto buy2
 if i$="" or i$="Q" goto weapons
 x=val(i$):if (x<1) or (x>wc) goto buy2
 position #1,34,x
 input #1,cb$:if cb$<>"2" print \"Weapon not available for sale!":goto buy2
 input #1,w$\s,d,v\wa:w$=mid$(w$,4)
 print \"You choose the "w$" for "v" gold,"
 input @2"Do you wish to try it out first? "i$:if instr("Y",i$) gosub try.wep
 xa$=right$("000"+str$(x),3)+","
 a=instr(xa$,xw$)
 if a print \"I see that you already possess this weapon.  You may NOT buy another.":goto buy2
 input @0\"Buy it? "i$:if i$<>"Y" goto buy2
 g3=gh:g4=gl:g1=0:g2=v:gosub chk.gold
 if a=0 print \"Sorry to say, but you do not have"\"enough gold at hand":goto buy2

buy4
 xw=xw+1:xw$=xw$+xa$
 if x<=10 goto buy5
 nw=nw-1
 position #1,34,x:print #1,0
buy5
 print \"DONE!"
 if wa=8 print \"Buy ammo in O)lly's Ammo shop..."
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold:print \"You now have "gd$" in gold."
 if xw>5 print \"No more room for weapons!":goto buy.wep
 goto buy2
;
try.wep
 print \"You try out the "w$
 print \"Weapon class: ";
 if wa=2 print "Hack/Slash/Bash.":print "Best Targets: SWIFT, Small, Short";
 if wa=3 print "Poke/Jab.":print "Best Targets: HUGE, SWIFT,"; 
 if wa=5 print "Pole/Ranged.":print "Best Targets: MAN SIZED, Big, Short";
 if wa=8 print "Projectile (+10% surprise).":print "Best Targets: HUGE, Large";
 if wa=9 print "Proximity.":print "Best Targets: Anybody..";
 print \"Required dex: "s+4
 if s+4>pd print "Not dextrous enough to use this weapon!"\
 n$=w$:gosub special:dy$=dx$+"weapons":open #1,dy$
 zz=s:if xp>1 then s=((xp+2)*s)/3
 print " Base damage: "d
 zs=((s+1)-zz)+yz+yx
 print "  Your skill: "zs
 print " Ease of use: "10-zz
 print \"You hand the "w$" back.":return
;
special
 i$="SPECIAL":dy$=ds$+"spur.weapon":link dy$
;
sel.wep
 wr$=""
 x=0:if xw=0 print \"No weapons.":goto weapons
 print \"Sell which weapon:"\\
 for i=1 to xw:y=(i*4)-3:x=val(mid$(xw$,y))
 position #1,34,x:input #1,cb$\w$:w$=mid$(w$,4)
 print i". "w$
 next
 
 input @2\"Which : "i$:if i$="" or i$="Q" goto weapons:else x=val(i$)
 if (x<1) or (x>xw) goto sel.wep
 y=(x*4)-3
 x=val(mid$(xw$,y))
 if x>57 print \"'I don't know what that is, and I don't want it!'":goto sel.wep
 if zy=1 print "# weapons="nw:input "new value="nw
 if nw>24 print \"My weapons inventory is full.":goto weapons
 position #1,34,x:input #1,cb$\w$\s,d,v
 a=v/16:l=a*pi:if l=>v then l=a*14
 if pi=0 then l=a
 if cb$="2" then l=l/2:goto sel.wep1
 print \"I will give you "l" gold for it."\
 input @0 "Doest Thou accept MY offer? "i$
 if i$<>"Y" goto weapons
 vw=25:if vk<25 vw=vk
 if x=17 print \"Hah! Shame on you, I will not buy this weapon!!":vk=vk-vw :goto weapons
 print \"Good!":g2=l:gosub add.gold
 xw=xw-1
 if xw=0 then xw$="":goto wr.weap
 l=len(xw$)
 if y=1 then xw$=mid$(xw$,5):goto wr.weap
 if (y+4)>l then xw$=left$(xw$,y-1):goto wr.weap
 xw$=left$(xw$,y-1)+mid$(xw$,y+4)
 
wr.weap
 nw=nw+1
 position #1,34,x:print #1,"2"
 goto weapons

sel.wep1
 if l<1 l=1
 print \"'I already have a "mid$(w$,4)","
 print "but I suppose I could give you "l
 input @2 "gold. What say you?' Y/N? "i$:if i$<>"Y" goto weapons
 print \"'Sold!' He throws it into the back room."
 g2=l:gosub add.gold
drp.wpn
 l=len(xw$):a=val(mid$(xw$,y))
 xw=xw-1:if xw=0 then xw$="":goto drp.wpn2
 if y=1 then xw$=mid$(xw$,5):goto drp.wpn2
 if (y+4)>l then xw$=left$(xw$,y-1):goto drp.wpn2
 xw$=left$(xw$,y-1)+mid$(xw$,y+4)
drp.wpn2
 cb$="2":if a>10 then cb$="1"
 position #1,34,a
 print #1,cb$
 wr$="":goto weapons
;
wep.list
 print \'
The Weapons Master leads you to a table
where his handcrafted weapons lay....'\
 b=0:x=1:print
w.list2
 position #1,34,x
 input #1,cb$\w$\s,d,v
 setint(1)
 if cb$<>"2" goto w.list3
 w$=mid$(w$,4)
 print right$("  "+str$(x),2)". "left$(w$+"               ",15)"- "right$("    "+str$(v),4)" Gold"
 b=b+1
w.list3
 x=x+1:if (b=nw) or (x>wc) return
 if (key(1)) return
 goto w.list2
 
wp.exit
 position #1,34,0
 print #1,nw
 close:goto main1
;
protect
 print \'The Weapons Master greets you and says:

"Welcome, Adventurer!! Choose from this
 fine list of protection for your long
 journey!"'\

 dy$=dw$+"items":open #1,dy$
 x=1
pro1
 position #1,30,x:input #1,cb$:if cb$="*" goto pro1a
 input #1,it$\it:it=it*100:it$=left$(mid$(it$,3)+"                   ",20)
 print right$("   "+str$(x),3)". "it$" - "right$("     "+str$(it),5)" Gold"
pro1a
 x=x+1:if x>5 goto pro2
 goto pro1
pro2
 if xi>zo-1 print \"You have no room in your pack!":close:goto main1
 input @2\"Your Choice (?=List): "i$:if i$="" or i$="Q" close:goto main1
 if i$="?" then x=1:print:goto pro1
 x=val(i$):if (x<1) or (x>5) goto pro2
 position #1,30,x:input #1,cb$:if cb$="*" goto pro2
 input #1,it$\it:it=it*100
 g3=gh:g4=gl:g1=0:g2=it:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto pro2
 a$=mid$(it$,3)
 print \"You choose "a$" for "it" gold? ";:input @0 i$
 if i$<>"Y" goto pro2
 xa$=right$("000"+str$(x),3)+","
 print \"Done!":g2=it:gosub sub.gold
 xi=xi+1:xi$=xi$+xa$:goto pro2

general
 print \'The Stores Master greets you and says:

"Welcome, Adventurer!! Have you come to
 buy goods for your journey through the
 Land?" ';:input @0 i$
 if i$<>"Y" goto main1
 dy$=dw$+"stores":open #1,dy$
 print \"Good!! What will you have today?"\
 x=1
gen1
 position #1,26,x:input #1,cb$:if cb$="*" goto gen1a
 input #1,gs$\gs:setint(1)
 gs$=mid$(gs$,3)
 print right$("   "+str$(x),3)". "left$(gs$+"                    ",18)" - "right$("     "+str$(gs),5)" Gold"
gen1a
 x=x+1:if (x>10) or (key(1)) goto gen2
 goto gen1
gen2
 if xf>(zo-1) print \"You have no room in your pack!":close:goto main1
 input @2\"Your Choice (?=List): "i$:if i$="" or i$="Q" close:goto main1
 if i$="?" then x=1:print:goto gen1
 x=val(i$):if (x<1) or (x>10) goto gen2
 position #1,26,x:input #1,cb$:if cb$="*" goto gen2
 input #1,gs$\gs
 g3=gh:g4=gl:g1=0:g2=gs:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto gen2
 a$=mid$(gs$,3)
 print \"You choose "a$" for "gs" gold? ";:input @0 i$
 if i$<>"Y" goto gen2
 xa$=right$("000"+str$(x),3)+","
 a=instr(xa$,xf$):if a print \"I see you already have "a$"."\"You may buy no more.":goto gen2
 print \"Done!":g2=gs:gosub sub.gold
 xf=xf+1:xf$=xf$+xa$:goto gen2

bank
 print \"[ Ye Bank of SPUR ]"
 g1=bh:g2=bl:gosub prt.gold:print \"In Account :"gd$" gold"
 g1=gh:g2=gl:gosub prt.gold:print \"In hand    :"gd$" gold"
 input @2\"[D]eposit, [W]ithdraw, [T]ransfer? "i$:if i$="" or i$="Q" goto main1
 if i$="W" goto bank3
 if i$="T" then if xp<2 i$="Must be at least level 2 to transfer gold":print \i$: gosub add.lg:goto bank
 if i$="T" goto bank6
 if i$<>"D" goto bank
 input @2 \"[ Deposit ] - How much? "gd$:if gd$="" goto main1
 gosub val.gold:if a=0 print \"Invalid amount!":goto bank
 gosub spl.gold:g3=gh:g4=gl:gosub chk.gold:if a=0 print \"You don't have that much!":goto bank
 gosub put.gold
 goto bank5
bank3
 input @2 \"[ Withdraw ] - How much? "gd$:if gd$="" goto main1
 gosub val.gold:if a=0 print \"Invalid amount!":goto bank
 gosub spl.gold:g3=bh:g4=bl:gosub chk.gold:if a=0 print \"You don't have that mu‡h!":goto bank
bank4
 gosub tak.gold
bank5
 g1=bh:g2=bl:gosub prt.gold:print \"In Account: "gd$" gold"
 g1=gh:g2=gl:gosub prt.gold:print "In hand   : "gd$" gold"\\:goto main1
bank6
 input@2 \"[ Transfer ]-player number or L)ist? :"i$:
 if i$="" or i$="Q" goto bank
 if i$="L" gosub plr.sub:goto bank6
 x=val(i$):if (x>np) or (x=0) print \"Number from 1 to "np", L or Q please!":goto bank6
 gosub rd.ply2:if zz$="" goto bank6
 print \"Give to "zz$"? Y/N";:input @2 " "i$:if i$<>"Y" goto bank6
bank7
 input @2 \"Give how much? "gd$:if gd$="" goto bank6
 gosub val.gold:if a=0 print \"Invalid amount!":goto bank7
 gosub spl.gold:g3=bh:g4=bl:gosub chk.gold:if a=0 print \"You don't have that much!":goto bank7
 i$="Transferred "+gd$+" gold to "+zz$:gosub add.lg
 gosub put.gld2:gosub wr.ply2
 print \"Gold transferred to "zz$:goto bank

wizard
 if xs=10 goto wiz2b
 if pc>2 then if xs>5 goto wiz2b
 dy$=dw$+"spells"
 print \'
You enter the cave of the Wizard, a
dis-embodied voice asks.....

"Are you here to learn a spell"? ';
 input @0 i$:if i$<>"Y" print \"Return when you are ready.":goto main1
 print \'
A scroll appears before you, and the
voice pronounces...'\\
 x=1:open #1,dy$
wiz1a
 position #1,40,x
 input #1,cb$\q$,q2$,q3,q4
 setint(1)
 if (cb$="*") or (cb$="") goto wiz1b
 print right$("  "+str$(x),2)" "left$(q$+"                      ",20)"-"right$("    "+str$(q4),4)" Gold"
wiz1b
 x=x+1:if (x>sc) or (key(1)) close:goto wiz1c
 goto wiz1a
wiz1c
 print \"Choose carefully your spells to learn."\
 if pc=1 print "Psst! Fellow wizard!! Half price for you!"
 if pc=2 print "Psst! Fellow Adept! 2/3 price for you!"
wiz2
 input @2\"Learn which spell? (?=List): "i$
 if i$="?" print \md$\:x=1:open #1,dy$:goto wiz1a
 if i$="" or i$="Q" goto main1:else x=val(i$)
 i$="'Sorry, this spell for "
 if x=19 then if pc>1 print i$"Wizards only'":goto wiz2
 if x=18 then if pc<>2 print i$"Druids only'":goto wiz2 
 if (x<1) or (x>sc) goto wiz2
 
 open #1,dy$:position #1,40,x
 input #1,cb$\q$,q2$,q3,q4:close
 if cb$="*" print \"I do not know that spell.":goto wiz2
 if pc=1 q4=q4/2
 if pc=2 q4=q4*2:q4=q4/3
 print \"You have chosen "q$" for "q4" gold"
 input @0\"Is this correct? "i$
 if i$<>"Y" goto wiz2
 g3=gh:g4=gl:g1=0:g2=q4:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto wiz2
wiz2b
 if xs>5 then if pc>2 print'
Sorry, Non - Adepts can only learn  six spells..'\:goto main1
 if xs=10 print'
I am sorry but ye have already  learned ten spells.'\:goto main1
wiz3
 print \"Teaching spell..";
 for a=1 to 50
 if not (a mod 5) print ".";
 next
 gosub sub.gold:if pc<3 print"Your calling makes learning simple!":goto wiz4
 if pi<10 print \"Thy intelligence may  hinder thee  from learning this spell."\
 b=0:if (pr=2) or (pr=7) or (pr=8) then b=3
 zz$=rnd$:a=random(25):a=a+5+b
 if a>pi then zz$=rnd$:if random(10)<3 print "After much study..":goto wiz4
 if a>pi then print \"'Alas! My efforts to teach thee were in vain, maybe if thee were smarter..'"
 if b>0 then if a>pi print "'Your kind never did make good wizards,' the voice sniffs.."
 if a>pi goto wiz2
wiz4
 print \"Spell taught, use it wisely, for it may only be used ONCE!"
 xs=xs+1
 a$=right$("000"+str$(x),3)+","
 xs$=xs$+a$
 goto wiz2
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
 
put.gold
 bh=bh+g1
 bl=bl+g2:if bl=>10000 then bl=bl-10000:bh=bh+1
 if g2>gl then gl=gl+10000:gh=gh-1
 gh=gh-g1:gl=gl-g2
 return
 
tak.gold
 if g2>bl then bl=bl+10000:bh=bh-1
 bh=bh-g1:bl=bl-g2
 gh=gh+g1
 gl=gl+g2:if gl=>10000 then gl=gl-10000:gh=gh+1
 return
 
prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
 
spl.gold
 gd$=right$("00000000"+gd$,9)
 g1=val(left$(gd$,5)):g2=val(right$(gd$,4))
 if g1<0 g1=0:g2=0:gd$="":print \"Number too large!"
 return
 
chk.gold
 a=0
 if g3>g1 then a=1:return
 if (g3=g1) and (g4=>g2) then a=1:return
 return
 
val.gold
 l=len(gd$)
 for i=1 to l:a=instr(mid$(gd$,i,1),"0123456789")
 if (not a) then i=l:next:return
 next:return
 
set.pa
 pa=ps+pd+pt+pi+pw+pe:pa=pa mod 10
 return
 
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto quit1
 return

termin
 print \"Terminate Connection"\\"Are you sure? ";
 input @0 " "i$:if i$<>"Y" goto main1
 goto dropped1

quit0
 input @0\"Leave the Land of SPUR ? "i$
 if i$<>"Y" goto main1
quit1
 dy$=ds$+"spur.logon"
 link dy$,"quit1"

dropped
 i$="SPUR.SHOP"
dropped1
 dy$=ds$+"spur.logon"
 link dy$,"quit3"
;
rd.ply2
 zz$="":dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,cs,ct,ci,ce,cw,cd
 input #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 input #1,p2$:close:if ys>0 zz$=mid$(n2$,2):else print \"No such player"
 return
;
wr.ply2
 dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,x
 print #1,n2$,ys,yp,yl,yr,yh
 print #1,cs,ct,ci,ce,cw,cd
 print #1,ya,yb,yc,yd,ye,yf,yg,yi,yj,yk,ym,yn
 print #1,p2$
 close
 return
;
put.gld2
 yc=yc+g1
 yd=yd+g2:if yd=>10000 then yd=yd-10000:yc=yc+1
 if g2>bl then bl=bl+10000:bh=bh-1
 bh=bh-g1:bl=bl-g2
 return
;
pawn.shp
 if instr("*PS",ys$) print \"Pawn shoppe closed for today!":goto main1
 if len(ys$)<240 ys$=ys$+"*PS"
pawn.p
 print \"Ye Olde Pawn Shoppe"
 input "[S]ell, [Q]uit :"i$:if i$="Q" print \"Ok-fine":goto main1
 if i$<>"S" goto pawn.p
 if xi=0 print "No Items!!":goto main1
 print \"You are carrying:"\
 dy$=dw$+"items"
 open #1,dy$
 for x=1 to xi
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm>0 n$=left$(n$,zm-1)
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xi
 next:print:close
 
 input @2\"Sell which item number? "a$:x=val(a$):if a$="" goto pawn.p
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto pawn.p
 l=len(xi$):y=(x*4)-3:a=val(mid$(xi$,y))
pwn.1
 open #1,dy$
 position #1,30,a
 input #1,cb$\it$\g2
 close:g2=g2*10:zm=instr("|",it$):if zm>0 it$=left$(it$,zm-1)
 if a=67 then if mid$(zu$,2,1)="1" print \"Can't, you are USEing it!":goto pawn.p
 if (a=73) or (a=76) print \"I don't want it!":goto pawn.p
 print \"I'll give ya "g2" gold for the "mid$(it$,3)","
 input "Hoky-doky? "i$:if i$<>"Y" print \"Sniff..":goto pawn.p
 print \"SOLD! Ya-betcha!":gosub add.gold
drp.itm2
 xi=xi-1:if xi=0 then xi$="":goto pawn.p
 if y=1 then xi$=mid$(xi$,5):goto pawn.p
 if (y+4)>l then xi$=left$(xi$,y-1):goto pawn.p
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
 goto pawn.p
;
clan
 if flag(15) print \"Involuntary OUTLAWS may not change!":goto main1
 xu=1000:zz$="Change from Civy."
 if vv>0 xu=2000:zz$="Change from Outlaw."
 if vv>2 zz$="Desert a Guild!"
 f$=dx$+"CLANS":gosub show.file
clan1
 print \"There is a fee of "xu" gold":print "to "zz$
 if vv>2 print "(Plus 400 e.p. honor penality!)"
 input @0 \"Which? (1-5,Q,?) :"i$
 if i$="Q" print \"No change..":goto main1
 if not instr(i$,"12345") goto clan
 g3=gh:g4=gl:g1=0:g2=xu:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto main1
clan2
 vw=100:if vw>vk vw=vk
 if vv>2 print\"(100 point honor penality for deserting your Guild!)":vk=vk-vw
 z=val(i$)
 if z=1 vv=6:flag(3)=0:flag(13)=0:print\"Welcome to the Claw! \|/":print \"Guild sub: B9"
 if z=2 vv=3:flag(6)=0:flag(13)=0:print\"Welcome to the Sword! -}----":print\"Guild sub: B2"
 if z=3 vv=8:flag(3)=0:flag(6)=0:print\"Welcome to the Fist! ==[]":print \"Guild sub: B29"
 if z=4 vv=0:print\"Ok, your status is: Civy"
 if z=5 vv=1:print\"Ok, you're an OUTLAW!"
 if z>3 flag(3)=0:flag(6)=0:flag(13)=0
 if (z<1) or (z>5) print \"Enter 1 thru 5 please.":goto clan1
 zt$="REJOINED "
 if z<4 then if flag(3)+flag(6)+flag(13)=0 zt$="JOINED "
 if zt$="JOINED " print \"Access to the Guild sub & HQ is given by the GuildMaster.":else if z<4 print \"Welcome back! You now have access to HQ!"
 print \"AutoDuel is OFF"\"Use FL in dungeon to set your FOLLOW status"
 gosub sub.gold:g1=gh:g2=gl:gosub prt.gold
 print "(Writing in News log..)"
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$": "zz$
 print #1, n1$" (#"un", "a1$")";
 if z=1 print #1, \zt$"MARK OF THE CLAW. \|/"
 if z=2 print #1, \zt$"MARK OF THE SWORD. -}----"
 if z=3 print #1, \zt$"THE IRON FIST. ==[]"
 if z=4 print #1, " IS NOW A CIVILIAN"
 if z=5 print #1, " IS NOW AN OUTLAW"
 if z<4 then if zt$="JOINED " print #1,\"  **[ WAITING FOR GUILD ACCESS ]**"
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 close:goto main1
;
elevator
 if cl>5 print \"The elevator doesn't come here!":goto main1
 dy$=dx$+"elevator":open #1,dy$
 position #1,pn,10:input #1,xu$:close
 if un=1 print \"xu$='"xu$"'; pn="pn
elev.1
 input @2\"ELEVATOR: enter combination ->"i$
 if i$="" or i$="Q" goto main1
 if i$<>xu$ print \"Wrong!":goto elev.1
 input @2\"LEVEL: [1] [2] [3] [4] [5]->"i$
 a=val(i$):if (a<1) or (a>5) print \"It doesn't go there!":goto main1
 print "Ok, here we go! New level :"a:cl=a:goto main1
;
return
 return
;
add.lg
;.. i$=log message
 open #1,"a:add.log":append #1
 print #1,"[Spur.shop] "i$" @"time$:close:return
;
compile
 if un=1 print \"compiled":link "k:system.seg"
comp.ck
 print \" ok":return
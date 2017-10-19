;
;     Spur.Shop

 public main1
 public return
 public compile

main
 if un=1 print "spur.shop--";:gosub comp.chk
 cl=6:gosub set.pa
 print \"Entering the ships stores area.."\
 
main1
 on nocar goto dropped
 free:gosub tim.chk:if (ev-ex)<120 print \"Dusk approaches..."
 yz=ev-ex
 i$=str$(yz-((yz/60)*60)):i$=right$("00"+i$,2)
 zz$="["+str$(yz/60)+":"+i$+"]"
 print \zz$;" SHIPS STORES";:input " (?=Menu):"i$
 if i$="?" f$=dx$+"ship.menu":gosub show.file:goto main1
 if i$="J" or i$="JOIN" goto clan
 if i$="W" goto armory
 if i$="B" goto bank
 if i$="V" print \"(No magic shop on the ship..)":goto main1
 if (i$="S") or (left$(i$,4)="STAT") i$="STAT2":dy$=dz$+"spur.misc5":link dy$
 if (i$="I") or (left$(i$,3)="INV") i$="INV2":dy$=dz$+"spur.sub":link dy$
 if (i$="Q") or (i$="QUIT") goto quit0
 if i$="T" goto termin
 if i$="P" goto pawn.shp
 if i$="H" then f$=dx$+"spur.help":gosub show.file:goto main1
 if i$="C" then f$=dx$+"spur.winners":gosub show.file:goto main1
 if i$="A" then f$=dx$+"spur.log":gosub show.file:goto main1
 if i$="L" gosub plr.list:goto main1
 if i$="E" then dy$=dz$+"spur.misc":i$="travel3":cr=1:di=7:link dy$,"misc"
 if i$="G" goto general
 if i$="SALVAGE" goto salvage
 if i$="SCHOOL" print \"(Inactive here)":goto main1
 if left$(i$,2)="TR" goto elevator
 if (i$="}") and ((info(5)) or (un=dm)) then dy$=ds$+"spur.sysop":link dy$
 if instr(" ",i$) print \"There was a space in your command":goto main1
 print \"Huh?":goto main1
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
 gosub prt.gold
 print right$("  "+str$(b1),3)"  ";
 print left$(n$+"               ",14)"  ";
 print "$"gd$"   ";
 vy=instr("|",lo$)
 if vy then if not instr("\|/",lo$) then lo$=left$(lo$,vy-1)
 print right$("  "+str$(b2),3)"-"lo$;zw$
 
plrlist4
 x=x+1:if (x>np) or (key(1)) close:return
 goto plrlist1

plrlist5
 print \\" #   Adventurer       Gold/Hand   Dungeon Level/Room"
 print "---  ---------------  ----------  ----------------------------"
 return
;
armory
 print \'
Entering Ships armory:
[P]rotection, [W]eapondry, [A]mmo? ';
 input @2 i$
 if i$="P" goto protect
 if i$="W" goto weapons0
 if i$="A" goto ammo
 print \"You leave the armory!":goto main1

weapons0
 dy$=dx$+"weapons":open #1,dy$
 position #1,34,0:input #1,nw
;
buy.wep
 if xw>5:print \"You can carry no more weapons..":goto wp.exit
buy1
 wr$="":print \"You look at the weapons rack, it is mostly empty.."
buy2
 input @2\"Your Choice (?=List): "i$
 if i$="?" gosub wep.list:goto buy2
 if i$="" or i$="Q" goto wp.exit
 x=val(i$):if (x<58) or (x>60) print \"Enter from 58 to 60, or Q":goto buy2
 position #1,34,x
 input #1,cb$
 input #1,w$\s,d,v\wa:w$=mid$(w$,4)
 print \"You choose the "w$" for "v" gold,"
 input @2"Do you wish to try it out first? "i$:if instr("Y",i$) gosub try.wep
 xa$=right$("000"+str$(x),3)+","
 a=instr(xa$,xw$)
 if a print \"You already have this weapon. You may NOT buy another.":goto buy2
 input @0\"Buy it? "i$:if i$<>"Y" goto buy2
 g3=gh:g4=gl:g1=0:g2=v:gosub chk.gold
 if a=0 print \"You do not have enough gold.":goto buy2

buy4
 xw=xw+1:xw$=xw$+xa$
buy5
 print \"YOU INSERT GOLD IN THE SLOT"
 print \"Buy ammo in A)mmo locker..."
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
 print \"You hand the "w$" back to the robot..":return
;
special
 i$="SPECIAL2":dy$=ds$+"spur.weapon":link dy$
;
wep.list
 print \"The weapons here are:"
 b=0:x=58:print
w.list2
 position #1,34,x
 input #1,cb$\w$\s,d,v
 setint(1)
 w$=mid$(w$,4)
 print right$("  "+str$(x),2)". "left$(w$+"               ",15)"- "right$("    "+str$(v),4)" Gold"
 b=b+1
w.list3
 x=x+1:if (b=nw) or (x>wc) return
 if (key(1)) return
 goto w.list2
 
wp.exit
 close:goto armory
;
protect
 print \"You go to the armor rack.."

 dy$=dw$+"items":open #1,dy$
 x=113
pro1
 position #1,30,x:input #1,cb$:if cb$="*" goto pro1a
 input #1,it$\it:it=it*100:it$=left$(mid$(it$,3)+"                   ",20)
 print right$("   "+str$(x),3)". "it$" - "right$("     "+str$(it),5)" Gold"
pro1a
 x=x+1:if x>116 goto pro2
 goto pro1
pro2
 if xi>zo-1 print \"You have no room in your pack!":close:goto armory
 input @2\"Your Choice (?=List): "i$:if i$="" or i$="Q" close:goto armory
 if i$="?" then x=1:print:goto pro1
 x=val(i$):if (x<113) or (x>116) print \"Enter from 113 to 116 or Q":goto pro2
 position #1,30,x:input #1,cb$:if cb$="*" goto pro2
 input #1,it$\it:it=it*100
 g3=gh:g4=gl:g1=0:g2=it:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto pro2
 a$=mid$(it$,3)
 print \"You choose "a$" for "it" gold? ";:input @0 i$
 if i$<>"Y" goto pro2
 xa$=right$("000"+str$(x),3)+","
 print \"You insert gold into the slot.":g2=it:gosub sub.gold
 xi=xi+1:xi$=xi$+xa$:goto pro2

general
 print \"You go to the rations despenser,";
 dy$=dw$+"stores":open #1,dy$
 print "and look inside.."\
 x=70
gen1
 position #1,26,x:input #1,cb$:if cb$="*" goto gen1a
 input #1,gs$\gs:setint(1)
 gs$=mid$(gs$,3)
 print right$("   "+str$(x),3)". "left$(gs$+"                    ",18)" - "right$("     "+str$(gs),5)" Gold"
gen1a
 x=x+1:if (x>75) or (key(1)) goto gen2
 goto gen1
gen2
 if xf>(zo-1) print \"You have no room in your pack!":close:goto main1
 input @2\"Your Choice (?=List): "i$:if i$="" or i$="Q" close:goto main1
 if i$="?" then x=70:print:goto gen1
 x=val(i$):if (x<70) or (x>75) print \"Enter 70 to 75, or Q":goto gen2
 position #1,26,x:input #1,cb$:if cb$="*" goto gen2
 input #1,gs$\gs
 g3=gh:g4=gl:g1=0:g2=gs:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto gen2
 a$=mid$(gs$,3)
 print \"You choose "a$" for "gs" gold? ";:input @0 i$
 if i$<>"Y" goto gen2
 xa$=right$("000"+str$(x),3)+","
 a=instr(xa$,xf$):if a print \"You already have "a$"."\"You may buy no more.":goto gen2
 print \"You insert gold in the slot.":g2=gs:gosub sub.gold
 xf=xf+1:xf$=xf$+xa$:goto gen2

bank
 print \"[ Ships Bank ]"
 g1=bh:g2=bl:gosub prt.gold:print \"In Account :"gd$" gold"
 g1=gh:g2=gl:gosub prt.gold:print \"In hand    :"gd$" gold"
 input @2\"[D]eposit, [W]ithdraw, [T]ransfer? "i$:if i$="" or i$="Q" goto main1
 if i$="W" goto bank3
 if i$="T" goto bank6
 if i$<>"D" goto bank
 if zy=1 print "bh="bh
 input @2 \"[ Deposit ] - How much? "gd$:if gd$="" goto main1
 gosub val.gold:if a=0 print \"Invalid amount!":goto bank
 gosub spl.gold:g3=gh:g4=gl:gosub chk.gold:if a=0 print \"You don't have that much!":goto bank
 gosub put.gold
 goto bank5
bank3
 input @2 \"[ Withdraw ] - How much? "gd$:if gd$="" goto main1
 gosub val.gold:if a=0 print \"Invalid amount!":goto bank
 gosub spl.gold:g3=bh:g4=bl:gosub chk.gold:if a=0 print \"You don't have that much!":goto bank
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
 gosub put.gld2:gosub wr.ply2
 print \"Gold transferred to "zz$:goto bank

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
 if g1<0 g1=0:g2=0:gd$="":print \"Number too lage!"
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
 print \"(Pawn shop not active here)":goto main1
;
clan
 print "(Join not active here)":goto main1
;
elevator
 dy$=dx$+"elevator":open #1,dy$
 position #1,pn,10:input #1,xu$:close
 if un=1 print \"xu$='"xu$"'; pn="pn
elev.1
 if un=1 input "Test malfunction Y/N:" i$:if i$="Y" goto malfunction
 input @2\"TRANSPORTER ROOM: Coordinates ->"i$
 if i$="" or i$="Q" goto main1
 if i$<>xu$ print \"Wrong!":goto elev.1
 input @2\"LEVEL: [1] [2] [3] [4] [5]->"i$
 a=val(i$):if (a<1) or (a>5) print \"It don't go there!":goto main1
 print "Standby to beam down!":cl=a
 zz$=rnd$:xz=random(100):if instr("TR+",ys$) xz=xz-20
 if xz<10 goto malfunction
 if len(ys$)<220 then if not instr("TR+",ys$) then ys$=ys$+"TR+"
 for x=1 to 8:print ".":gosub delay:next:print \
 dy$=dz$+"spur.shop":link dy$
;
;
ammo
 print \"You enter the ship's ammo locker.."
 dy$=dw$+"items":open #1,dy$
ammo3
 x=118
 print \"  # Name      Rnds Dmg Weapon    Cost"
 print  " []=-=-=-=-=-=[STARBURST]=-=-=-=-=-=[]"
ammo1
 position #1,30,x:input #1,cb$:if cb$="*" goto ammo1a
 input #1,it$\it:it=it*10
 zm=instr("|",it$):if zm=0 goto ammo1a
 zw$=mid$(it$,zm+1,2):zx$=mid$(it$,zm+3,1):zy$=mid$(it$,zm+4)
 if left$(zy$,4)="LIGH" zy$="LIGHT SABRE"
 if left$(zy$,4)="PHAS" zy$="HAND PHASER"
 if left$(zy$,4)="PLAS" zy$="PLASMA RIFLE"
 it$=left$(it$,zm-1):it$=mid$(it$,3):if left$(zy$,1)=" " zy$=mid$(zy$,2)
 it$=left$(it$+"          ",11)
 it$=right$("   "+str$(x),3)+":"+it$
 it$=it$+" "+zw$
 it$=it$+" "+zx$+" "+zy$
 it$=left$(it$+"                        ",35)
 print it$"-"right$("  "+str$(it),3)
ammo1a
 x=x+1:if x>121 goto ammo2
 goto ammo1
ammo2
 if xi>zo-1 print \"You have no room in your pack!":close:goto armory
 input @2\"Your Choice (?=List): "i$:if i$="" or i$="Q" close:goto armory
 if i$="?" goto ammo3
 x=val(i$):if (x<118) or (x>121) print \"Enter 118 - 121 or Q":goto ammo2
 position #1,30,x:input #1,cb$:if cb$="*" goto ammo2
 input #1,it$\it:it=it*20
 g3=gh:g4=gl:g1=0:g2=it:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto ammo2
 a$=mid$(it$,3):zm=instr("|",a$)
 if not zm print \"This is not ammo!!":goto ammo2
 a$=left$(a$,zm-1)
 print \"You choose "a$" for "it" gold? ";:input @0 i$
 if i$<>"Y" goto ammo2
 xa$=right$("000"+str$(x),3)+","
 print \"You insert gold in the slot.":g2=it:gosub sub.gold
 xi=xi+1:xi$=xi$+xa$:goto ammo2
;
return
 return
;
malfunction
 gosub delay:print \"A STRANGE BUZZING COMES FROM THE TRANSPORTER!!"
 gosub delay:print \"A RED LIGHT STARTS FLASHING URGENTLY!"\
 for xz=1 to 5:gosub delay:print "[] ALARM []"\:next
 i$="[] MALFUNCTION []"
 xz=info(2):if xz=0 xz=2
 if xz>1 xz=100
 for yz=1 to 4
 for yx=1 to len(i$):print mid$(i$,yx,1);:for yy=1 to xz:next:next
 for yx=1 to len(i$):print chr$(8)" "chr$(8);:for yy=1 to xz:next:next
 next:for yz=1 to 8:gosub delay:zz$=rnd$:yx=random(10)+1:for yy=1 to yx
 print " ";:next:print ".":next
 print:zz$=rnd$:cl=random(6)+1:if cl>6 cl=6
 dy$=dx$+"battle.log":create dy$:open #1,dy$:append #1
 print #1, left$(date$,6)yr$" "time$": HARR HARR"
 print #1, "THE TRANSPORTER MALFUNCTIONED!"
 print #1, n1$" WAS SENT.. SOMEWHERE.."
 print #1, "[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 i$="MALFUNCTION":goto lnk.msc
;
salvage
 print \"You go to the ships Salvage Bay"
 if instr("*SS",ys$) print \"The salvage computer does not respond":goto main1
 if len(ys$)<240 ys$=ys$+"*SS"
sal.1
 print \"Salvage Bay"
 input "[S]ell, [Q]uit :"i$:if i$="Q" print \"AFFIRMATIVE DAVE":goto main1
 if i$<>"S" goto sal.1
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
 
 input @2\"Sell which item number? "a$:x=val(a$):if a$="" goto sal.1
 if (x<1) or (x>xi) print "You're NOT carrying that!!":goto sal.1
 l=len(xi$):y=(x*4)-3:a=val(mid$(xi$,y))
 if a<>146 print\"NON-SALVAGE STATUS. DOES NOT COMPUTE":goto sal.1
pwn.1
 open #1,dy$
 position #1,30,a
 input #1,cb$\it$\g2
 close:g2=g2*40:zm=instr("|",it$):if zm>0 it$=left$(it$,zm-1)
 if a=67 then if mid$(zu$,2,1)="1" print \"Can't, you are USEing it!":goto sal.1
 if (a=73) or (a=76) print \"I don't want it!":goto sal.1
 print \"SALVAGE VALUE "g2" GOLD FOR THE "mid$(it$,3)","
 input "AFFIRMATIVE? "i$:if i$<>"Y" print \"bzzz..":goto sal.1
 print \"ACKNOWLEDGED":gosub add.gold
drp.itm2
 xi=xi-1:if xi=0 then xi$="":goto sal.1
 if y=1 then xi$=mid$(xi$,5):goto sal.1
 if (y+4)>l then xi$=left$(xi$,y-1):goto sal.1
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
 goto sal.1
;
delay
 for a=1 to 3000:next:return
;
lnk.msc
 dy$=dz$+"spur.misc":link dy$
;
compile
 if un=1 print "ok..":link "k:system.seg"
;
comp.chk
 print \" ok":return
;

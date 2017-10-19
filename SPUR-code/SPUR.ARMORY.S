
;..spur.armory.s

 on nocar goto dropped
 public compile

 print\'
You are lead through a back door, to a large shed in back.
Acrid smoke and clanging of metal greet you, as well as
a huge metal smith who eyes you through a yellow grin.'

 gosub open
;..move readied or worn values to file before proceeding
 position #2,250,pn,209:input #2,x:if x zw$="A":gosub set.data:it=ar:gosub store
 position #2,250,pn,213:input #2,x:if x zw$="S":gosub set.data:it=sh:gosub store

armory0
 gosub pr.items:if xi=0 goto shop
 if zz=0 print "You don't have any armor or shields!":goto shop
armory1
 print\'"What kin eye fix fer ye?" (?=list): ':input @2 a$
 if a$="?" goto armory0
 if a$="" goto shop
 if instr(" ",a$) print \"There was a space in your entry.":goto armory1
 if a$="W" position #2,250,pn,209:input #2,x:if x goto armory2
 if a$="R" position #2,250,pn,213:input #2,x:if x goto armory2
 x=val(a$):if (x<1) or (x>xi) print \"You don't have that item.":goto armory1
 y=(x*4)-3:x=val(mid$(xi$,y))
armory2
 position #1,30,x,2:input #1,n$\it
 zw$=left$(n$,1):if x>59 zw$="*"
 if zw$<>"S" if zw$<>"A" print "'I can't do anything for the "mid$(n$,3)"'":goto armory1
 gosub get.data
 if zz>(it*10)-1 print "'I can do no more for the "mid$(n$,3)"'":goto armory1
 zz=(it*10)-zz:if xp>2 zz=zz*2
 g3=gh:g4=gl:g1=0:g2=zz
 print \"'I will fix the "mid$(n$,3)" for "zz" gold'"
 gosub chk.gold
 if a=0 print \"You do not have enough gold.":goto armory1
 input @2"Ok? [Y]/n:"i$
 if i$="N" print '"Ho boy..."':goto armory1
 print \"The smithy grabs the "mid$(n$,3)" and scuttles back into the smoke."
 gosub delay
 print "Noises can soon be heard."
 gosub delay:print "BANG ";
 gosub delay:print "CLANG ";
 gosub delay:print "RATTLE ";
 gosub delay:print "WHEEZE(?) ";
 gosub delay:print "OOFF!":gosub delay
 print \"Done!":g2=zz:gosub sub.gold
 g1=gh:g2=gl:gosub prt.gold:print "You now have "gd$" gold"
 it=it*10:gosub store
;update if item is current worn or readied
 position #2,250,pn,209:input #2,a:if a=x ar=it
 position #2,250,pn,213:input #2,a:if a=x sh=it
 goto armory1

store
 f$=right$("X"+str$(x),2)
;..find record number in ITEM file for repair
 xx=instr(f$,zy$):if xx=0 return
 position #2,250,pn,zy:input #2,a$
 if len(a$)<>14 a$="00000000000000"
 f$=str$(it):if it>99 f$="99"
 f$=right$("0"+f$,2)
 if xx=1 a$=f$+mid$(a$,3):goto store1
 if xx=13 a$=left$(a$,12)+f$:goto store1
 a$=left$(a$,xx-1)+f$+mid$(a$,xx+2)
store1
 position #2,250,pn,zy:print #2,a$
 return
;
get.data
;..zz starts as it*10
 gosub set.data
 position #2,250,pn,zy:input #2,a$
 if len(a$)<>14 return
 f$=right$("X"+str$(x),2)
 xx=instr(f$,zy$)
 if xx=0 zz=0:return
 zz=val(mid$(a$,xx,2))
 if zz<1 zz=0
 return
;
pr.items
 zz=0
 xi=len(xi$)/4:if xi=0 print \"No Items.":return
 print:x=0
 position #2,250,pn,209:input #2,a:if a gosub pr.2a
 position #2,250,pn,213:input #2,a:if a gosub pr.2a
 for x=1 to xi:gosub pr.2:next
 return

pr.2
 y=(x*4)-3:a=val(mid$(xi$,y))
pr.2a
 position #1,30,a,2:input #1,n$\it:zw$=left$(n$,1)
 if zw$<>"A" if zw$<>"S" goto pr.1
 gosub set.data
 position #2,250,pn,zy:input #2,a$
 f$=right$("X"+str$(a),2)
 xx=instr(f$,zy$)
 if xx=0 print "We do not service the "mid$(n$,3):goto pr.1
 xx=val(mid$(a$,xx,2)):i$=""
 if it<1 print "Bad value of [it]":goto pr.1
 zt=(xx*100)/it:zt=zt/10
 if zt>125 if a<60 i$="ENCHANTED"
 if zt>100 if i$="" i$="EXCELLENT"
 if zt>75 if i$="" i$="GOOD"
 if zt>50 if i$="" i$="SERVICABLE"
 if zt>25 if i$="" i$="POOR"
 if i$="" i$="TERRIBLE"
 zm=instr("|",n$):if zm n$=left$(n$,zm-1)
 if x zt$="["+str$(x)+"]      "
 print zt$" - "mid$(n$,3);
 print ", IN "i$" CONDITION ("xx")"
 zz=1
pr.1
 return
;
set.data
 if zw$="S" zy$="X4X51213234556":zy=217:zt$="[R]eadied"
 if zw$="A" zy$="X2X31024284657":zy=233:zt$="[W]orn   "
 return
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

delay
 for yy=1 to 5000:next
 return
;
add.log
;.. i$=log message
 close
 open #1,"a:add.log":append #1
 print #1,"Spur.armory: "i$" @"time$
 close
open
 open #1,dw$+"items":open #2,dx$+"misc.data"
 return
;
shop
 link dz$+"spur.shop","main1"
;
quit1
 link ds$+"spur.logon","quit1"
;
dropped
 i$="SPUR.ARMORY":dy$=ds$+"spur.logon":link dy$,"quit3"
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print \"Compiled..":link "k:system.seg"
;


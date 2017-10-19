
;... spur.misc8.s
;... modified with Appleworks

 on nocar goto dropped
 if flag(32) print "spur.misc8-";:gosub comp.ck

 public compile

 on nocar goto dropped
 if i$="JAKES" goto jakes
 if i$="SRV.GUILD" goto s.guild
 i$="Bad value of i$ in spur.misc8! i$="+i$:print \i$
 gosub add.lg:goto advent
;
;
jakes
 print \'
You stand inside a dimly lit stable, a fat little man peers at you over grimey
lenses, perched on an enormous mustache. "Welcome to Jakes Stable!"'

jakes1
 gosub tim.chk
 setint(1):print \'
"What kin ey git fer ye?"
 1) Oats         5) Sugar Cube
 2) Lasso        6) Train Horse
 3) Saddle       7) Tips
 4) Horse Armor'

 setint(""):input @2\"->"i$
 if i$="" or i$="Q" goto street
 x=val(i$)
 if x=1 x=82:goto food
 if x=2 x=161:goto item
 if x=3 x=162:goto item
 if x=4 x=163:goto item
 if x=5 x=16:goto food
 if x=6 goto train
 if x=7 goto tips
 print \"'Beg yer pardin?'":goto jakes1

item
 if xi>zo-1 print \"You have no room in your pack!":goto jakes1
 dy$=dw$+"items":open #1,dy$
 position #1,30,x:input #1,cb$
 input #1,it$\it:close
 if cb$="*" print "Unavailable!":goto jakes1
 it=it*100
 g3=gh:g4=gl:g1=0:g2=it:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto jakes1
 a$=mid$(it$,3)
 print \"You choose "a$" for "it" gold? ";:input @0 i$
 if i$<>"Y" goto jakes1
 xa$=right$("000"+str$(x),3)+","
 print \"Done!":g2=it:gosub sub.gold
 xi=xi+1:xi$=xi$+xa$:goto jakes1

food
;.. input x = ration number
 if xf>(zo-1) print \"You have no room in your pack!":close:goto jakes1
 dy$=dw$+"stores":open #1,dy$
 position #1,26,x:input #1,cb$
 input #1,gs$\gs:close
 if cb$="*" print "Unavailable!":goto jakes1
 g3=gh:g4=gl:g1=0:g2=gs:gosub chk.gold:if a=0 print \"You do not have enough gold.":goto jakes1
 a$=mid$(gs$,3)
 print \"You choose "a$" for "gs" gold? ";:input @0 i$
 if i$<>"Y" goto jakes1
 xa$=right$("000"+str$(x),3)+","
 print \"Done!":g2=gs:gosub sub.gold
 xf=xf+1:xf$=xf$+xa$:goto jakes1
;
train
 i$=d1$+d2$+d3$
 if not instr("=",i$) print "Ye don't have a mount!":goto jakes1
 if not instr("@",i$) print "Ye horse must have a saddle first.":goto jakes1
 if not instr("$",i$) print "Ye horse must have armor first.":goto jakes1
 input @2\"Ye want me to train yer horse for 2000 gold? "i$
 if i$<>"Y" goto jakes1
 g3=gh:g4=gl:g1=0:g2=2000:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":goto jakes1
 a=0
 if instr("=",d1$) if not instr("!",d1$) d1$=d1$+"!":a=1
 if instr("=",d2$) if not instr("!",d2$) d2$=d2$+"!":a=1
 if instr("=",d3$) if not instr("!",d3$) d3$=d3$+"!":a=1
 if a=0 print \"Thy mount already IS trained!":goto jakes1
 g2=2000:gosub sub.gold
 a=34:gosub messages:goto jakes1
;
tips
 a=35:gosub messages:goto jakes1
;
;
;
s.guild
 setint(1):print \'
You stand in the entrance of the Servants Guild. A huge, strange looking being
greets you, bowing low. "I am Bubba, Master of the Allys Guild. How may we be
of assistance?"'
 setint("")

s.guild1
 gosub tim.chk:setint(1):print \'
             [ALLYS GUILD]
1) Armor             2) Discipline training
3) Body building     4) Combat training
5) Tracking training'

 setint(""):input @2\"->"i$
 if i$="" or i$="Q" goto street
 if a1+a2+a3=0 print "Ye do not have any Allies!":goto street
 x=val(i$)
 gosub a.select:if zt=0 goto s.guild1
 if x=1 gosub s.armor:goto s.guild1
 if x=2 gosub s.disc:goto s.guild1
 if x=3 gosub s.bod:goto s.guild1
 if x=4 gosub s.wep:goto s.guild1
 if x=5 gosub s.track:goto s.guild1
 print "Bad x value":goto s.guild1

a.select
 zt=0:print \"Which ally?"
 if a1 lu$=d1$:gosub cln.ally:print "1) "lu$:if not instr("|",d1$) d1$=d1$+"|"
 if a1 if not instr("#",d1$) d1$=d1$+"#5"
 if a2 lu$=d2$:gosub cln.ally:print "2) "lu$:if not instr("|",d2$) d2$=d2$+"|"
 if a2 if not instr("#",d2$) d2$=d2$+"#5"
 if a3 lu$=d3$:gosub cln.ally:print "3) "lu$:if not instr("|",d3$) d3$=d3$+"|"
 if a3 if not instr("#",d3$) d3$=d3$+"#5#"
 input @2\"->"i$:if (i$="") or (i$="Q") zt=0:goto s.guild1
 zt=val(i$):if (zt<1) or (zt>3) zt=0:print \"1 to 3 or Q":goto a.select
 if zt=1 zt$=d1$:if a1=0 zt=0
 if zt=2 zt$=d2$:if a2=0 zt=0
 if zt=3 zt$=d3$:if a3=0 zt=0
 if zt=0 print \"No ally there!":goto a.select
 lu$=zt$:gosub cln.ally
 if flag(32) print "a.select: zt$="zt$;:input @2" Mod->"i$:if i$<>"" zt$=i$
 if len(zt$)>17 print \"Sorry, "lu$" can not be helped..":zt=0
 return

s.disc
 g2=1000:zw$="TRAINED IN DISCIPLINE":zx$="!":goto set.ally

s.armor
 if instr("=",zt$) print \"Sorry, our amour will not fit "lu$:zt=0
 g2=600:zw$="EQUIPPED WITH ARMOR":zx$="$":goto set.ally

s.wep
 g2=800:zw$="TRAINED IN COMBAT":zx$="%":goto set.ally

s.track
 if instr("=",zt$) print \"Sorry, "lu$" would not make a good tracker!":zt=0
 g2=750:zw$="TRAINED IN TRACKING":zx$="&":goto set.ally

s.bod
 x=instr("#",zt$):if x=0 print \lu$" can not be helped!":zt=0:return
 zs=val(mid$(zt$,x+1,1)):if zs<1 print \lu$" can not be helped!":zt=0:return
 if zs>8 print \lu$" already is as large as possible!":zt=0:return
 zs=zs+1:zx$="#"+str$(zs)
 if x=len(zt$)-1 zt$=left$(zt$,x-1):goto s.bod2
 zt$=left$(zt$,x-1)+mid$(zt$,x+2)
s.bod2
 if flag(32) print "s.bod: zt$="zt$", x="x
 g2=(zs*40)+(zs*40)+(zs*40):zw$="BODY BUILT +3"
 goto set.ally

set.ally
 if zt=0 return
 if instr(zx$,zt$) print \lu$" already IS "zw$"!":return
 print \"Ye want "lu$" "zw$" for "g2" gold? y/N :";:input @2 i$
 if i$<>"Y" return
;g2 set before coming here
 g3=gh:g4=gl:g1=0:gosub chk.gold
 if a=0 print \"Ye do not have enough gold.":return
 gosub sub.gold:gosub delay
 if zt=1 d1$=zt$+zx$
 if zt=2 d2$=zt$+zx$
 if zt=3 d3$=zt$+zx$
 goto log
;
delay
 print "You wait in the Masters Waiting Room, sipping coffee..";
 for a=1 to 10:for b=1 to 3000
 next:print ".";:next:print "DONE!!":return
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
;
log
;... xu$=zw$ check prevents monotinous repeats of the same messge
;... when an allys body built routine is repeated.
 if xu$=zw$ return
 dy$=dx$+"battle.log":create dy$:open #2,"battle.log":append #2
 print #2, left$(date$,6)yr$" "time$"-ALLY GUILD"
 print #2, n1$" HAD "lu$" TRAINED"
 print #2, "IN THE ALLIES GUILD. ENHANCEMENT WAS:"
 print #2, zw$
 print #2,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close #2
 xu$=zw$
 return

street
 i=0:zv$="":print "You return to the street.."
advent
 dy$=dz$+"spur.main":link dy$
main.ret
 dy$=dz$+"spur.main":link dy$,"return"
comb.ret
 dy$=dz$+"spur.combat":link dy$,"return"
lnk.sub
 dy$=dz$+"spur.sub":link dy$
lnk.msc6
 dy$=dz$+"spur.misc6":link dy$
linkshop
 setint(""):dy$=dz$+"spur.shop":link dy$,"main1"
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:i$="QUIT":goto lnk.sub
 if ev-ex<120 print on$"Dusk approaches..."of$
 return

drop.1
 pop
dropped
 i$="SPUR.MISC8":dy$=ds$+"spur.logon":link dy$,"quit3"
;
show.file
 setint(1):print \s$\:copy f$:setint(""):return
;
add.lg
 open #2,"a:add.log":append #2
 print #2,"Spur.misc8: "i$" @"time$
 close #2:return
;
; a=message number
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):ready dr$:return
;
cln.ally
 if instr("|",lu$) lu$=left$(lu$,instr("|",lu$)-1)
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
comp.ck
 print "ok":return
;

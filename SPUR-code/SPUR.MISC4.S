;.... spur.misc4.s

 on nocar goto dropped
 public compile
;
 if un=1 print "spur.misc4--";:gosub comp.ck
 cs$=""
 if i$="MON.CST" goto mon.cst
 if i$="rd.dwarf" gosub rd.mons:goto mon.ret
 if i$="rd.mons" gosub rd.mons:goto rd.mon3
 if i$="LOGON.STAY" gosub stay.a:dy$=ds$+"spur.logon":link dy$,"return"
 if i$="MAIN.STAY" goto stay
 i$="Bad value of i$ in spur.misc4 ->"+i$
 print \i$:gosub add.lg:goto l.return
;
mon.cst
 zw$="":gosub rnd.10z
 if (z+5>ms) or z<3 then if not instr("end",zs$) goto endrnce
 if z+7>ms then if instr("++",wy$) then if not instr("end2",zs$) goto endrnce
 if not instr("dest",zs$) goto destroy
 if instr("++",wy$) then if not instr("dest2",zs$) goto destroy
 if instr("++",wy$) gosub rnd.10z:if (z+xp+8>ms) or (z=5) goto teleport
 goto c.return

endrnce
 print \m$" CASTS AN ENDURANCE SPELL, AND GAINS STRENGTH!"
 ms=ms+5*xp:if instr("++",wy$) ms=ms+2*xp
 if instr("end",zs$) zs$=zs$+"end2":else zs$=zs$+"end"
 pop:goto c.return

destroy
 print \m$" CAST A DESTROYER SPELL ON YOU!!"
 gosub rnd.10z:z=(z/2)+1:z=z+4
 if instr("++",wy$) z=z+2
 if instr("dest",zs$) zs$=zs$+"dest2":else zs$=zs$+"dest"
 print \"ZAP! You take "z" hits!":hp=hp-z
 if hp<1 hp=0:pop:print\"opps..":xn=sn:sn=0:z=14:i$="dead2":goto lnk.msc6
 pop:goto c.return
;
teleport
 print \m$" CASTS A TELEPORT SPELL ON YOU!"\\"THE AREA FADES FROM VIEW.."\
 pop:pop:mf=0:mw=0:m$="":wy$="":dy$=dz$+"spur.main":link dy$,"flee2"
;
;
 vy=0:vz=0:zq=0:zs=0:md=0:mf=0:mw=0
 dy$=dw$+"monsters"
 open #1,dy$
 position #1,32,m
 input #1,cb$\m$\ms,sw\ma
 close
 ty$=left$(m$,1):m$=mid$(m$,3)
 wy$="":if m=67 wy$="|<":m$="GUARD \|/":goto claw
 yy=instr("|",m$):if yy wy$=mid$(m$,yy)+"  ":m$=left$(m$,yy-1)
 if right$(m$,1)=" " m$=left$(m$,yy-2)
 if m=70 gosub wraith:if vw return
claw
 if xp>1 then ms=((xp+1)*ms)/2
 if instr(".",wy$) ms=ms+10
 if not instr(".",wy$) then if ms>60 ms=60
 if ms>80 ms=80
 ms=ms+((cl-1)*3)
 zx$=left$(m$,1):yy=val(zx$):if yy>0 m$=mid$(m$,2)
 zw$="THE "+m$:i$="S ":if right$(zw$,1)="S" i$=" "
 if (zw$=d1$) or (zw$=d2$) or (zw$=d3$) then ms=0:print \zw$" LOOK"i$"AROUND NOSTALGICALLY..":return
 zw$=" HUGELARGE  BIG  MANSHORTSMALLSWIFT"
 z=(ma-2)*5+1:zy$=mid$(zw$,z,5)
 if left$(zy$,1)=" " zy$=mid$(zy$,2):if left$(zy$,1)=" " zy$=mid$(zy$,2)
 if ma=5 zy$=zy$+" SIZED"
 if m>64 then if m<68 zx$=rnd$:if random(100)/20=3 m$="CAPTAIN!" +mid$(m$,6):ms=ms+(xp*3):wy$="|;>]"
 zw$="YOU SEE A "
 if instr("E",wy$) zy$=zy$+" EVIL"
 if instr("G",wy$) zy$=zy$+" GOOD"
 if instr("$",wy$) gosub multi.mn
 zw$=zw$+zy$+" "+m$+"!":xz$="S ":if right$(m$,1)="S" xz$=" "
 if m=74 ms=ms+5+(xp*2):return
 if m=93 ms=ms+30
 if (instr(".",wy$)) or (instr("AC",wy$)) goto d.charm

;...turf guards
 if m=67 then if ((vv=6) or (vv=7)) zq=1
 if m=66 then if ((vv=3) or (vv=4)) zq=1
 if m=65 then if ((vv=8) or (vv=9)) zq=1
 if zq=1 zw$="YOU MEET ONE OF YOUR GUARDS.":zx$="HE SALUTES SMARTLY!":return

;...surprise
 z=10-ma:z=z*2:z=z+(2*xp):z=z+pd
 if pc=5 or pc=6 z=z+15
 if pc=8 z=z+7
 if pr=3 z=z+15
 if pr=4 z=z+7
 if wa=8 z=z+15
 if z>50 z=50
 i$="A":if right$(m$,1)="S" i$="SOME"
 zx$=rnd$:if random(150)<z zw$="YOU SURPRISED "+i$+" "+zy$+" "+m$+"!":zs=998
 if zs=998 then if instr(":",wy$) zw$="THE "+zy$+" "+m$+" FAIL"+xz$+"TO DETECT YOU!" :goto rd.mon2
 if zs=998 then if yy>0 a$=rnd$:z=random(100):if z<(hp+(xp*2)) zx$="WHO RUN"+xz$+"AWAY SCREAMING!":md=2:mw=0:ms=0:return

;...charm
d.charm
 if (yy=0) or (zs=998) goto rd.mon2
 z=pi+pw:z=z+(2*xp)
 if pc=4 z=z+20
 if pc=9 if yy=1 z=z+20
 if pr=2 if not instr("E",wy$) z=z-40
 if pr=3 if yy=2 z=z+40
 if pr=4 z=z+10
 if pr=8 if not instr("E",wy$) z=z-20
 if z>70 z=70

;.. additional mods for alignment
 i$="":if not instr("E",wy$) goto not.evil
 if (pr=2) or (pr=8) z=z+10:if vk>900 i$="*"
 if (pr=3) or (pr=4) if vk>700 i$="*"
 if i$="*" cs$="(WHO IS AGAST AT YOUR GOODLY WAYS)":ms=ms+(xp*5):goto rd.mon2
 if vk<900  z=z+((1000-vk)/20):goto not.good
 if vk>1100 z=z-((vk-1000)/20):goto not.good
not.evil
 if not instr("G",wy$) goto not.good
 if (pr=3) or (pr=4) z=z+10:if vk<1100 i$="*"
 if (pr=2) or (pr=8) if vk<1300 i$="*"
 if i$="*" cs$="(WHO IS AGAST AT YOUR EVIL WAYS)":ms=ms+(xp*5):goto rd.mon2
 if vk>1100 z=z+((vk-1000)/20)
 if vk<900  z=z-((1000-vk)/20)
not.good
 zx$=rnd$:zx$="IS":if right$(m$,1)="S" zx$="ARE"
 if random(200)+10<z then if not instr(".",wy$) zq=1:zx$="(WHO "+zx$+" QUITE CHARMED..)"
 if pr=9 then if instr("DRAGON",m$) zq=1:zx$="(Dragons are great fans of Half-Elfs..)"
 if instr("AC",wy$) zq=1
rd.mon2
 gosub mon.set
 if zq=0 then if zs=0 gosub tactical
 if (not sw) then sw$="":return
 dy$=dx$+"weapons"
 open #1,dy$
 position #1,34,sw
 input #1,cb$\sw$
 close:sw$=mid$(sw$,4)
 return
;
tactical
 a$=right$("000"+str$(m),3):if instr(a$,xm$) return
 zt=0:i$="1111122333":gosub rnd.10z
 zx$=mid$(i$,z,1):vy=val(zx$):if vy=0 vy=1
 if vy=1 then if a1 print \d1$" SHOUTS 'TO THE FRONT!'":zt=a1:i$=d1$:x=h1
 if vy=2 then if a2 print \d2$" SHOUTS 'ON THE FLANK!'":zt=a2:i$=d2$:x=h2
 if vy=3 then if a3 print \d3$" SHOUTS 'TO THE REAR!'":zt=a3:i$=d3$:x=h3
 zx$=rnd$:z=random(299):z=(z/10)-9
 if zt>0 then if z>zt then if instr("!",i$) print i$" IS TOO CLEVER TO BE CAUGHT OFF GUARD.":return
 if zt>0 then if z>zt print i$" WAS CAUGHT OFF GUARD!":vz=1:goto desert
 if zt>0 return
 if vy=1 print \"TO THE FRONT!"
 if vy=2 print \"ON THE FLANK!"
 if vy=3 print \"TO THE REAR!"
 z=z+(vy*3)
 if zt=0 then if (z>(pi+xp)) vz=1
 if random(10)=5 vz=1
 if vz=1 print "YOU ARE CAUGHT OFF GUARD!"
 return
desert
 gosub rnd.10z:if z<>5 then return
 if instr("SPACE",ww$) xx$="FIRES RETROS, AND FLEES!":else xx$="JUMPS OVERBOARD AND SWIMS AWAY!"
 if instr("@@",lo$) print i$" "xx$:else print i$" RUNS AWAY SCREAMING!"
 gosub fre.ally
 if vy=1 d1$="*":a1=0:h1=0
 if vy=2 d2$="*":a2=0:h2=0
 if vy=3 d3$="*":a3=0:h3=0
 if (a1+a2+a3)<1 then ai=0:ai$=""
 xx$="FLEE":zt$=i$+" DESERTED":goto news
;
mon.set
 if m=103 gosub guardian
 a$=right$("000"+str$(m),3):if instr(a$,xm$) then return
 if not instr("?",wy$) m$="THE "+m$
 if instr("+",wy$) print \"The air crackles with magic.."
 if instr("++",wy$) print "Lightning shimmers around "m$".."
 z=instr("-",wy$):if (cl<6) or (z=0) goto fire
 if zs<>998 print \m$" READIES IT'S ENERGY WEAPON!":gosub delay.a
 if instr("LAZ.SH",ys$) print \"YOUR LAZER SHIELD KICKS IN!"\:gosub delay.a :else print \"(Too bad you didn't USE a LAZER SHIELD)"
 z=0
fire
 if (not instr("097",xi$)) or (z=0) then goto stone
 gosub rnd.10a:if a=5 zz$="ICE CRYSTAL":gosub glasses:goto stone
 print\"The ICE CRYSTAL glows, preventing FIRE ATTACK from "m$"!"
 wy$=left$(wy$,z-1)+mid$(wy$,z+1)
stone
 z=instr("#",wy$):if (not instr("082",xi$)) or (z=0) then return
 gosub rnd.10a:if a=5 zz$="CRYSTAL PENDANT":goto glasses
 print\"The CRYSTAL PENDANT flashes, preventing TURN TO STONE by "m$"!"
 wy$=left$(wy$,z-1)+mid$(wy$,z+1)
 return
;
glasses
 print \m$" happens to see you are"
 print "wearing the "zz$", and"
 print "quickly puts on ANTI-"zz$
 print "glasses!":return
;
guardian
 if instr("gd2",ys$) print \"THIS TIME, THE GUARDIAN IS WAITING FOR YOU!":wy$=wy$+"++];":ms=ms+(xp*6):vz=1:return
 if mid$(zu$,8,1)<>"1" goto no.amult
 gosub rnd.10a:if a<3 zz$="AMULET":gosub glasses:goto no.amult
 wy$="<.~":print \"The Amulet of life blazes bright, startling the GUARDIAN!"
no.amult
 if instr("gd1",ys$) then if len(ys$)<240 ys$=ys$+"gd2"
 if not instr("gd1",ys$) then if len(ys$)<240 ys$=ys$+"gd1"
 return

wraith
 vz=1:vw=0:wy$="|.*&~<!51E"
 if mid$(zu$,2,1)="1" ms=ms+(xp*7):wy$=wy$+";":print \"(..oh, oh... The ring..)"\
 if vk>800 return
 gosub rnd1000z:if (pr=2) or (pr=8) z=z+100
 if z+100 < vk print \"The monster ignores your alignment, and attacks!":return
 print \'
The Ringwraith recognizes one of his own kind! Hot yellow eyes glow at you
from under black hood for a long second. You feel its evil strength..'\
 for vw=1 to 2000:next
 if hp<30 hp=30:print "(hit points increase)"
 if ps<26 ps=26:print "(strength increases)"
 if pe<26 pe=26:print "(energy increases)"
 if pd<26 pd=26:print "(dexterity increases)"
 ep=ep+25:print "(+25 exp)"
 zt$="RINGWRAITH VISITED":xx$="EVIL!":gosub news
 print \"The shadow flies away.."\
 if vk>25 vk=vk-25
 mf=0:mw=0:m$="":wy$="":ms=0:zn=70
 return

multi.mn
 gosub rnd.10z:z=z/2+2:ms=ms+((ms/2)*z):wy$=wy$+"]"
 zw$="YOU SEE "+str$(z)+" ":if right$(m$,1)<>"S" m$=m$+"S"
 return

rd.mon3
 if md=2 print \zw$\\zx$
 if ms=0 goto mon.ret
 mw=m:md=0
 a$=right$("000"+str$(m),3):if instr(a$,xm$) then md=1:mw=0:mf=0
 if md=1 goto mon.ret
 z=instr("!",wy$)
 if zw$<>"" print \zw$:if (zq>0) and (z=0) then print zx$
 if cs$<>"" print cs$:goto mon.ret
 if yy<>1 then if yy<>3 goto mon.ret
 if z yx=val(mid$(wy$,z+1,2)):goto perm.qt
 if zs=998 print "'YELP!!'":goto mon.ret
 if zq>0 print "'GOSH, ER... HI "n1$"!'":goto mon.ret
 zz$=rnd$:yx=random(99)/10:yx=yx+61:if yx>70 yx=61
 if instr("E",wy$) then if ((pr=2) or (pr=9)) goto perm.qt
 if instr("G",wy$) then if ((pr=3) or (pr=4)) goto perm.qt
 yx=random(499)/10:yx=yx+1
perm.qt
 z=170:dy$=dw$+"monster.quote"
 open #1,dy$:position #1,z,yx:input #1,zz$:close
 yx=instr("$",zz$):dy$=zz$:xz=len(zz$)
 if yx>1 then if yx<xz dy$=left$(zz$,yx-1):zz$=mid$(zz$,yx+1):dy$=dy$+n1$+zz$
 if yx=1 dy$=n1$+mid$(zz$,2)
 if yx=xz dy$=left$(zz$,yx-1)+n1$
 zz$=dy$:dy$="'"+zz$+"'"
 print dy$:goto mon.ret
;
news
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$" "xx$
 print #1, zt$" THE "n1$
 print #1, "PARTY IN "ww$".."
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 return
;
fre.ally
 if x=0 return
 dy$=dx$+"allies":open #1,dy$
 position #1,26,x
 print #1,1:close:return
;
delay.a
 for a=1 to 4000: next:return
;
stay
 if vv<3 print \"ONLY GUILD MEMBERS CAN HAVE FOLLOWERS.":goto advent
 if yt$="*" print \"NOBODY IS FOLLOWING!":goto advent
 a$=n1$:gosub stay.a:yz=len(xv$):zt$=ta$
 if cl=1 then if (len(ta$)+yz<250) ta$=ta$+xv$
 if cl=1 then if zt$=ta$ then if (len(tf$)+yz<250) tf$=tf$+xv$
 if cl=2 then if (len(tb$)+yz<250) tb$=tb$+xv$
 if cl=3 then if (len(tc$)+yz<250) tc$=tc$+xv$
 if cl=4 then if (len(td$)+yz<250) td$=td$+xv$
 if cl=5 then if (len(te$)+yz<250) te$=te$+xv$
 if cl=6 then if (len(th$)+yz<250) th$=th$+xv$
 goto advent
;
stay.a
 xv$="":zt=0:i$=str$(vv)
 if instr("\|/",ww$) then if not instr(i$,"67") zt=1
 if instr("-}-",ww$) then if not instr(i$,"34") zt=1
 if instr("=[]",ww$) then if not instr(i$,"89") zt=1
 if (instr("#!",lo$)) or (instr("+",ww$)) then zt=1
 if (instr("@@",lo$)) or (instr("<<",lo$)) then zt=1
 if instr("OK",lo$) zt=0
 if zt=1 print \"A STRANGE FORCE PREVENTS YOU FROM DROPPING OFF FOLLOWERS!":return
 print \"DROPPING OFF FOLLOWERS."
 dy$=dx$+"spur.users":open #1,dy$
 dy$=dx$+"misc.data":open #2,dy$
stay.b
 yz=instr("*",yt$):xy=instr("=",yt$)
 if not xy then close:yt$="*":return
 xu$=mid$(yt$,yz+1,xy-2):i$=mid$(yt$,xy+1,3)
 x=val(i$)
 position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh:input #1,zw$:input #1,zx$:input #1,zy$
 yl=cl:yr=cr:position #1,130,x
 print #1,n2$,ys,yp,yl,yr,yh:print #1,zw$:print #1,zx$:print #1,zy$
 position #2,250,x:print #2,a$\
 yt$=mid$(yt$,xy+4)
 xv$=xv$+str$(cr)+"="+xu$+":"+i$+":"
 goto stay.b
;
advent
 dy$=dz$+"spur.main":link dy$
mon.ret
 vu=0:vq=0:wx$="":zs$="":zm=0
l.return
 dy$=dz$+"spur.main":link dy$,"return"
main.msc
 dy$=dz$+"spur.main":link dy$,"misc"
c.return
 dy$=dz$+"spur.combat":link dy$,"return"
lnk.msc6
 dy$=ds$+"spur.misc6":link dy$
;
rnd.10a
 zz$=rnd$:a=(random(999)/100)+1:return
rnd.10z
 zz$=rnd$:z=(random(999)/100)+1:return
rnd1000z
 zz$=rnd$:z=(random(9999)/10)+1:return
;
dropped
 i$="SPUR.MISC4"
dropped1
 dy$=ds$+"spur.logon"
 link dy$,"quit3"
; ^ target ok
add.lg
;.. i$=log message
 open #2,"a:add.log":append #2
 print #2,"Spur.misc4[] "i$" @"time$:close #2:return
;
compile
 if un=1 print \"Compiled..":link "k:system.seg"
comp.ck
 print "..ok":return
;

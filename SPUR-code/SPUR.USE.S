;spur.use.s
;Worked on with Appleworks
 on nocar goto dropped
 public compile
 if flag(32) print "spur.use-";:gosub comp.ck
;
use
 if it$="FIREPLACE" goto fire
 gosub pr.items:if xi=0:goto advent
use2
 input @2\"Use which number Item? "a$:if a$="" goto advent
 if instr(" ",a$) print \"There was a space in your entry.":goto use2
 x=val(a$):if (x<1) or (x>xi) print \"You don't have that item.":goto use2
 y=(x*4)-3:x=val(mid$(xi$,y))
 if x=16 gosub grenade:gosub clr.item:goto advent
 if x=66 goto comm
 if x=67 goto use4
 if x=80 then if cl=5 then if cr=390 goto key
 if x=80 print \"(Not here!)":goto advent
 if x=96 gosub room.dsp:goto advent
 if (x=112) or (x=117) goto power.up
 if (x=131) or (x=132) gosub card:goto advent
 if x=133 goto tool
 if (x=142) and (cl=5) and (cr=105) goto fl.vial
 if x=143 goto vial
 if x=144 goto slippers
 if x=161 goto lasso
 if ((x=162) or (x=163)) then goto eq.horse
 open #1,dy$:position #1,30,x,2
 input #1,n$\it:close
 if instr("ROCKET",n$) gosub rocket:gosub clr.item:goto advent
 zm=instr("|",n$):if zm goto ammo
 if left$(n$,1)="P" goto use3
 gosub spec.itm
 if (left$(n$,1) <> "S") print \"YOU PLAY WITH THE "mid$(n$,3)"..":goto advent
;...Use shield
 if ((x=114) or (x=116)) goto power.sh
 a=0
 if pc=1 if it>2 a=1
 if (pc=6) or (pc=8) or (pr=3) if it>4 a=1
 if (pr=5) or (pr=6) if it>5 a=1
 if a print \"THE "mid$(n$,3)" IS TOO BULKY FOR YOUR KIND" :goto advent
power.sh
 f$=dx$+"misc.data":open #2,f$
 position #2,250,pn,213:input #2,a
 if sh=0 goto no.sh
 if a>60 if sh>40 input @2\"Power shield will lose charge when repacked, ok? y/[N] :"i$:if i$<>"Y" close:goto advent
 if a=0 i$="  OLD SHIELD":goto fake.sh
 open #1,dy$:position #1,30,a,2
 input #1,i$\xx:close #1
;..store shield condition
;..don't store shield condition from ship
 if a>60 goto store.pw
 f$=right$("X"+str$(a),2)
;..find record number in ITEM file for shield
 xx=instr(f$,"X4X51213234556")
 if xx=0 close:i$="xx=0 in use shield, f$="+f$:print \i$ :gosub add.log:goto advent
 position #2,250,pn,217:input #2,a$
 if len(a$)<>14 a$="00000000000000"
 if flag(32) print "a$="a$
 f$=str$(sh):if sh>99 f$="99"
 f$=right$("0"+f$,2)
 if xx=1 a$=f$+mid$(a$,3):goto store.sh
 if xx=13 a$=left$(a$,12)+f$:goto store.sh
 a$=left$(a$,xx-1)+f$+mid$(a$,xx+2)

store.sh
 if flag(32) print "a$="a$
 position #2,250,pn,217:print #2,a$
store.pw
 a$=right$("000"+str$(a),3)+","
 if flag(32) print "a$="a$
 xi=xi+1:xi$=xi$+a$
 print \"YOU REPACK THE "mid$(i$,3)".."

fake.sh
 if a=0 print \"Discard the "mid$(i$,3); :input @2"? y/[N] :"i$:if i$<>"Y" close:goto advent

no.sh
 position #2,250,pn,213:print #2,x
 ep=ep+1:if pi<8 then pi=pi+1:gosub smart
 if x=114 it=2:print \hl$"THE BATTLE SHIELD GLOWS!"of$
 if x=116 it=2:gosub lazer.sh
 sh=it*10
 if x>59 print \"USE SHIELD POWER PAK TO ENERGIZE FULLY"
 if x<60 gosub get.sh
 print mid$(n$,3)" READIED. (New shield rating: "sh")"
 close
 gosub clr.item
 goto advent
;
get.sh
 position #2,250,pn,217:input #2,a$
 if len(a$)<>14 return
 if flag(32) print "a$="a$
 f$=right$("X"+str$(x),2)
 xx=instr(f$,"X4X51213234556")
 if xx=0 return
 sh=val(mid$(a$,xx,2))
 if sh<1 sh=it*10
 return
;
use3
 ep=ep+1
 if cp=0 cp=1:print \"Compass used.":else cp=0:print \"Compass placed in pack."
 if cp=1 print "(USE again to return to pack)"
 goto advent
use4
 ep=ep+1:zw=2:zw$="1":if mid$(zu$,2,1)="1" zw$="0"
 if zw$="1" print \"Ring worn! You are hard to see!":print "(USE again to remove)":print \"THE EVIL SENSES YOU MORE CLEARLY!"
 if zw$="1" then if pt>5 print \"(You feel a bit less healthy!)":pt=pt-2
 if zw$="0" print \"Ring returned to your pack."
 gosub zu$:goto advent
;
tool
 z=0:gosub delay.a
 if instr("134,",xi$) z=1
 if instr("135",xi$) z=z+1
 if z=1 print \"You don't have all the parts to the spacesuit."
 if z<2 goto tool.2
 print \"Bingo! Using the tools, you repair the spacesuit!"
 x$="134,":y=instr(x$,xi$):gosub clr.item
 x$="135,":y=instr(x$,xi$):gosub clr.item
 xi=xi+1:xi$=xi$+"122,"
 goto advent
tool.2
 x$="141,"
 if not instr(x$,xi$) print \"Playing with the tools does no good..":goto advent
 y=instr(x$,xi$):gosub clr.item
 xi=xi+1 :xi$=xi$+"066,"
 print \"You repair the communicator!"
 if instr("*TO",ys$) i$="Tool kit exausted..":gosub add.log: print \i$ :x$="133," :y=instr(x$,xi$) :gosub clr.item:goto advent
 if len(ys$)<240 ys$=ys$+"*TO"
 goto advent
;
card
 if cl<6 goto no.cd
 i$="You slide the card into the slot, and a door softly slides open.."
 if instr("->",lo$) then if x=131 e=1:print \i$:return
 if instr("<-",lo$) then if x=132 w=1:print \i$:return
 if not instr("<-",lo$) then if not instr("->",lo$) goto no.cd
 print \"Sticking the wrong card in the slot gets an electric shock!":if hp>5 hp=hp-4
 return
no.cd
 print \"(Playing with the Security card, does no good. :-)":return
;
lazer.sh
 print \hl$"A SHIMMERING GLOW ENGULFS YOU!"of$
 print "(50% defense from lazer fire)"
 if len(ys$)<245 if not instr("LAZ.SH",ys$) ys$=ys$+"LAZ.SH"
 return
;
power.up
 xx=209:if x=117 xx=213
 f$=dx$+"misc.data":open #2,f$
 position #2,250,pn,xx:input #2,a
 close
 if xx=209 if a<>113 if a<>115 print \"ELECTRONIC ARMOR NOT WORN":goto advent
 if xx=213 if a<>114 if a<>116 print \"ELECTRONIC SHIELD NOT READIED":goto advent
 a=ar:if xx=213 a=sh
 print \"Current power level is "a"%. Recharge? ";
 input @2"y/[N] :"i$
 if i$<>"Y" goto advent
 gosub clr.item
 i$="zzzzt":gosub pulse
 print "..  Recharged to 120%"
 if xx=209 ar=120
 if xx=213 sh=120
 goto advent
;
grenade
 print \"You hurl the grenade!":gosub delay.a
 if not mw print \"It explodes harmlessly.":return
 i$="kaboom":gosub pulse:print "!!!"
 gosub delay.a:gosub rnd.10a:a=a+5+(xp*2)
 print \m$" takes "a" damage..":ms=ms-a:goto nuk.mon
;
rocket
 if instr("NUCLEAR",n$) goto nuke
 gosub delay.a:print \\\
 i$="swoosh":gosub pulse:print \\\:gosub delay.a
 if not mw print "Such pretty fireworks!... Ohhh... Ahhh..."\:return
 gosub rnd.10a:if a<3 print"MISS..."\:return
 print "KABOOOMM!! DEBRIS FLYS! ":gosub delay.a
 if instr("PLASMA",n$) print \"A SECONDARY EXPLOSION FROM THE PLASMA!":gosub delay.a
 i$=rnd$:a=random(200)/10:a=a+15+xp
 if instr(";;",wy$) a=(a*2)/3:print \"CRUMMP! AGAINST THE HEAVY ARMOR!"
 if instr("PLASMA",n$) a=a+20
 if a>ms a=ms
 print \m$" STAGGERS. TAKING "a" DAMAGE.."\
 ms=ms-a
nuk.mon
 if ms<1 ms=0:pop:gosub clr.item:i$="kill.mon" :dy$=dz$+"spur.combat":link dy$,"misc"
 return
;
nuke
 gosub delay.a:print \\\"THE ROCKET BEGINS TO SPEAK!!"
 gosub delay.a:print \'"Targeting sequence initiated..."'
 gosub delay.a:if not mw print \'"Target acquisition failure..."':return:else print \'"Target acquired. Firing sequence initiated..."'
 gosub delay.a:print \'"Non-adversarial units should seek cover at this time!"'
 gosub delay.a:print \'
Scrambling for cover, you are suddenly hurled thru the air. Fortunately, you
are not looking in the direction of the blast. Un-fortunately, the ground gets
in the way of your flight path.'
 gosub delay.a:print \"You slowly awaken and regain your senses...."
 if instr("*pwr.ar*",ys$) print \"The power armor protected you.":else if hp>1 print \"You suffer "hp/2" damage from the blast!"\"(Too bad you weren't wearing power armor)":hp=hp/2
 if instr("124,",xi$) print \"The RAD suit protects you from radiation.":else print \"You have radiation poisoning!":zw=4:zw$="1":gosub zu$
 ms=0:goto nuk.mon
;
comm
 gosub delay.a
 if instr("FR",lo$) print \"YOU HEAR ONLY STATIC FROM THE COMMUNICATOR..":goto advent
 xz=0:if instr("CM*",ys$) xz=5
 gosub rnd.10a:if (a<xz) or (a=3) then goto malfunction
 if not instr("CM*",ys$) then if len(ys$)<240 ys$=ys$+"CM*"
 print \"The device hums strangely!"
 input @2 "Still want to use it? y/[N]:"i$:if i$<>"Y" goto advent
 gosub delay.a:print \"A tiny voice comes from the device!"
 gosub delay.a:print \'"STANDBY TO BEAM ABOARD..."'
 gosub delay.a:print \"The area fades from view..."
 gosub delay.a:print \"...to be replaced by metal walls!"
 cl=6:cr=1:i$="travel3":dy$=dz$+"spur.misc":link dy$
;
slippers
 gosub delay.a:print \"The slippers glow strangely!"\:gosub delay.a
 a=19:gosub messages:cl=1:cr=1
 i$="travel3":dy$=dz$+"spur.misc":link dy$
;
ammo
 if wr$="" print \"YOU MUST READY YOUR WEAPON FIRST!":goto advent
 i$=mid$(n$,zm+4)
 if x=147 i$="MUSKET"
 if x=148 i$="357 MAG"
 if x=149 i$="44 MAG"
 if x=150 i$="CANNON"
 if not instr(i$,wr$) print \"THIS AMMO IS NOT FOR THE "wr$"!":goto advent
 if instr("STORM",wr$) print \"THE "wr$" DOES NOT USE PHYSICAL AMMO!":goto advent
 if x>146 gosub ammo.b
 i$=mid$(n$,zm+1):vn=val(left$(i$,2)): vl=vn: vm=val(mid$(i$,3,1)
 print \vn" ROUNDS NOW READY: +"vm" DAMAGE"
 if x<147 gosub clr.item
 goto advent

ammo.b
 f$=dx$+"misc.data":open #2,f$
 a=(x-147)*2:position #2,250,pn,201+a:input #2,zz
 if zz<1 print "The "left$(n$,zm-1)" is empty!":close:pop :goto advent
 zz=zz-1:position #2,250,pn,201+a:print #2,zz:close
 print "("zz" refills now left.)"
 return
;
spec.itm
 if x=142 print \"(The vial is empty!)";
 i$=right$("0"+str$(x)+",",4)
 if not instr(i$,"074,076,078,082,097,122,123,124,138,") return
 print \"The "mid$(n$,3)" will automatically be used at the proper time."
 pop:goto advent
;
key
 if (mid$(zu$,7,1)="1") or (mid$(zu$,7,1)="2") then print \"There are only ruins here!":goto advent
 a=4:gosub messages:n=1:goto advent
;
fire
 print \"You sit and warm yourself by the fire.."
 if ps<20 print "Feeling the strength return..":ps=20:if hp<20 hp=hp+4
 goto advent
;
;
lasso
 if (not instr("HORSE",m$)) or (mw=0) print \"You practice with the lasso": goto advent
 if a1>0 if a2>0 if a3>0 print \"Only 3 allies allowed, use ORDER to dismiss one":goto advent
 if instr("=",d1$+d2$+d3$) print \"Only 1 mount per customer":goto advent
 if ms>15 ms=15
 print \"You capture the horse!"
name.hrs
 lu$="":input \"Name your horse (12 char max) :"m$
 if (len(m$)>12) or (len(m$)<4) goto name.hrs
 i$="!@#$%^&*()_-+=[{]}\|:;<,>.?/"
 for x=1 to len(i$):if instr(mid$(i$,x,1),m$) lu$=mid$(i$,x,1)
 next:if lu$<>"" print \"'"lu$"' not allowed in name.":goto name.hrs
 if a1=0 d1$=m$+"|=":a1=ms+5:h1=0:goto lasso.b
 if a2=0 d2$=m$+"|=":a2=ms+5:h2=0:goto lasso.b
 d3$=m$+"|=":a3=ms+5:h3=0
lasso.b
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$" MOUNT"
 print #1, n1$" got a mount!"
 print #1, "Name of the mount- "m$
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 zq=0:mw=0:mf=0:m$="":wy$=""
 goto advent
;
eq.horse
 a=0:i$="@":if x=163 i$="$"
 if not instr("=",d1$+d2$+d3$) print \"Need a mount first..":goto advent
 if instr("=",d1$) if instr(i$,d1$) a=1
 if instr("=",d2$) if instr(i$,d2$) a=1
 if instr("=",d3$) if instr(i$,d3$) a=1
 if a print \"Horse already has one.":goto advent
 if instr("=",d1$) d1$=d1$+i$
 if instr("=",d2$) d2$=d2$+i$
 if instr("=",d3$) d3$=d3$+i$
 i$="Saddle":if x=163 i$="Horse Armor"
 print \"You put the "i$" on the horse.."
 gosub clr.item:goto advent

pr.items
 xi=len(xi$)/4:if xi=0 print \"No Items.":return
 dy$=dw$+"items"
 open #1,dy$
 print:for x=1 to xi
 y=(x*4)-3:a=val(mid$(xi$,y))
 position #1,30,a,2
 input #1,n$:zm=instr("|",n$):if zm n$=left$(n$,zm-1)
 setint(1)
 print right$("   "+str$(x),3)". - "mid$(n$,3)
 if key(1) x=xi:zt$="abort"
 next:close:return
;
clr.item
 xi=xi-1:if xi=0 then xi$="":return
 l=len(xi$)
 if y=1 then xi$=mid$(xi$,5):return
 if (y+4)>l then xi$=left$(xi$,y-1):return
 xi$=left$(xi$,y-1)+mid$(xi$,y+4)
 return
;
zu$
;... input zw=position number, zw$=new value
 zu$="-"+zu$+"-"
 zx$=left$(zu$,zw):zy$=mid$(zu$,zw+2)
 zu$=zx$+zw$+zy$:zu$=mid$(zu$,2,10)
 return
;
malfunction
 print \"A STRANGE BUZZING COMES FROM THE COMMUNICATOR!!"\"A RED LIGHT STARTS FLASHING URGENTLY!"
 gosub clr.item:xi=xi+1:xi$=xi$+"141,"
 for xz=1 to 5:print \:gosub delay.a:next
 i$="malfunction":gosub pulse:print \
 zz$=rnd$:cl=random(lc*100)/100+1:if cl>lc cl=lc
 i$="MALFUNCTION":goto lnk.msc
;
vial
 if (cl=5) and (cr=105) print \"The vial is already full" :goto advent
 a=5:gosub messages
 zz=25:if pr=2 zz=27
 hp=(zz+xp):ps=25:pt=25:pi=25:pe=25:pw=25:pd=25
 if mid$(zu$,3,1)="1" print \"Poison- gone!"
 if mid$(zu$,4,1)="1" print \"Desease- gone!"
 zu$=left$(zu$,2)+"00"+mid$(zu$,5)
 if flag(32) print "zu$="zu$
 gosub clr.item:xi=xi+1:xi$=xi$+"142,":goto advent
;
fl.vial
 print \"You kneel and fill the vial with precious water from the pool."
 gosub clr.item:xi=xi+1:xi$=xi$+"143,":goto advent
;
room.dsp
 print \\\"The Palintar glows softly..."\\\
 xy=(pi+pw)*xp
 if pc=2 xy=xy+20
 if pr=3 xy=xy+30
 if pr=4 xy=xy+20
 if pr=9 xy=xy+10
 if xy<240 goto fail
 print \"A soft voice whispers..'You are now in room "cr"'"
 if cl=1 xu=12
 if cl=2 xu=15
 if cl=3 xu=10
 if cl=4 xu=7
 if (cl=5) or (cl=6) xu=20
 print "("nr" rooms total; in rows of "xu")."\

listrm4
 gosub tim.chk:if (ev-ex)<120 print "Dusk approaches..."
 print\"Room("cr"):[1-"nr", M)ap, Q)uit]";:input @2" :"i$
 if i$="M" f$="c:map."+str$(cl):gosub show.file:goto listrm4
 if i$="" or i$="Q" return
 x=val(i$)
 if x<1 print \"Please enter a number from 1-"nr", M or Q":goto listrm4
 if x>nr print \"1-"nr" rooms only!":goto listrm4
 ready dr$
listrm2
 edit(0)
 input #msg(x),xu$,xu,xv,xy,xz,yw,yx,yy,yz,zt,zs
 if xu$="" goto listrm3
 copy #6,#8
 setint(1)
 print\"Room Number  : "x
 print"Contains     :";:if (xu+xv+xy+xz)>0 then print
 if xu print"Monster- ";:dy$=dw$+"monsters":rl=32:d=xu:gosub rd.file
 if xv print"Item- ";:dy$=dw$+"items":rl=30:d=xv:gosub rd.file
 if xy print"Weapon- ";:dy$=dx$+"weapons":rl=34:d=xy:gosub rd.file
 if xz print"Ration- ";:dy$=dw$+"stores":rl=26:d=xz:gosub rd.file
 if (xu+xv+xy+xz)<1 then print"Nothing"
 print"Openings     :";
 if yw print" North";
 if yx print" South";
 if yy print" West";
 if yz print" East";
 print\\"Room command : ";:if zt=1 print"UP";:else if zt=2 print"DOWN";:else print"NONE";
 if (zt>0) and (zs>0) print" - to #"zs:else if (zt>0) and (zs=0) print" - Shoppe":else print
 gosub rm.name:print"Room Name: "zz$
 print\"Room Description :"\
 copy #8,#0
 print\
listrm3
 if xu$="" print \"[No room here...]"
 goto listrm4

tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto cnf.qt1
 return
cnf.qt1
 mw=0:mf=0:dy$=dz$+"spur.sub":link dy$,"quit"
;
rm.name
 zz=instr("|",xu$):if instr("\|",xu$) zz=0
 zz$=xu$:if zz zz$=left$(xu$,zz-2)
 if left$(zz$,4)<>"THE " then if left$(zz$,2)<>"A " zz$="THE "+zz$
 return
;
rd.file
 open #1,dy$
 position #1,rl,d
 input #1,cb$\d$\f
 d$=mid$(d$,3)
 close
 if instr("monster",dy$) d$=mid$(d$,2):d=instr("|",d$):if d d$=left$(d$,d-2)
 if instr("weapon",dy$) d$=mid$(d$,2)
 print d$:return
;
fail
 print 'A voice whispers, "Thou are not enlightened enough to use the Great Palintar!"'
 input @2\"View enlightenment status? [Y]/n:"i$
 if i$="N" return
 setint(1):print \'
Required Enlightenment status is 240. (Intelligence + Wisdom) times player
level = status, subject to following  additions:

 Druid;    plus 20
 Pixie;    plus 30
 Elf;      plus 20
 Half Elf; plus 10':setint("")

 print \"Your current status="xy
 return
;
;
dropped
 i$="SPUR.USE":dy$=ds$+"spur.logon":link dy$,"quit3"
;
advent
 setint(""):dy$=dz$+"spur.main":link dy$
;
lnk.msc
 dy$=dz$+"spur.misc":link dy$
;
show.file
 setint(1):copy f$:setint(""):return
;
delay.a
 for a=1 to 9000:next:return
;
smart
 print "(You feel a bit smarter)":return
;
rnd.10a
 zz$=rnd$:a=random(999):a=(a/100)+1:return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):ready dr$:return
;
cln.ally
 if (instr("\|/",lu$)) or (instr("-}-",lu$)) or (instr("=[]",lu$)) return
 lc$=""
 if instr(">",lu$) lc$="THE GOD ":if instr("+",lu$) lc$="THE GODDESS"
 lu$=lc$+lu$
 if instr("|",lu$) lu$= left$(lu$,instr("|",lu$)-1)
 return
;
;..input i$- all lower case letters, no spaces
pulse
 b=500:if hl$="" b=800
 for d=1 to 4
 for x=1 to len(i$)
 if d=1 if info(0) print #4,chr$(7);
 print hl$;chr$(asc(mid$(i$,x,1))-32);of$;
 for a=1 to b:next
 print chr$(8);mid$(i$,x,1);
 next
 if d<4 print chr$(8,len(i$));
 next
 return
;
add.log
;.. i$=log message
 open #1,"a:add.log":append #1:print #1,"Spur.use: "i$" @"time$:close
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print \"Compiled..":link "k:system.seg"
;
comp.ck
 print " ok..":return
;

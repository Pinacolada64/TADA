;spur.use.s
 on nocar goto dropped
 public compile

 if info(5) print "spur.use-";:gosub comp.ck
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
 if x=96 i$="PALINTAR":dy$=dz$+"spur.misc6":link dy$
 if (x=131) or (x=132) gosub card:goto advent
 if x=133 goto tool
 if (x=142) and (cl=5) and (cr=105) goto fl.vial
 if x=143 goto vial
 if x=144 goto slippers
 open #1,dy$:position #1,30,x,2
 input #1,n$\it:close
 if instr("ROCKET",n$) gosub rocket:gosub clr.item:goto advent
 zm=instr("|",n$):if zm goto ammo
 if left$(n$,1)="P" goto compass
 gosub spec.itm
 if (left$(n$,1) <> "S") print \"YOU PLAY WITH THE "mid$(n$,3)"..":goto advent
 ep=ep+1:if pi<8 then pi=pi+1:gosub smart
 a=0:if x=114 a=20:it=10:print \"THE BATTLE SHIELD GLOWS!"
 if x=116 a=20:it=10
 zz$="(Max shield rating for you is "
 if sh<100 then it=it*10:sh=sh+it:hs=1:if sh>100+a sh=100+a
 if pc=1 then if sh>25+a print zz$;25+a"%)":sh=25+a
 if (pc=6) or (pc=8) or (pr=3) then if sh>35+a print zz$;35+a"%)":sh=35+a
 if (pr=5) or (pr=6) then if sh>50+a print zz$;50+a"%)":sh=50+a
 print "(New shield rating: "sh"%)"
 if x=116 goto lazer.sh
 print \mid$(n$,3)" used.":gosub clr.item:goto advent
compass
 ep=ep+1
;if cp=0 cp=1:print \"Compass used.":else cp=0:print \"Compass placed in pack."
;if cp=1 print "(USE again to return to pack)"
 cp=not cp:print \"Compass ";:if not cp print "placed in pack."\\"(USE again to return to pack)"
 if cp=1 print "used."
 goto advent
use4
 ep=ep+1:zw=2:zw$="1":if mid$(zu$,2,1)="1" zw$="0"
 if zw$="1" print \"Ring worn! You are hard to see!"\"(USE again to remove)"\\"THE EVIL SENSES YOU MORE CLEARLY!"
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
; pina todo: check for int
 print \"Bingo! Using the tools, you repair the spacesuit!"
 x$="134,":y=instr(x$,xi$):gosub clr.item
 x$="135,":y=instr(x$,xi$):gosub clr.item
 xi=xi+1:xi$=xi$+"122,"
tool.2
 if instr("141,",xi$):x$="141,":y=instr(x$,xi$):gosub clr.item:xi=xi+1 :xi$=xi$+"066,":print \"You repair the communicator!":z=1
 if z=0 print \"Playing with the tools does no good.."
 goto advent
;
card
 if cl<6 goto no.cd
 i$="You slide the card into the slot, and a door softly slides open.."
 if instr("->",lo$) then if x=131 e=1:print \i$:return
 if instr("<-",lo$) then if x=132 w=1:print \i$:return
 if not instr("<-",lo$) then if not instr("->",lo$) goto no.cd
 print \"Sticking the wrong card in the slot gives you an electric shock!":if hp>5 hp=hp-4
 return
no.cd
 print \"(Playing with the security card does no good. :-)":return
;
lazer.sh
 if instr("LAZ.SH",ys$) print \"SHIELD ALREADY ENERGIZED":goto advent
 print \"A SHIMMERING GLOW ENGULFS YOU! (50% defense from lazer fire entire session)"
 if len(ys$)<245 ys$=ys$+"LAZ.SH"
 gosub clr.item:goto advent
;
grenade
 print \"You hurl the grenade!":gosub delay.a
 if not mw print \"It explodes harmlessly.":return
 print \\\"KABOOM!!":gosub delay.a:gosub rnd.10a:a=a+5+(xp*2)
 print \m$" takes "a" damage..":ms=ms-a:goto nuk.mon
;
rocket
 if instr("NUCLEAR",n$) goto nuke
 gosub delay.a:print \\\"SWOOSH!!"\\\:gosub delay.a
 if not mw print "Such pretty fireworks!... Ohhh... Ahhh..."\:return
 gosub rnd.10a:if a<3 print"MISS..."\:return
 print "KABOOOMM!! DEBRIS FLIES! ":gosub delay.a
 if instr("PLASMA",n$) print \"THERE'S A SECONDARY EXPLOSION FROM THE PLASMA!":gosub delay.a
 i$=rnd$:a=random(200)/10:a=a+15+xp
 if instr(";;",wy$) a=(a*2)/3:print \"CRUMMP! AGAINST THE HEAVY ARMOR!"
 if instr("PLASMA",n$) a=a+20
 if a>ms a=ms
 print \m$" STAGGERS, TAKING "a" DAMAGE.."\
 ms=ms-a
nuk.mon
 if ms<1 ms=0:pop:gosub clr.item:i$="kill.mon":dy$=dz$+"spur.combat":link dy$,"misc"
 return
;
nuke
 gosub delay.a:print \\\"THE ROCKET BEGINS TO SPEAK!!"
 gosub delay.a:print \"'Targeting sequence initiated...'"
 gosub delay.a:if not mw print \"'Target acquisition failure..'":return:else print \"'Target acquired. Firing sequence initiated...'"
 gosub delay.a:print \"'Non-adversarial units should seek cover at this time!'"
 gosub delay.a:print \'
Scrambling for cover, you are suddenly hurled through the air. Fortunately, you
are not looking in the direction of the blast. Unfortunately, the ground gets
in the way of your flight path.'
 gosub delay.a:print \"You slowly awaken and regain your senses...."
 if instr("*pwr.ar*",ys$) print \"The power armor protected you.":else if hp>1 print \"You suffer "hp/2" damage from the blast!"\"(Too bad you weren't wearing power armor)":hp=hp/2 
 if instr("124,",xi$) print \"The radiation suit protects you.":else print \"You have radiation poisoning!":zw=4:zw$="1":gosub zu$
 ms=0:goto nuk.mon
;
comm
 gosub delay.a
 if instr("FR",lo$) print \"You hear only static from the communicator..":goto advent
 xz=0:if instr("CM*",ys$) xz=5
 gosub rnd.10a:if (a<xz) or (a=3) then goto malfunction
 if not instr("CM*",ys$) then if len(ys$)<240 ys$=ys$+"CM*"
 print \"The device hums strangely!"
 input @2 "Still want to use it? y/[N]:"i$:if i$<>"Y" goto advent
 gosub delay.a:print \"A tiny voice comes from the device!"
 gosub delay.a:print \"'STANDBY TO BEAM ABOARD..'"
 gosub delay.a:print \"The area fades from view!!"
 gosub delay.a:print \"To be replaced by metal walls!"
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
 i$=mid$(n$,zm+1):vn=val(left$(i$,2)):vl=vn:vm=val(mid$(i$,3,1)
 print \vn" ROUNDS NOW READY: +"vm" DAMAGE"
 if x<147 gosub clr.item
 goto advent

ammo.b
 f$=dx$+"misc.data":open #2,f$
 a=(x-147)*2:position #2,250,pn,201+a:input #2,zz
 if zz<1 print "The "left$(n$,zm-1)" is empty!":close:pop:goto advent
 zz=zz-1:position #2,250,pn,201+a:print #2,zz:close
 print "("zz" refills now left.)"
 return
;
spec.itm
 if x=142 print \"(The vial is empty!)";
 i$=right$("0"+str$(x)+",",4)
 if not instr(i$,"074,076,078,082,097,122,123,124,138,") return
; 074 - inflatable dinghy     122 - spacesuit
; 076 - amulet of life        123 - Geiger counter
; 078 - great coat            124 - radiation suit
; 082 - crystal pendant       138 - space tracker
; 097 - ice crystal
 print \"The "mid$(n$,3)" will automatically be used at the proper time."
 pop:goto advent
;
key
; check wraith master status
 if (mid$(zu$,7,1)="1") or (mid$(zu$,7,1)="2") then print \"There are only ruins here!":goto advent
 a=4:gosub messages:n=1:goto advent
;
fire
 print \"You sit and warm yourself by the fire.."
 if ps<20 print "Feeling the strength return..":ps=20:if hp<20 hp=hp+4
 goto advent
;
pr.items
 close
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
 i$="[] MALFUNCTION []"
 xz=info(2):if xz=0 xz=2
 if xz>1 xz=100
 for yz=1 to 4
 for yx=1 to len(i$):print mid$(i$,yx,1);:for yy=1 to xz:next:next
 for yx=1 to len(i$):print chr$(8)" "chr$(8);:for yy=1 to xz:next:next
 next:print:zz$=rnd$:cl=random(lc*100)/100+1:if cl>lc cl=lc
 i$="MALFUNCTION":goto lnk.msc
;
vial
 if (cl=5) and (cr=105) print \"The vial is already full":goto advent
 a=5:gosub messages
 zz=25:if pr=2 zz=27
 hp=(zz+xp):ps=25:pt=25:pi=25:pe=25:pw=25:pd=25
 if mid$(zu$,3,1)="1" print \"Poison- gone!"
 if mid$(zu$,4,1)="1" print \"Disease- gone!"
 zu$=left$(zu$,2)+"00"+mid$(zu$,5)
 if un=1 print "zu$="zu$
 gosub clr.item:xi=xi+1:xi$=xi$+"142,":goto advent
;
fl.vial
 print \"You kneel and fill the vial with precious water from the pool."
 gosub clr.item:xi=xi+1:xi$=xi$+"143,":goto advent
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
 for a=1 to 4000:next:return
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
compile
 if un=1 print \"Compiled..":link "k:system.seg"
;
comp.ck
 print " ok..":return
;

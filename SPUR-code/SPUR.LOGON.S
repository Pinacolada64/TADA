; spur.logon.s

 public compile
 public quit1
 public quit3
 public return
 
Los.Spur
 kill "a:var":create "a:var"
 store "a:var":clear:recall "a:var"
 on nocar goto quit4

; set up variables:
var.set
 pn=0:sn=0:ew=clock(1):wa=0:ma=0:pa=0:sl=0:tm=0
 vm=0:vn=0:vo=0:vp=0:vt=0:vu=0:vv=0:vw=0
 xw=0:zm=0:zn=0:zo=0:zp=0:zq=0:zu=0:zv=0
 dc$="":n1$="":i$="":m$="":yt$="*":dr$="":du$=dx$
 zv$="":ys$="":wr$="":wx$="":wy$="":wz$=""

; pina added this (copied from gates of spur):
 dm$="g:":ds$="a:":dx$="j:":dz$="a:":dw$="j:"
 if info(5) print "ds$="ds$", dw$="dw$", dx$="dx$", dz$="dz$", du$="du$

 print sc$;
 if info(5) print "spur.logon-";:gosub comp.ck
 a=10:gosub messages

 dy$=dx$+"spur.data"
 open #1,dy$:a=mark(1):close
 if (a) and (info(5)) then dy$=ds$+"spur.control":link dy$,"configure"
 if a print \"Game Closed!":goto lnk.bbs
 open #1,dy$
 input #1,g$,np,go,oh,ol,og,lg$
 input #1,lc,mc,ic,sc,wc,ac,cg
 input #1,pq,sd,mv,td,bd
 input #1,dh,dl:close
 print \"    (Support sub: World of Spur)"\
 dy$=dx$+"spur.users":x=1
 zz=0:open #1,dy$
start3
 position #1,130,x
 input #1,n1$,n,pn:if n=un close:goto login
 if n=0 zz=1
 x=x+1:if x>np close:goto new
 goto start3

new
 if zz=0 then if not(info(5)) print \"Sorry, game is full right now!":goto quit2
 a=9:gosub messages
new_p
 input @0\\"Do you wish to enter the Land? "i$
 if i$="N" goto quit2
 if i$<>"Y" print \"Enter Y or N please..":goto new_p
new2
 print \"Enter your character's name (14 Char. Max.)"
 input @1 "-> " n1$:if len(n1$)>14 print \"Name too long..":goto new2
 if (instr(":",n1$)) or (instr("=",n1$)) or (instr("*",n1$)) print \"Following characters are not allowed; ':' '=' '*'":goto new2
 print \'
You will next  choose a Class and  Race for your player. Do you wish to  view a
descriptive file of each before you do?'
 input " Y/N :"i$:if i$="Y" f$=dx$+"school":gosub show.file
new3
 print \'Please Choose a Class:

1) Wizard      4) Paladin  7) Archer
2) Druid       5) Ranger   8) Assassin
3) Fighter     6) Thief    9) Knight

 Your Choice (1-9): ';
 input i$:pc=val(i$)
 if (pc>9) or (pc<1) goto new3
new4
 print \'Please Choose a Race:

1) Human    4) Elf        7) Dwarf
2) Ogre     5) Hobbit     8) Orc
3) Pixie    6) Gnome      9) Half-Elf

 Your Choice (1-9): ';
 input i$:pr=val(i$)
 if (pr<1) or (pr>9) goto new4
 i$="278 ,28  ,    ,    ,    ,4   ,235 ,345 ,28  "
 if instr(str$(pr),mid$(i$,pc*5-4,4)) print \"Illegal race/class combo!":goto new3
 input @0\"Is all information correct? Y/N:"i$
 if i$<>"Y" input @0\"[R]edo entry or [A]bort? "i$
 if i$="R" goto new2
 if i$="A" goto quit2
;
 setint(1):print \'
You may start  as a Civilian or Outlaw. Civilians  are safe  from  dueling, but
neither  may they  start a duel. Later, You may wish to J)oin a Guild. (SHOP)'
 setint("")
new5
 input \"Which: C)ivy, O)utlaw? "i$
 if i$="C" vv=0
 if i$="O" vv=1
 if (i$<>"C") then if (i$<>"O") print \"Enter C or O please..":goto new5
 i$=str$(vv):n1$=i$+n1$
 print \"(Writing in News log..)"
 yg=pc:yg=(yg-1)*7+1:yi=pr:yi=(yi-1)*8+1
 zw$="WIZARD DRUID  FIGHTERPALADINRANGER THIEF  ARCHER ASSASINKNIGHT "
 zx$=mid$(zw$,yg,7):yg=instr(" ",zx$):if yg zx$=left$(zx$,yg-1)
 zw$="HUMAN   OGRE    PIXIE   ELF     HOBBIT  GNOME   DWARF   ORC     HALF-ELF"
 zw$=mid$(zw$,yi,8):yi=instr(" ",zw$):if yi zw$=left$(zw$,yi-1)
 zx$=zw$+" "+zx$
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$": NEW RECRUIT"
 zw$=str$(un):zz$=mid$(n1$,2)+" (#"+zw$:zz$=zz$+", "+a3$+")"
 if vv=0 zx$=zx$+"- CIVILIAN."
 if vv=1 zx$=zx$+"- OUTLAW!"
 zz=len(zz$):z=len(zx$):if (zz+z)<38 print #1, zz$", "zx$:goto new6
 print #1, zz$\zx$
new6
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]"
 close

status
 print \\"Rolling..";
 gosub getnum:pd=b
 gosub getnum:ps=b
 gosub getnum:pt=b
 gosub getnum:pi=b
 gosub getnum:pw=b
 gosub getnum:pe=b
 goto stat1
 
getnum
 zz$=rnd$:a=0
getnum1
 print ".";
 b=asc(rnd$)-64:if b>17 then b=b-7
 if b=>11 return
 a=a+1:if a<10 then zz$=rnd$:goto getnum1
 b=b+9:if b<11 goto getnum1
 return
 
stat1
 if pc=1 then pw=pw+2:pt=pt-1:pi=pi+2
 if pc=2 then pw=pw+2:ps=ps-1:pi=pi+2
 if pc=3 then pw=pw-1:pt=pt+2:ps=ps+2:pi=pi-1:pd=pd-1:pe=pe+2
 if pc=4 then ps=ps+1:pi=pi+1:pd=pd+1
 if pc=5 then ps=ps+1:pi=pi-1:pw=pw+1
 if pc=6 then pw=pw-1:pd=pd+1:pe=pe+2
 if pc=7 then pd=pd+2:pe=pe-1
 if pc=8 then ps=ps+2:pd=pd-1
 if pc=9 then pt=pt+1:pi=pi+1:pe=pe-1
 if pr=1 then pd=pd+1:ps=ps-1:pi=pi+2:pw=pw+1:pe=pe-1
 if pr=2 then pd=pd-1:ps=ps+3:pt=pt+2:pi=pi-2:pw=pw-1
 if pr=3 then pd=pd-1:ps=ps+1:pw=pw+1
 if pr=4 then pd=pd+2:pt=pt-1:pi=pi+1:pw=pw+2
 if pr=5 then pd=pd+1:ps=ps-1:pi=pi+2:pe=pe+1
 if pr=6 then pd=pd+2:ps=ps-1:pt=pt+1:pi=pi+2
 if pr=7 then pd=pd-1:ps=ps+2:pt=pt+1
 if pr=8 then pd=pd+1:ps=ps+2:pi=pi-1:pw=pw-1:pe=pe+2
 if pr=9 then pd=pd+1:pw=pw+1
 zz$=rnd$:hp=((ps+pd+pt+pi+pw+pe)/6)+random(10):ep=0
 zz$=rnd$:x=random(10):if x>5 then sh=0:ar=0:goto stat2
 zz$=rnd$:sh=random(30):zz$=rnd$:ar=random(30)
stat2
 print \\"Hit Points   :"hp
 print "Strength     :"ps
 print "Dexterity    :"pd
 print "Constitution :"pt
 print "Intelligence :"pi
 print "Wisdom       :"pw
 print "Energy Level :"pe
 print "Shield       :";:if sh print sh"%":else print "None"
 print "Armor        :";:if ar print ar"%":else print "None"
 print \'
Hold while you are entered into the
BOOK of SPUR.....'
 gosub nw.plyr
 
 print \'
SPUR, the almighty and omnipotent,
senses your intrusion into HIS land!!'\
 gosub rd.user
 ai=0:ai$="":xw=0:xw$="":xf=0:xf$="":xi=0:xi$="":xm=0:xm$="":xs=0:xs$=""
 goto login1
 cl=1:cr=0
 gosub dwf.spur
 goto login1.5

; *** Login Routine ***

login
 print 'There is a large .. well .. illusion here, obiously from the great SPUR
himself, somehow you are told to wait, until your ..death(??!!) papers are 
completely in order.  A tingling runs up your spine as you wonder if your spine
will be there, in one piece tomorrow.';
 gosub tim.read
 gosub rd.user
 if n1$=lg$ then if info(5)=0 then if not instr("=",ph$) print '
Suddenly a voice roars, "You were the last Adventurer. You must wait till another passes through!'\:goto quit2
 if xp>24 xp=24:print \"Maximum level=24!"
login1
 gosub set.pa:xo=xf:xo$=xf$
; draw local screen windows:
 if (not td) then text:home:print
 if (not bd) goto login1.5
 poke 35,21
 a$=n1$
 l=len(a$)+12:a=peek(33)-l:a=a/2:l=peek(33)-l:l=l-a
 print #3 @1,22 chr$(45,a)"[ #"right$("   "+str$(pn),4)"-"a$" ]-"chr$(45,l):print #3 @1,1
 gosub tim.chk:gosub screen
login1.5
 xt$="":xt=0:zo=10
;..(zo=carrying capacity)
 if (pr=4) or (pr=7) or (pr=8) zo=9
 if (pr=5) or (pr=6) zo=8
 if pr=3 zo=7
 zz$=mid$(zu$,7,1)
 if instr(zz$,"12") zz$=", Wraith Master of Spur!":else zz$="!"
 print \"Welcome "n1$;zz$
 print \"The last Adventurer was "lg$
 zz$="The Guild of the "
 if (vv=6) or (vv=7) print \zz$"Claw bids":print "you, 'Welcome!' \|/"\
 if (vv=3) or (vv=4) print \zz$"Sword bids":print "you, 'Welcome!' -}----"
 if (vv=8) or (vv=9) print \zz$"Iron Fist bids":print "you, 'Welcome!' ==[]"\
 print \"Current status:"\
 if vv<3 goto no.guild
 if mid$(zu$,10,1)="1" zz$="WILL":else zz$="WILL NOT"
 print "Your character "zz$" follow other guild members."
no.guild
 if instr(left$(zu$,1),"AB") zz$="OFF":else zz$="ON"
 print "Room description: "zz$
 if mid$(zu$,3,1)="0" zz$="are NOT":else zz$="ARE"
 print "You "zz$" poisoned."
 if mid$(zu$,4,1)="0" zz$="are NOT":else zz$="ARE"
 print "You "zz$" diseased."
 if (vv=2) or (vv=4) or (vv=7) or (vv=9) zz$="ON":else zz$="OFF"
 print "Auto duel: "zz$\
 if vv>2 dy$=dx$+"misc.data":open #1,dy$:position #1,250,pn:input #1,i$\zz$ :close:if i$<>"*" print "You followed "i$" to your current location"\
 zz$="":zz=0
 if not instr("067",xi$) zu$=left$(zu$,1)+"0"+mid$(zu$,3)
 if mid$(zu$,8,1)="1" then if not instr("076",xi$) then if not instr("076",ai$) zu$=left$(zu$,7)+"0"+mid$(zu$,9):print \"[ AMULET OF LIFE- GONE!! ]"\
 zz$=mid$(zu$,7,1):zz=val(zz$):if zz<2 goto no.wizgl
 print \"Your Wizard's Glow spell has dissipated":if zz=2 zz$="1":else zz$="0"
 zu$=left$(zu$,6)+zz$+mid$(zu$,8)
no.wizgl
 zz$="":zz=0
 if info(5) print "zu$="zu$
 if a1 zz$=d1$:if a2 zz$=d1$+" and "+d2$:zz=1:if a3 zz$=d1$+", "+d2$+" and "+d3$
 if a1 then if a3 then if not a2 zz$=d1$+" and "+d3$:zz=1
 if not a1 then if a3 zz$=d3$
 zw$=" is":if zz=1 zw$=" are"
 if zz$<>"" print zz$;zw$" waiting for you!"
 gosub ply.loc:gosub strings:tm=0
 if (cl=6) and (cr=792) then dy$=ds$+"spur.ship":link dy$
 if cr then dy$=dz$+"spur.misc":i$="travel3":link dy$,"misc"
 dy$=dz$+"spur.shop":link dy$
;
show.file
; setint(1):copy f$:setint(""):return
 setint(1):open #1,f$:if mark(1) close #1:return
showfl2
 copy (20) #1
 if (eof(1) or key(1)) setint(""):close #1:return
 if not flag(35) goto showfl2
 print "Press [RETURN] ";:get i$:if i$=chr$(13) print " ";
 print chr$(8,16);chr$(32,16);chr$(8,16);
 if i$=" " setint(""):close #1:return
 setint(1):goto showfl2

;
rd.user
 dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,pn
 input #1,n1$,sn,pn,cl,cr,hp
 input #1,ps,pt,pi,pe,pw,pd
 input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 input #1,df,sl,sr:close
 dy$=dx$+"spur.allies"
 open #1,dy$:position #1,78,pn
 input #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 close
 print
 zz$=left$(n1$,1):zr=instr(zz$,"ABZCZZDZE")
 if zr then vv=zr-1:else vv=val(zz$)
 if zr print \"You slowly awaken from your duel loss..."
 n1$=mid$(n1$,2)
 dy$=dx$+"spur.weapons"
 open #1,dy$:position #1,64,pn
 input #1,xw\xw$:close
 dy$=dx$+"spur.stores"
 open #1,dy$:position #1,44,pn
 input #1,xf\xf$:close
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,pn
 input #1,xi\xi$:close
 dy$=dx$+"ally.items"
 open #1,dy$:position #1,84,pn
 input #1,ai\ai$:close
 dy$=dx$+"spur.monsters"
 open #1,dy$:position #1,44,pn
 input #1,xm\xm$:close
 dy$=dx$+"spur.spells"
 open #1,dy$:position #1,44,pn
 input #1,xs\xs$:close
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,pn
 input #1,zu$:close:if zu$="" zu$="0000000000"
 dy$=dx$+"honor"
 open #1,dy$:position #1,10,pn
 input #1,vk:close:if vk=0 gosub set.honor
 return

wr.user
 if sn=0 goto no.sn
 if vv>0 gosub kickout:if zm setint(1):print \'
================================
 Only Civilians are allowed to
 remain in the Shoppe!':goto throw2
; You
; have been  moved to the room
; just outside the shoppe.....
;================================'\:setint("")

 if instr("loot",ys$) gosub kickout:if zm setint(1):print \'
================================
 Shoppe security tells you that
 they do not allow pick-pockets
 to remain in the Shoppe.': goto throw2
; You are politely thrown out.
;================================'\:setint("")

 if (flag(27)+flag(28)+flag(29))>0 gosub kickout:if zm setint(1):print \'
================================
 I see you have access to a Guild
 but are hiding behind the title
 of Civilian.  SHAME on you!'

throw2
 print \' You are thrown out of the Shoppe.
================================'\:setint("")

no.sn
 zz$=str$(vv):n1$=zz$+n1$:if cl=0 cl=1
 if (len(n1$)>15) then n1$=left$(n1$,15)
 dy$=dx$+"spur.users"
 open #1,dy$:position #1,130,pn
 print #1,n1$,sn,pn,cl,cr,hp
 if (not sn) close:return
 print #1,ps,pt,pi,pe,pw,pd
 print #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 print #1,df,sl,sr:close
 dy$=dx$+"spur.allies"
 open #1,dy$:position #1,78,pn
 print #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3:close
 dy$=dx$+"spur.weapons"
 open #1,dy$:position #1,64,pn
 print #1,xw\xw$:close
 dy$=dx$+"spur.stores"
 open #1,dy$:position #1,44,pn
 print #1,xf\xf$:close
 dy$=dx$+"spur.items"
 open #1,dy$:position #1,84,pn
 print #1,xi\xi$:close
 dy$=dx$+"ally.items"
 open #1,dy$:position #1,84,pn
 print #1,ai\ai$:close
 if xm<=10 goto wr.user3
 x=xm-10
 for a=1 to x
 zz$=rnd$:b=random(xm):if b=0 then b=1
 y=(b*4)-3:l=len(xm$)
 if y=1 then xm$=mid$(xm$,5):goto wr.user2
 if (y+4)>l then xm$=left$(xm$,y-1):goto wr.user2
 xm$=left$(xm$,y-1)+mid$(xm$,y+4)
wr.user2
 xm=xm-1
 next:xm=10
wr.user3
 dy$=dx$+"spur.monsters"
 open #1,dy$:position #1,44,pn
 print #1,xm\xm$:close
 dy$=dx$+"spur.spells"
 open #1,dy$:position #1,44,pn
 print #1,xs\xs$:close
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,pn
 print #1,zu$:close
 if yt$<>"*" a$=mid$(n1$,2):i$="LOGON.STAY":gosub lnk.msc4
 x=1:gosub clr.misc
 dy$=dx$+"misc.data"
 if vo>0 then if vp<100 open #1,dy$:position #1,250,pn,17+(vo*3-3):print #1,vp :close
 gosub wr.honor
 return
; 
nw.plyr
 gosub dwf.spur
 f$=dx$+"spur.users"
 open #1,f$
 if sn goto nw.plyr2
 sn=un:x=1
nw.plyr1
 position #1,130,x:input #1,a$,n
 if (not n) then pn=x:goto nw.plyr2
 x=x+1:goto nw.plyr1
nw.plyr2
 position #1,130,pn
 print #1,n1$,sn,pn,1,0,hp
 print #1,ps,pt,pi,pe,pw,pd
 print #1,0,1000,0,0,sh,ar,pc,pr,0,0,0,1
 print #1,df,sl,sr
 close
 dy$=dx$+"elevator":open #1,dy$
 position #1,pn,10:print #1,"q!9.]pT-":close
 gosub quote
 print \"See SPUR ANNEX in the Gates of Spur menu for help files."
 print \"NOTE that inactive players are removed after 2 weeks."
 print \"Standby. Creating account.."
 f$=dx$+"spur.allies"
 open #1,f$
 position #1,78,pn
 for x=1 to 3:print #1,"*,0,0":next
 close:if pn>np then np=pn
 
 a=0:a$=""
 i$="locker":x=84:gosub wr.clr
 i$="ally.items":x=84:gosub wr.clr
 i$="spur.items":x=84:gosub wr.clr
 i$="spur.weapons":x=64:gosub wr.clr
 i$="spur.stores":x=44:gosub wr.clr
 i$="spur.monsters":x=44:gosub wr.clr
 i$="spur.spells":x=44:gosub wr.clr
 i$="spur.time":x=12:gosub wr.clr
 dy$=dx$+"spur.status"
 open #1,dy$:position #1,32,pn:print #1,"0000000000":close
 x=0:gosub clr.misc
 gosub set.honor
 wx$="NEW.USER":gosub tim.read
 return

wr.clr
 f$=dx$+i$:open #1,f$:position #1,x,pn
 print #1,a\a$:close:return
;
set.pa
 pa=ps+pd+pt+pi+pw+pe:pa=pa mod 10
 return
 
dwf.spur
 if lc=0 print "Maze undefined. Create Levels/Rooms and re-initialize.":return
 zz=flag:z1=edit(5)+3072:flag=z1:fill z1,255,0
 f1$=dx$+"d.level1":gosub rd.lvl
 zz$=rnd$:df=random(nr)
 if df=0 then df=pn

dwf
 if df>nr then df=df mod nr
;.. zz$ checks for rooms where we don't want the dwarf
 zz$="*"+str$(df)+"*"
 if flag(df) then if not instr(zz$,"*1*13*14*15*23*24*") goto spur
 df=df+1:goto dwf
spur
 fill z1,255,0
 sl=2:if sl>lc then sl=lc
 f1$=dx$+"d.level"+str$(sl)
 gosub rd.lvl
 zz$=rnd$:sr=random(nr)
 if sr=0 then sr=pn
spur.2
 if sr>nr then sr=sr mod nr
 if flag(sr) then flag=zz:return
 sr=sr+1:goto spur.2
 
rd.lvl
 open #1,f1$
 input #1,ln$,nr,ri
 read #1,z1,255:close:return
;
tim.chk
 ex=clock(1)-ew:if ex=>ev pop:goto quit1
 return
 
tim.read
 dy$=dx$+"spur.time":open #1,dy$
 mt=mv:if mv=0 then mt=0:goto set.time
 position #1,12,un
 input #1,a$,eu
 b$=mid$(" "+date$+" ",2,5)
 print \"Last played on '"a$"', Today is '"b$"'"\
 if a$<>b$ then eu=0
set.time
 close
 if un<>1 goto set.1
 eu=0:if mt=0 then ev=3600:return
 ev=mt:return
set.1
 if mt=0 then mt=clock(2)-clock(1):eu=0
 ev=mt-eu
 if ev>(clock(2)-clock(1)) then ev=clock(2)-clock(1)
 if ev>0 return
 if wx$<>"NEW.USER" zs$=a3$+" tried to re-enter Spur after time expired, @"+time$:gosub log:print \"(Re-entry attempt noted in security log)"
 if wx$="NEW.USER" zs$=a3$+" started character":gosub log
 gosub tim.mess:goto lnk.bbs
 
tim.mess
 print\'
Alas...the sun has set on yet another
adventurer within the Land of Spur.
Wake ye early in the morning after a
long rest to resume your quest!!!'
 return
;
screen
 print #3 @1,23 "LV:      RM:    |PS:     PC:     PW:   "
 print #3 @1,24 "MV:      EP:    |PE:     PD:     PI:   ";
; screen width:
 if peek(33)=40 goto scn.rtn
 print #3 @41,23 "|RT:   IT:   WP:   AR:    SH:    KL:"
 print #3 @41,24 "|XL:   TI:   GH:          DR:    SR:";
scn.rtn
 print #3 @1,21
 return

scn.rst
 if bd poke 35,24
 home:if (not td) print ^
 return
;
quit
 if wz$="WRITE DONE" return
 wz$="WRITE DONE"
 if cr=0 goto quit.a
 if pw<7 then pw=pw+2
 if pi<7 then pi=pi+2
 if ps<10 then ps=ps+2
 if pe<10 then pe=pe+2
 if hp<20 then hp=hp+2
quit.a
 if (mv>0) and (ex=>ev) gosub tim.mess
 print \'SPUR says hold whilst your adventure
is written in the BOOK of SPUR....'
 dy$=dx$+"spur.data"
 open #1,dy$
 print #1,g$,np,go,oh,ol,og,n1$
 print #1,lc,mc,ic,sc,wc,ac,cg
 print #1,pq,sd,mv,td,bd
 print #1,dh,dl:close
 if (not mv) goto quit.b
 eu=eu+ex:a$=left$(date$,5)+"":if left$(cm$,5)<>a$ then eu=0
 dy$=dx$+"spur.time":open #1,dy$
;.. eu=mt: set time to full limit. Prevents multiple plays per day (unless
;   player gets killed)
;----------------------
;.. Drop carrier. Lose remaining time, unless calling long distance.
;.. Q)uit Spur while on line. Lose remaing time
 if sn>0 then if info(0)>0 eu=mt
;.. Suicide. Lose remaining time
 if sn=0 if z=2 if info(5)=0 then eu=mt
 position #1,12,un
 print #1,a$,eu
 close
 
quit.b
 gosub wr.user
 zs$=left$(date$,5)+" "+time$+"#"+left$(str$(un)+"   ",4)+a3$+"/"+mid$(n1$,2)+ ": "+str$(ex/60)+" min."
 if wn zs$=zs$+" [WON GAME]"
 if info(0)+info(5)=0 zs$=zs$+" [CARRIER LOST]"
 if (sn=0) and (z=2) then zs$=zs$+" [SUICIDE, TIMER MAXED]"
 if eu<>mt zs$=zs$+" [TIMER NOT MAXED]"
 gosub log:print \"It is written!":return

quit1
 on nocar goto quit4
 gosub quit
quit2
 gosub scn.rst:goto lnk.bbs

quit3
 gosub quit:goto quit5
quit4
 if n1$<>"" i$="SPUR.LOGON":gosub quit
quit5
 if (left$(i$,5)<>"SPUR.") and (info(0)+info(5)=0) then i$="SPUR.UNKNOWN"
 if left$(i$,5)="SPUR." gosub drp.msg
 gosub scn.rst:set zz$="":recall "a:var"
 link "a:main.seg","term1"

;
ply.loc
 print \"(Just a sec..)"\
 dy$=dx$+"spur.users"
 ta$=">:":tb$=">:":tc$=">:":td$=">:":te$=">:":tf$=">:":th$=">:"
 x=1:open #1,dy$
ply.loc1
 if x=pn goto ply.loc2
 position #1,130,x
 input #1,n2$,ys,yp,yl,yr,yh
 input #1,yi,yi,yi,yw,yw,yd
 if (yr=0) or (ys=0) goto ply.loc2
 if len(n2$)>15 goto ply.loc2
 xu$=str$(yr):zt$=ta$
 if yl=1 i$=ta$:gosub ply.loc5:ta$=i$
 if yl=2 i$=tb$:gosub ply.loc5:tb$=i$
 if yl=3 i$=tc$:gosub ply.loc5:tc$=i$
 if yl=4 i$=td$:gosub ply.loc5:td$=i$
 if yl=5 i$=te$:gosub ply.loc5:te$=i$
 if yl=6 i$=th$:gosub ply.loc5:th$=i$
 if yl=1 then if zt$=ta$ xu=len(tf$):if xu<221 gosub ply.loc4:gosub ply.loc3 :tf$=tf$+xx$+zz$
ply.loc2
 x=x+1:if x>np close:return
 goto ply.loc1
ply.loc3
 zz$=str$(x):xv$="000"+zz$:zz$=right$(xv$,3):zz$=zz$+":"
 if len(zz$)>4 pop:goto ply.loc2
 return
ply.loc4
 xx$=xu$+"="+n2$+":":if len(xx$)>21 pop:goto ply.loc2
 return
ply.loc5
 xu=len(i$):if xu<221 gosub ply.loc4:gosub ply.loc3:i$=i$+xx$+zz$
 return
;
quote
 a=11:gosub messages:input @2"Enter quote -> " i$
 if len(i$)>60 print "TOO LONG!":goto quote
 if i$="" i$="blank":print "Ok, you will be silent.."
 dy$=dx$+"spur.chat":open #1,dy$:position #1,64,pn:print #1,i$:close
 dy$=dw$+"spur.chat":open #1,dy$:position #1,64,pn:print #1,i$:close
 return

; pina - seriously? D:
drp.msg
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$\mid$(n1$,2)" DROPPED CARRIER IN "i$
 if mw print #1,"IN FRONT OF "m$". HP="hp:if hp<10 print #1,"[ SPUR ACCESS REMOVED! ]":flag(26)=0
 print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
 return
;
advent
 dy$=dz$+"spur.main":link dy$
;
lnk.msc4
 dy$=dz$+"spur.misc4":link dy$
;
lnk.bbs
 clear:recall "a:var":kill "a:var":link "Spur.Gates"

return
 return
;
clr.misc
 dy$=dx$+"misc.data":open #1,dy$:position #1,250,pn
 print #1,"*"\:if x=1 close:return
 for a=1 to 60:position #1,250,pn,17+(a*3-3):print #1,0:next
 close:return
;
strings
 if zy=1 print "1]"ta$\"2]"tb$\"3]"tc$\"4]"td$\"5]"te$\"6]"th$\\"Aux 1]"tf$
 return
;
log
 open #1,"c:spur.log":append #1:print #1,zs$:close:return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):return
;
kickout
 zm=0:if (cl<>6) and (cr>0) then return
 if (cl=6) and (cr>0) then if cr<>792 return
 if mm=0 return
 zm=1:if (cl=6) and (cr=0) then cr=584:return
 cr=1:return
;
set.honor
 vk=1000
 if (pr=2) or (pr=8) then vk=750
 if (pr=3) or (pr=4) then vk=1250
wr.honor
 dy$=dx$+"honor"
 open #1,dy$:position #1,10,pn
 print #1,vk:close
 return
;
compile
 if info(5) print "Compiled..":link "k:system.seg"
comp.ck
 print " ok..":return

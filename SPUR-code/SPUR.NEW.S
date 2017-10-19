;spur.new.s

 on nocar goto dropped
 public compile

new2
 print \"Enter your Players name (14 Char. Max.)"
 input @1 "-> " n1$
 if len(n1$)>14 print \"Name too long..":goto new2
 if len(n1$)<3 print \"Name too short..":goto new2
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
You may start  as a Civilian or Outlaw. Civilians  are safe from  dueling, but
neither  may they  start a duel. Later, You may wish to J)oin a Guild.'
 setint("")
new5
 input \"Wich: C)ivy, O)utlaw? "i$
 if i$="C" vv=0
 if i$="O" vv=1
 if (i$<>"C") then if (i$<>"O") print \"Enter C or O please..":goto new5
 i$=str$(vv):n1$=i$+n1$
 print \"(Writing in News log..)"
 yg=pc:yg=(yg-1)*7+1:yi=pr:yi=(yi-1)*8+1
 zw$="WIZARD DRUID  FIGHTERPALADINRANGER THIEF  ARCHER ASSASINKNIGHT "
 zx$=mid$(zw$,yg,7):yg=instr(" ",zx$):if yg zx$=left$(zx$,yg-1)
 zw$="HUMAN   OGRE    PIXIE   ELF     HOBBIT  GNOME   DWARF ORC     HALF-ELF"
 zw$=mid$(zw$,yi,8):yi=instr(" ",zw$):if yi zw$=left$(zw$,yi-1)
 zx$=zw$+" "+zx$
 dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
 print #1, left$(date$,6)yr$" "time$": NEW RECRUIT"
 zw$=str$(un):zz$=mid$(n1$,2)+" (#"+zw$:zz$=zz$+", "+a1$+")"
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
 ai=0:ai$="":xw=0:xw$="":xf=0
 xf$="":xi=0:xi$="":xm=0:xm$="": xs=0:xs$=""
 link ds$+"spur.logon","return"
;
nw.plyr
 gosub dwf.spur
 f$=dx$+"spur.users":open #1,f$
 if sn goto nw.plyr2
 sn=un:x=1
nw.plyr1
 position #1,130,x:input #1,a$,n
 if (not n) then pn=x:goto nw.plyr2
 x=x+1:goto nw.plyr1
nw.plyr2
 gosub nw.plyr9
 f$=dw$+"spur.users":open #1,f$
 gosub nw.plyr9:goto nw.plyr0
nw.plyr9
 position #1,130,pn
 print #1,n1$,sn,pn,1,0,hp
 print #1,ps,pt,pi,pe,pw,pd
 print #1,0,1000,0,0,sh,ar,pc,pr,0,0,0,1
 print #1,df,sl,sr
 close:return

nw.plyr0
 dy$=dx$+"elevator":open #1,dy$
 position #1,pn,10:print #1,"x$3_;sO=":close
 gosub quote
 print \"See SPUR ANNEX in the GAMES menu for help files."
 print \"Note that inactive players are removed after 2 weeks."
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
 gosub clr.misc
 gosub set.honor
 wx$="NEW.USER":gosub tim.read
 return
;
rd.lvl
 open #1,f1$
 input #1,ln$,nr,ri
 read #1,z1,255:close:return
;
tim.read
 dy$=dx$+"spur.time":open #1,dy$
 mt=mv:if mv=0 then mt=0:goto set.time
 position #1,12,un
 input #1,a$,eu
 b$=mid$(" "+date$+" ",2,5)
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
 zs$=a1$+" started character":gosub log
 gosub tim.mess:goto lnk.bbs
;
tim.mess
 print\'
Alas...the sun has set on yet another adventurer within the Land of Spur.
Wake ye early in the morning after a long rest to resume your quest!!!'
 return
;
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
;
quote
 a=11:gosub messages:input @2"Enter quote -> " i$
 if len(i$)>60 print "TOO LONG!":goto quote
 if i$="" i$="blank":print "Ok, you will be silent.."
 dy$=dx$+"spur.chat":open #1,dy$:position #1,64,pn:print #1,i$:close
 dy$=dw$+"spur.chat":open #1,dy$:position #1,64,pn:print #1,i$:close
 return
;
messages
 bk$=dx$+"messages":ready bk$:input #msg(a),i$
 setint(1):copy #6,#0:setint(""):print of$:return
;
clr.misc
 dy$=dx$+"misc.data":open #1,dy$:position #1,250,pn
 print #1,"*"\
;..clear weapon experience
 for a=1 to 60
 position #1,250,pn,17+(a*3-3):print #1,0
 next
;..clear armor & shield in use
 position #1,250,pn,209:print #1,0
 position #1,250,pn,213:print #1,0
;..clear armor & shield condition
 position #1,250,pn,217:print #1,"00000000000000"
 position #1,250,pn,233:print #1,"00000000000000"
 close:return
;
quit2
 pop:gosub scn.rst
;
lnk.bbs
 clear:recall "a:var":link yw$,yy$

log
 open #1,"c:spur.log":append #1:print #1,zs$:close
 return
;
add.log
 open #1,"a:add.log":append #1
 print #1,"SPUR.NEW "i$" @"time$
 close:return
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
; show a disk file. f$ is filename
; f$ is recycled inside routine. No other variables used.
show.file
 setint(1)
 if flag(32) print "File="f$
 open #1,f$:if mark(1) close #1:print \f$" file not found" :return
 f$=""
showfl2
 copy (18) #1
 if (eof(1) or key(1)) goto showfl3
 if f$<>"+" print "More? [Y]/n (+ for non stop):";:get f$:print ""
 if f$=" " goto showfl3
 if (f$="N" or f$="n") goto showfl3
 setint(1):goto showfl2
showfl3
 setint(""):close #1:f$=""
 return
;
dropped
 i$="Dropped carrier":gosub add.log
 gosub scn.rst:set zz$="":recall "a:var"
 link "a:logoff.seg","term1"
;
scn.rst
 if bd poke 35,24
 home:if (not td) print ^
 return
;
compile
 if a$="spur.compile" link "d:spur.compile","return"
 if info(5) print "Compiled..":link "k:system.seg"
 goto dropped
;


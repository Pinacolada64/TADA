; spur.control.s

; last modified 2012/06/14 by pinacolada

 on nocar goto dropped

 public list
 public configure
 public annex.l

gosub compiler
main
 input \"SPUR Sysop Control (?=Menu): "i$
 push main

 if i$="A" goto listally
 if i$="P" goto listplyr
 if i$="I" goto listitem
 if i$="M" goto listmons
 if i$="R" goto room.dsp
 if i$="W" zm=1:goto listwep
 if i$="S" goto listspel
 if i$="F" goto listfood
 if i$="C" goto config
 if i$="G" goto object
 if i$="U" goto printer
 if i$="T" print \"Removed.."
 if i$="Y" goto time.set
 if i$="D" print \"Removed.."
 if i$="Q" goto quit
 if i$<>"?" return

menu
 f$=dx$+"control.menu"
show.file
 setint(1):print \s$\:copy f$:setint(""):return

config
 print \"Configure New System."
 input @0\"Are you sure ?" i$:if i$<>"Y" return
 
configure
 on nocar goto dropped
 gosub config2
 dy$=dz$+"spur.logon":link dy$
 
config2
 print \"Enter the name of your game:"
 input @3\"->"g$
 print \"Make sure "dx$" drive is on-line"
 print "and press [Return]";:get i$
 print \\"Creating files to "dx$" drive..."
 f$=dx$+"spur.time":kill f$
 create f$
 f$=dx$+"spur.monsters":kill f$
 create f$
 f$=dx$+"spur.spells":kill f$
 create f$
 f$=dx$+"spur.weapons":kill f$
 create f$
 f$=dx$+"spur.items":kill f$
 create f$
 f$=dx$+"spur.stores":kill f$
 create f$
 f$=dx$+"spur.allies":kill f$
 create f$
 f$=dx$+"spur.log":kill f$
 create f$
 f$=dx$+"spur.users":kill f$
 create f$
 
 f$=dm$+"mail":ready f$
 bk$=dx$+"spur.books"
 open #1,bk$:a=mark(1):close
 if (not a) goto config3
 create bk$:open #1,bk$:gosub bld.mgfl
 ready bk$
 msg(0)=999:update
config3
 f$=dx$+"weapons":open #1,f$:a=mark(1):close
 b=34:c=10:gosub reset:wc=x-1

 f$=dx$+"items":open #1,f$:a=mark(1):close
 b=30:c=0:gosub reset:ic=x-1

 f$=dx$+"stores":open #1,f$:a=mark(1):close
 b=26:c=0:gosub reset:cg=x-1

 f$=dx$+"spells":open #1,f$:a=mark(1):close
 b=40:c=0:gosub reset:sc=x-1

 f$=dx$+"allies":open #1,f$:a=mark(1):close
 b=26:c=0:gosub reset:ac=x-1

 f$=dx$+"monsters":open #1,f$:a=mark(1):close
 b=32:c=0:gosub reset:mc=x-1

 f$=dx$+"spur.winners":open #1,f$:a=mark(1):close
 if (not a) goto config4
 create f$:open #1,f$:print #1,'
[] [] [] [] [] [] [] [] [] [] []
[]     Conquerors of SPUR     []
[] [] [] [] [] [] [] [] [] [] []':close
 
config4
 x=0
config.lv
 x=x+1:f$="d.level"+str$(x):open #1,f$:a=mark(1):close
 if (not a) goto config.lv
 lc=x-1
 
config5
 f$=dx$+"spur.data":open #2,f$
 input #2,ga$,f,go,oh,ol,og,lg$
 input #2,f,f,f,f,f,f,f
 input #2,sd,pq,mv,td,bd
 input #2,dh,dl:close:kill f$:create f$:open #2,f$
 np=0:lg$=""
 if ga$<>"" goto config5a
 go=1:oh=0:ol=5000:og=0:sd=1:pq=1:mv=0:td=0:bd=1:dh=0:dl=100
config5a
 gosub object
 print #2,g$,np,go,oh,ol,og,lg$
 print #2,lc,mc,ic,sc,wc,ac,cg
 print #2,sd,pq,mv,td,bd
 print #2,dh,dl:close

 print \\"System files created"
 return

; **********************************
; *  Set Variable Game Objectives  *
; **********************************
 
object
 print \"[ Game Objective ]"
 print "Current Game Objective is #"go
 if og<>0 print "Item number is "og
 g1=oh:g2=ol:gosub prt.gold:print "Gold amount is "gd$
 print \'
1. Get out w/Specific Amt. of Gold
2. Get out w/Special Item
3. Get out w/Gold & Item

Please Choose by number (CR=Abort): ';:input @2 i$
 if i$="" return
 a=val(i$):if (a<1) or (a>3) goto object
 go=a
 if a=1 goto object2

object1
 if ic=0 print \"No ITEMS are currently defined.":go=1:goto object2
 dy$=dx$+"items"
object1a
 input \"Item # or [L]ist: "i$
 if i$="L" gosub listitem:goto object1a
 x=val(i$):if (x<1) or (x>ic) print \"Items 1-"ic:goto object1a
 open #1,dy$:position #1,30,x:input #1,cb$\it$\it:close #1:ty$=left$(it$,1):og$=mid$(it$,3)
 if cb$="*" print \"ITEM has been killed":goto object1a
 if ty$<>"T" print \"The ITEM must be a carried Treasure":goto object1a
 i$="JEWEL":gosub chk.obj
 i$="DIAMOND":gosub chk.obj
 i$="GOLD":gosub chk.obj
 i$="SILVER":gosub chk.obj
 i$="COIN":gosub chk.obj
 print \"Item selected is "og$:og=x
 if a=2 then oh=0:ol=0:goto object
 
object2
 input \"Amount of Gold (in Thousands)? "a$:a=val(a$):if a<0 goto object2
 oh=a/10:ol=a mod 10:ol=ol*1000
 if go=1 then og=0
 goto object
 
chk.obj
 if instr(i$,og$) print \"The item can not be "i$:pop:goto object1a
 return
 
reset
 if a create f$
 open #1,f$
 print #1,c:x=1
count
 position #1,b,x
 input #1,cb$
 if cb$="" close:return
 if cb$="*" goto count2
 cb$="1":if x<=c then cb$="2"
 position #1,b,x
 print #1,cb$
count2
 x=x+1:goto count
 
; *******************
; *  List Routines  *
; *******************

listally
 if pq gosub ptr.pmt
 print #o,\"Allies"\
 dy$=dx$+"allies"
 open #1,dy$:x=1
listaly2
 position #1,26,x
 input #1,cb$\x1$\x2,x3
 setint(1)
 i$=" Taken **":if cb$="1" i$=" Free    "
 if cb$="*" goto listaly3
 print #o,right$("   "+str$(x),3)"."i$" Str:"right$(" "+str$(x2),2)" Hit: "x3"0%   Name:"x1$
listaly3
 x=x+1:if (x>ac) or (key(1)) close:return
 goto listaly2

listmons
 if pq gosub ptr.pmt
 print #o,\"Monsters"\
 dy$=dx$+"monsters"
 open #1,dy$:x=1
listmns2
 position #1,32,x
 input #1,cb$\m$\ms,sw
 setint(1)
 if cb$="*" goto listmns3
 ty$=left$(m$,1):m$=mid$(m$,3)
 print #o,right$("   "+str$(x),3)". ";
 print #o,"Strength: "right$(" "+str$(ms),2);
 print #o,"     Special Wep: "right$("  "+str$(sw),3)"       Name: "m$
listmns3
 x=x+1:if (x>mc) or (key(1)) close:return
 goto listmns2

listspel
 if pq gosub ptr.pmt
 print #o,\"Spells"\
 dy$=dx$+"spells"
 open #1,dy$:x=1
listspl2
 position #1,40,x
 input #1,cb$\q$,q2$,q3,q4
 setint(1)
 if (cb$="*") or (cb$="") goto listspl3
 print #o,right$("   "+str$(x),3)". "left$(q$+"                     ",21);right$("    "+str$(q4),4)"g  "str$(q3)"0% "q2$
listspl3
 x=x+1:if (x>sc) or (key(1)) close:return
 goto listspl2

listitem
 if pq gosub ptr.pmt
 print #o,\"Items"\
 dy$=dx$+"items"
 open #1,dy$:x=1
listitm2
 position #1,30,x
 input #1,cb$\it$\it
 setint(1)
 if cb$="*" goto listitm3
 ty$=left$(it$,1):it$=left$(mid$(it$,3)+"                    ",20)
 print #o,right$("   "+str$(x),3)". "it$" Type: "ty$"  "right$("   "+str$(it),3)"g"
listitm3
 x=x+1:if (x>ic) or (key(1)) close #1:return
 goto listitm2

annex.l
 on nocar goto dropped
 o=0:pq=0:zm=0:gosub listwep
 dy$=ds$+"spur.annex":link dy$,"annex"

listwep
 if pq gosub ptr.pmt
 input @2\"Long or short list? [L]/s:"zt$
 print #o,\"   Weapons          "left$(date$,6)yr$\
 i$="ENERGY    BASH/SLASHPOKE/JAB  POLE      PROJECTILEPROXIMITY "
 xv$="012 3  45"
 dy$=dx$+"weapons"
 open #1,dy$:x=1
listwep2
 position #1,34,x
 input #1,cb$\w$\s,d,v\wa
 setint(1)
 if cb$="*" goto listwep3
 xu$=mid$(xv$,wa,1):xu=val(xu$):xu$=mid$(i$,(xu*10)+1,10)
 ty$=left$(w$,1):w$=left$(mid$(w$,3)+"                  ",18)
 if cb$="0" cb$="Player"
 if cb$="1" cb$="Room"
 if cb$="2" cb$="Shop"
 if zm=0 w$=mid$(w$,2)
 zv$=right$("   "+str$(x),3)+". "+w$
 if zt$="S" print #o,zv$" Loc: "cb$:goto listwep3
 yt$=" ":if wa=8 yt$="*"
 print #o,zv$" "right$("   "+str$(v),4)"g  Ease: "s"  Hits: "d;yt$" Type: "xu$"  Loc: "cb$ 
listwep3
 x=x+1:if (x>wc) or (key(1)) close:print \"* Also gets bonus from Ammo":return
 goto listwep2

listfood
 if pq gosub ptr.pmt
 print #o,\"Rations"\
 dy$=dx$+"stores"
 open #1,dy$:x=1
listfd2
 position #1,26,x
 input #1,cb$\gs$\gs
 setint(1)
 if cb$="*" goto listfd3
 ty$=left$(gs$,1):gs$=left$(mid$(gs$,3)+"                  ",18)
 print #o,right$("   "+str$(x),3);". ";
 if ty$="F" print #o,"Food   :";:else if ty$="D" print #o,"Drink  :";:else print #o,"Cursed :";
 print #o,gs$;right$("   "+str$(gs),3)" gold"
listfd3
 x=x+1:if (x>cg) or (key(1)) close:return
 goto listfd2

; pina here: this section is pretty buggy and unclear.
; * b1 apparently does not get initialized so prints garbage
;   for the first bbs user account name. list #s do not increment
;   properly
; * spur character names sometimes have #s as 1st char
;   (they shouldn't get printed, in my opinion)
; * the "xxx - gold" could lose the "-" too.

; also, it seems like the bbs user id# and spur player # columns are swapped?

listplyr
 if pq gosub ptr.pmt
 print #o,"Players:"\
 dy$=dx$+"spur.users":open #1,dy$:x=1
 dt$="k:users":open #2,dt$

; pina here: let's print a header so it's clearer what columns mean.
; also, initialize b1 and see if that fixes the 1st bbs account name.
 print #o\" TLOS                     Dwarf Spur  BBS"
 print #o "  ID     BBS User Name     Room Room  ID          Game Name              Gold"
 print #o " --- --------------------- ---- ---- ---- --------------------------- -------"
lstplyr2
 position #1,130,x

; b1,b2 get read from spur.users here:

; input #1,n$,b1,b2\f\g1,g2,g3,g4\s1,s2,s3
; going to try swapping inputting b2/b1 so they display in proper columns later:
 input #1,n$,b2,b1\f\g1,g2,g3,g4\s1,s2,s3
 setint(1)
 if not b1 goto lstplyr3

; reading from k:users here:
; pina: should b1 increment to display proper user name?
 b1=b1+1

;p1$/p2$ are bbs user first/last names:
 position #2,64,b1:input #2,p1$,p2$

 setint(1)
; this displays tlos id#, then bbs user name:
; although why not use x (loop counter) instead of b1?
; p1$=p1$+" "+p2$:print #o,right$("    "+str$(b1),4)" "left$(p1$+"                     ",21);
 print #o,right$("    "+str$(x),4)" "left$(p1$+" "+p2$+"                      ",22);
; display dwarf room:
; TODO: print "DEAD" if so:
 print #o,right$("    "+str$(s1),4)" ";
; display spur room:
; TODO: print "DEAD" if so:
 print #o,right$("    "+str$(s3),4)" ";
; display bbs account # + game name:
 print #o,right$("    "+str$(b2),4)" ";
; strip # from left of name, if present:
 if val(left$(n$,1)) n$=mid$(n$,2)
 print #o,left$(n$+"                          ",26);
; gosub gold.cnv - inline this once-used subroutine
;gold.cnv
 t1=g1+g3
 t2=g2+g4
 if t2>10000 then t2=t2-10000:t1=t1+1
 b$=str$(t1):a$="0000":if t1=0 then a$="    ":b$=" "
 a$=right$("     "+b$,5)+right$(a$+str$(t2),4)
; return
 print #o,a$
lstplyr3
 x=x+1:if (x>np) or (key(1)) close:return
 goto lstplyr2
 
room.dsp
 input @2\"Rooms on which level "i$
 if i$="" return
 x=val(i$):if (x<1) or (x>lc) print \lc" levels only":goto room.dsp
 i$=str$(x):dr$=dx$+"room.level"+i$:f1$=dx$+"d.level"+i$

listroom
 if pq gosub ptr.pmt
 open #1,f1$:input #1,ln$,nr,ri:close #1:if not nr print \"Level not defined.":return
 dy$=dm$+"mail":ready dy$
 open #1,dr$:a=mark(1):close #1
 if a print \"No rooms to read":return
 input @2\"Start at room # "i$:x=val(i$):if x<1 then x=1
 if x>nr then x=nr
 ready dr$
listrm2
 edit(0)
 input #msg(x),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 if lo$="" goto listrm3
 copy #6,#8
 setint(1)
 print #o,\md$\
 print #o,"Room Number  : "x
 print #o,"Contains     : ";
 if m print #o,"Monster # "m"  ";
 if i print #o,"Item # "i"  ";
 if wp print #o,"Weapon # "wp"  ";
 if fd print #o,"Ration # "fd"  ";
 if (not m) and (not i) and (not wp) and (not fd) print #o,"Nothing";
 print #o
 print #o,"Exits        :";
 if n print #o," North";
 if s print #o," South";
 if w print #o," West";
 if e print #o," East";
 print #o,\\"Room command : ";:if rc=1 print #o,"UP";:else if rc=2 print #o,"DOWN";:else print #o,"NONE";
 if (rc>0) and (rt>0) print #o," - to #"rt:else if (rc>0) and (rt=0) print #o," - Shoppe":else print #o
 print #o,"Room Name    : "lo$
 print #o,\"Room Description :"\
 copy #8,#o
; print #o,\
listrm3
 x=x+1:if (x>nr) or (key(1)) return
 if lo$="" goto listrm2
 if o=0 print md$:input @2"Q=Quit, C/R=Continue: "i$:if i$="Q" return
 goto listrm2

ptr.pmt
 o=0:if info(0) return
 q$="":input @0\"Send output to printer? "q$
 if q$="Y" then o=5
 return
 
printer
 input \"Printer Prompts - [ON] or [OFF] -> "i$
 if i$="ON" then pq=1
 if i$="OFF" then pq=0
 return

time.set
 a=mv/60
 print \"Current time limit: ";:if a print a" mins.":else print "Unlimited"
set.tim1
 input @2\"Enter time limit -> "i$
 if i$="" goto set.tim2
 e=val(i$):if (e<0) or (e>90) print \"Enter 0-90":goto set.tim1
 mv=e*60
set.tim2
 print \"Time limit: ";:if not mv print "Unlimited time":else print mv/60" mins"
 return
 
list
 on nocar goto dropped
 if xl$="listally" gosub listally:goto relink
 if xl$="listmons" gosub listmons:goto relink
 if xl$="listspel" gosub listspel:goto relink
 if xl$="listitem" gosub listitem:goto relink
 if xl$="listwep" gosub listwep:goto relink
 if xl$="listfood" gosub listfood:goto relink
 if xl$="listplyr" gosub listplyr:goto relink
 if xl$="room0" gosub room0:goto relink
 if xl$="levels" gosub levels0:goto relink
 
room0
 xl$="listroom":xn$="ROOMS":zz=flag:z1=edit(5)+3072:fill z1,255,0
rooms
 print \"Rooms on which"
 input @2\"Level #: "i$:if i$="" then flag=zz:return
 x=val(i$):if (x<1) or (x>lc) print \"Levels 1 to "lc" only.":goto rooms
 dr$=dx$+"room.level"+str$(x):f1$=dx$+"d.level"+str$(x):gosub rd.lvl:ready dr$:flag=z1:lx=x
room2
 print \"[ "xn$" ]"
 print \'[R]ebuild Flags  [M]issing Definitions
[D]efined Rooms  [U]naccessible Rooms'
 input \"[L]ist [E]dit [#] [K]ill or [Q]uit: "i$
 if i$="Q" then x=lx:gosub wr.lvl:flag=zz:return
 if i$="L" gosub listroom:i$="L"
 if i$="E" goto ed.room
 if i$="K" goto kil.room
 if i$="R" goto rm.rbld
 if i$="D" goto rm.defn
 if i$="M" goto rm.miss
 if i$="U" goto rm.unac
 x=val(i$):if x>0 goto ed.room1
 goto room2

kil.room
 gosub rd.room
print \"There are "nr" rooms on "mid$(f1$,5)
 input @2\"Kill room # (CR=Abort): "i$:if i$="" goto rooms
 x=val(i$):if (x<1) or (x>nr) goto kil.room
 input @0\"Are you sure? "i$:if i$<>"Y" goto kil.room
 n=0:s=0:e=0:w=0:m=0:i=0:wp=0:fd=0:rc=0:rt=0:lo$=""
 edit(0)
 gosub wr.room
 goto room2

ed.room
 input @2\"Room number (CR=Abort): "i$:x=val(i$):if i$="" goto room2
ed.room1
 if (x<1) or (x>nr) print \"Rooms 1 to "nr" only.":goto ed.room
 gosub rd.room
 if x=1 then rc=2:rt=0

ed.room2
 print \"Room Number "x" of "nr" rooms in Level "lx
 print \"M:Monster #  : "m
 print "I:Item #     : "i
 print "P:Weapon #   : "wp
 print "R:Ration #   : "fd
 print "C:Room Cmd # : ";:if rc=1 print "UP";:else if rc=2 print "DOWN";::else print "NONE";
 if (rc>0) and (rt>0) print " - to #"rt:else if (rc>0) and (rt=0) print " - Shoppe":else print
 print \"N:North exit : ";:if n print "YES":else print "NO"
 print "S:South exit : ";:if s print "YES":else print "NO"
 print "E:East exit  : ";:if e print "YES":else print "NO"
 print "W:West exit  : ";:if w print "YES":else print "NO"
 print \"T:Room Title : "lo$
 print \"D:Room Description: ";:if not edit(2) print "[ NONE ]":else print "[ WRITTEN ]"
room.pmt
 input @2\"Which: (?=List) : "i$
 if i$="?" goto ed.room2
 if i$="M" gosub ed.r.mon
 if i$="I" gosub ed.r.itm
 if i$="P" gosub ed.r.wep
 if i$="R" gosub ed.r.rat
 if i$="C" gosub ed.r.cmd
 if i$="N" then n=not n:if n then c=(x<=ri)*nr+x-ri:gosub set.rmpt
 if i$="S" then s=not s:if s then a=nr-ri:c=x+ri-((x>a)*nr):gosub set.rmpt
 if i$="E" then e=not e:if e then b=x mod ri:c=x+1-((b=0)*ri):gosub set.rmpt
 if i$="W" then w=not w:if w then b=x mod ri:c=x+((b=1)*ri)-1:gosub set.rmpt
 if i$="D" print \"Edit room scenario, 1000 bytes max."\:gosub ed.room3
ed.name
 if i$="T" input \"You are in: "lo$:if len(lo$)>25 print \"Maximum 25 char length exceeded"\:goto ed.name
 if i$<>"" goto ed.room2
 
room.sav
 input \"[S]ave [R]eturn [A]bort: "i$
 if i$="A" goto room2
 if i$="R" goto ed.room2
 if i$<>"S" goto room.sav
 if (not n) and (not s) and (not e) and (not w) and (not rc) print \"Exit MUST be defined from this room!":goto ed.room2
 if lo$="" then lo$="ROOM # "+str$(x):print \"Room name = "lo$
 gosub wr.room:goto room2

ed.room3
 edit(1)
 if edit(2)>1000 print\"Room desc. too long, please shorten."\:goto ed.room3
 if not edit(2) pop:goto ed.room2
 return
 
ed.r.mon
 input \"Monster #: "m
 if (m<0) or (m>mc) print \"Enter 0-"mc:goto ed.r.mon
 if m=0 print \"No monster waiting!"
 return
 
ed.r.itm
 input \"Item #: "i
 if i=0 print \"No item in room!":return
 if (i<6) or (i>ic) print \"Enter 6-"ic:goto ed.r.itm
 return
 
ed.r.wep
 input \"Weapon #: "wp
 if wp=0 print \"No weapon here!":return
 if (wp<11) or (wp>wc) print \"Enter 11-"wc:goto ed.r.wep
 return
 
ed.r.rat
 input \"Ration #: "fd
 if (fd<0) or (fd>cg) print \"Enter 0-"cg:goto ed.r.rat
 if fd=0 print \"No rations in room!"
 return

ed.r.cmd
 input \"Room Command #: "rc
 if (rc<0) or (rc>2) print \"Enter 0, 1, or 2!":goto ed.r.cmd
 if x=1 then rc=2:print \"Ladder can not be edited!":return
 if rc=0 print \"No ladder in this room!":rt=0:return
 if rc=1 print \"Ladder UP!"
 if rc=2 print \"Ladder DOWN!"
 
ed.rc2
 if rc<>0 input "Connect to Room: "rt
 if (rt<1) or (rt>900) goto ed.rc2
 if (rc=1) and (lx=1) then rt=x
 return
 
rm.rbld
 print \"Rebuilding all room flags"\
 fill z1,255,0
 for x=1 to nr
 gosub rd.room
 if lo$="" goto rbld1
 flag(x)=1
 if n then c=(x<=ri)*nr+x-ri:gosub set.rmpt
 if s then a=nr-ri:c=x+ri-((x>a)*nr):gosub set.rmpt
 if e then b=x mod ri:c=x+1-((b=0)*ri):gosub set.rmpt
 if w then b=x mod ri:c=x+((b=1)*ri)-1:gosub set.rmpt
rbld1
 print right$("   "+str$(x),3);chr$(8,3);
 next
 print \\"Rebuild complete."
 gosub wr.lvl
 goto room2
 
rm.defn
 print \"  The following rooms have been defined for level "lx":"\
 for x=1 to nr
 if flag(x) print right$("    "+str$(x),4);
 next
 print \:goto room2
 
rm.miss
 print \"The following rooms can be accessed but have not been defined:"\
 for x=1 to nr
 if (flag(nr+x)) and (not flag(x)) print right$("    "+str$(x),4);
 next
 print \:goto room2
 
rm.unac
 print \"  The following rooms have been defined but can never be accessed:"\
 for x=1 to nr
 if (flag(x)) and (not flag(nr+x)) print right$("    "+str$(x),4);
 next
 print \:goto room2
 
set.rmpt
 flag(nr+c)=1:return
 
rd.room
 edit(0)
 input #msg(x),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 copy #6,#8
 return

wr.room
 a=msg(x):kill #msg(x)
 print #msg(x),lo$,m,i,wp,fd,n,s,e,w,rc,rt
 copy #8,#6
 msg(x)=a:update
 flag(x)=1
 return

levels0
 zz=flag:z1=edit(5)+3072:flag=z1:fill z1,255,0
levels
 print \'[ LEVELS ]

[C]reate [E]dit [A]dd [K]ill [Q]uit: ';:input i$
 if i$="C" goto cr.lvl
 if i$="K" goto kl.lvl
 if i$="A" goto ad.lvl
 if i$="Q" then flag=zz:return
 if i$<>"E" goto levels

ed.lvl
 input \"Level #: "i$:x=val(i$)
 f1$=dx$+"d.level"+i$:gosub rd.lvl
 if ln$="" goto ed.lvl3
ed.lvl2
 print \"Level "x" with "nr" rooms"
 print \"[1] Level Name: "ln$
 print "[2] Room Incr.: "ri\
 input @2\"Which (1-2,CR): "i$
 if i$="1" input \"Level Name: "ln$
 if i$="2" gosub ed.lvl4
 if i$<>"" goto ed.lvl2
 input \"[S]ave [A]bort [R]eturn: "i$
 if i$="A" then goto levels
 if i$="R" goto ed.lvl2
 if i$<>"S" then goto ed.lvl2
 nr=ri*ri:gosub wr.lvl
 goto levels
ed.lvl3
 input @0 \"No data file, Create? "i$
 if i$<>"Y" goto levels
 goto cr.lvl

ed.lvl4
 input @2\"Room Increment (2-30): "i$:if i$="" return
 i=val(i$)
 if (i<2) or (i>30) print \"Illegal dimension":goto ed.lvl4
 print \"This will create a "i"x"i" level with "(i*i)" rooms."
 print '
You MUST alter existing rooms and define
new rooms to accomodate this new grid!'
 input @0\"Is this OK? "i$:if i$<>"Y" return
 ri=i:return

kl.lvl
 input @2\"Level # (CR=Abort): "i$:if i$="" goto levels
 ln=val(i$):if (ln<1) or (ln>lc) goto kl.lvl
 f1$=dx$+"d.level"+str$(ln):gosub rd.lvl
 dr$=dx$+"room.level"+str$(ln)
 print \"Remove "ln$\"With "nr" rooms? ";
 input @0 i$:if i$<>"Y" goto levels
 f$=dm$+"mail":ready f$:kill dr$:kill f1$:print \"Level Killed"
 if ln<>lc goto kl.lvl2
 lc=lc-1
 print \"You MUST now remove access from this Level in Level"lc
 goto rooms
kl.lvl2
 for i=(ln+1) to lc
 f1$=dx$+"room.level"+str$(i):f2$=dx$+"d.level"+str$(i)
 f3$=dx$+"room.level"+str$(i-1):f4$=dx$+"d.level"+str$(i-1)
 dy$="b:xdos"
 use dy$,"R "+f1$+","+f3$
 use dy$,"R "+f2$+","+f4$:next
 print \"Levels Adjusted.":lc=lc-1
 goto levels

ad.lvl
 input @0\"Add a predefined level? "i$
 if i$<>"Y" goto levels
 input \"File name of new Level? "f0$:f0$=dx$+f0$
 open #1,f0$:if mark(1) print \"File not on "dx$" drive.":close:goto ad.lvl
 close:input \"ROOM file name of new level? "f2$:f2$=dx$+f2$
 open #1,f2$:if mark(1) print \"File not on "dx$" drive.":close:goto ad.lvl
 close:f$=dx$+"room.level"+str$(lc+1):f1$=dx$+"d.level"+str$(lc+1)
 print \"Adding new Level #"lc+1
 dy$="b:xdos"
 use dy$,"R "+f0$+","+f1$
 use dy$,"R "+f2$+","+f$
 print \"Checking Monsters, Items, Weapons  and  Rations....."
 for x=1 to nr:z=0:gosub rd.room
 if m>mc then zz$=rnd$:m=random(mc):z=1
 if i>ic then zz$=rnd$:i=random(ic):z=1
 if w>wc then zz$=rnd$:w=random(wc):z=1
 if fd>cg then zz$=rnd$:fd=random(cg):z=1
 if z gosub wr.room
 next:print \"Level Added!":lc=lc+1:goto levels

cr.lvl
 print \"Level Number: "lc+1:ln=lc+1
 f1$=dx$+"d.level"+str$(ln):gosub rd.lvl
 if ln$<>"" print \"Level exists!":goto levels
 input \"Level Name: "ln$
cr.lvl2
 input \"Room Increment (2-30): "i$:ri=val(i$)
 if (ri<2) or (ri>30) print \"Illegal dimension":goto cr.lvl2
 print \"This will create a "ri"x"ri" level with "(ri*ri)" rooms."
 input @0\"Is this OK? "i$:if i$<>"Y" goto levels
 nr=ri*ri
 dr$=dx$+"room.level"+str$(ln):create dr$
 open #1,dr$:gosub bld.mgfl
 ready dr$:msg(0)=nr:update
 f1$=dx$+"d.level"+str$(ln):create f1$:fill z1,255,0
 gosub wr.lvl:lc=lc+1:goto levels

rd.lvl
 open #1,f1$
 input #1,ln$,nr,ri
 read #1,z1,255
 close #1:return

wr.lvl
 open #1,f1$
 print #1,ln$,nr,ri
 write #1,z1,255
 close #1:return
 
bld.mgfl
 ed=edit(5):fill ed,255,0:poke ed,8:poke ed+1,32
 write #1,ed,2:fill ed,255,0:for x=1 to 20:write #1,ed,255:next
 write #1,ed,26:close:return
 
prt.gold
 a$=str$(g1):gd$="0000":if g1=0 then gd$="    ":a$=" "
 gd$=right$("    "+a$,5)+right$(gd$+str$(g2),4)
 return
 
relink
 dt$=ds$+"spur.sysop":link dt$,"relink"
 
quit
 pop:dy$=ds$+"spur.sysop"
 link dy$
 
dropped
 link "a:main.seg","term1"

compiler
 print \"spur.control-ok"
 return
;

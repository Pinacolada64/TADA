;.. spur.backup.s
 public compile
 dr$="c9:"
 open #1,dr$+"backup.date":x=mark(1)
 if x close:print dr$"backup.date file not found"
 if x=0 input #1,i$:close:print \"Files last updated on "i$
start
 on nocar goto dropped
 print \"Spur player files"
 input @2"B)ackup files, R)estore player, Q)uit :"i$
 if i$="Q" or i$="" link "d:spur.annex","system"
 if i$="B" goto cp.spur
 if i$="R" gosub restore:goto start
 print \"Bad entry":goto start
;
cp.spur
 print \"Copying c: to j: directory.."
 f$="c:spur.data":print \f$:open #1,f$
 input #1,g$,np,go,oh,ol,og,lg$
 input #1,lc,mc,ic,sc,wc,ac,cg
 input #1,pq,sd,mv,td,bd
 input #1,dh,dl:close
 f$=dr$+"spur.data":kill f$:create f$:open #1,f$
 print #1,g$,np,go,oh,ol,og,lg$
 print #1,lc,mc,ic,sc,wc,ac,cg
 print #1,pq,sd,mv,td,bd
 print #1,dh,dl:close

 f$="c:spur.users":open #1,f$
 f$=dr$+"spur.users":open #2,f$:if mark(1) close:print \"Backup files not found in j: directory- aborted." :goto cp.spur4
 print "See who played since last backup.."
 zz$="":for a=1 to np
 position #1,130,a
 input #1,n1$,sn,pn,cl,cr,hp
 input #1,ps,pt,pi,pe,pw,pd
 input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,i$
 position #2,130,a
 input #2,n1$,sn,pn,cl,cr,hp
 input #2,ps,pt,pi,pe,pw,pd
 input #2,gh,gl,bh,bl,sh,ar,pc,pr,yy,i$
 if ep<>yy print "#"sn"/"pn", "n1$ :zz$=zz$+right$("00"+str$(a),3)
 next:if zz$="" print \"Nobody played!":close:goto cp.spur4
 print "Player file  ";
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 if (a<1) or (a>np) print \"Bad player number:"a:close:pop:goto cp.spur4
 position #1,130,a
 input #1,n1$,sn,pn,cl,cr,hp
 input #1,ps,pt,pi,pe,pw,pd
 input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 input #1,df,sl,sr
 position #2,130,a
 print #2,n1$,sn,pn,cl,cr,hp
 print #2,ps,pt,pi,pe,pw,pd
 print #2,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 print #2,df,sl,sr
 print a",";:next:close

 print \"Spur.allies  ";
 open #1,"c:spur.allies":open #2,dr$+"spur.allies"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,78,a:input #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 position #2,78,a:print #2,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 print a",";:next:close

 print \"Spur.weapons ";
 open #1,"c:spur.weapons":open #2,dr$+"spur.weapons"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,64,a:input #1,xw\xw$
 position #2,64,a:print #2,xw\xw$
 print a",";:next:close

 print \"Spur.stores  ";
 open #1,"c:spur.stores":open #2,dr$+"spur.stores"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,44,a:input #1,xf\xf$
 position #2,44,a:print #2,xf\xf$
 print a",";:next:close

 print \"Spur.items   ";
 open #1,"c:spur.items":open #2,dr$+"spur.items"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,84,a:input #1,xi\xi$
 position #2,84,a:print #2,xi\xi$
 print a",";:next:close

 print \"Ally.items   ";
 open #1,"c:ally.items":open #2,dr$+"ally.items"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,84,a:input #1,ai\ai$
 position #2,84,a:print #2,ai\ai$
 print a",";:next:close

 print \"Spur.spells  ";
 open #1,"c:spur.spells":open #2,dr$+"spur.spells"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,44,a:input #1,xs\xs$
 position #2,44,a:print #2,xs\xs$
 print a",";:next:close

 print \"Spur.status  ";
 open #1,"c:spur.status":open #2,dr$+"spur.status"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,32,a:input #1,zu$
 position #2,32,a:print #2,zu$
 print a",";:next:close

 print \"Locker       ";
 open #1,"c:locker":open #2,dr$+"locker"
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,84,a:input #1,zt\zw$
 position #2,84,a:print #2,zt\zw$
 print a",";:next:close

 zv$="Honor":print \left$(zv$+"          ",13);
 i$="c:"+zv$:open #1,i$
 i$=dr$+""+zv$:open #2,i$
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,10,a:input #1,zt
 position #2,10,a:print #2,zt
 print a",";:next:close

 zv$="Spur.monsters":print \left$(zv$+"          ",13);
 i$="c:"+zv$:open #1,i$
 i$=dr$+""+zv$:open #2,i$
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,44,a:input #1,zt\zw$
 position #2,44,a:print #2,zt\zw$
 print a",";:next:close

 zv$="Spur.chat":print \left$(zv$+"          ",13);
 i$="c:"+zv$:open #1,i$
 i$=dr$+""+zv$:open #2,i$
 for x=1 to len(zz$)/3:i$=mid$(zz$,(x-1)*3+1,3):a=val(i$)
 position #1,64,a:input #1,zw$
 position #2,64,a:print #2,zw$
 print a",";:next:close
 print \"Updating date file.."
 f$=dr$+"backup.date":kill f$:create f$
 open #1,f$:print #1,da$:close
 print \"Done!"

cp.spur4
 goto start
;
;
restore
 gosub view.dat
 input @2\"Restore which player record? :"i$
 a=val(i$):if a=0 return
 if a>np print \"To high!":goto restore
 print "Restore to active file, as record #["a;:input @2"]:"i$
 zz=val(i$):if zz<1 zz=a
 if zz>np print \"To high":goto restore
 open #1,dr$+"spur.users":if mark(1) close:print \"Backup not found in j: directory- aborted.":return
 print \"Restoring spur.users file. Backup #"a" to active #"zz
 input @2"Ok? [Y]/n:"i$:if i$="N" close:return
 open #2,"c:spur.users"
 position #1,130,a:input #1,n1$,i$
 print \"Restoring "n1$;:input @2" OK? [Y]/n:"i$:if i$="N" close:return
 position #2,130,zz:input #2,a$,sn,i$
 if sn>0 then if a$<>n1$ print "Overwrite "a$;:input @2" OK [Y]/n:"i$:if i$="N" close:return
 print \"Restoring spur.users"
 position #1,130,a
 input #1,n1$,sn,pn,cl,cr,hp
 input #1,ps,pt,pi,pe,pw,pd
 input #1,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 input #1,df,sl,sr
 print "Writing to [c:]";
 gosub wr.user
 open #2,"a:spur.users":x=mark(2)
 if x print ".. a:spur.users not found":close
 if x=0 print "... [a:]":gosub wr.user
 print "Restoring Spur.allies"
 open #1,dr$+"spur.allies":open #2,"c:spur.allies"
 position #1,78,a:input #1,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 position #2,78,zz:print #2,d1$,a1,h1\d2$,a2,h2\d3$,a3,h3
 close
 print "Restoring Spur.weapons file"
 open #1,dr$+"spur.weapons":open #2,"c:spur.weapons"
 position #1,64,a:input #1,xw\xw$
 position #2,64,zz:print #2,xw\xw$
 close
 print "Restoring Spur.stores file"
 open #1,dr$+"spur.stores":open #2,"c:spur.stores"
 position #1,44,a:input #1,xf\xf$
 position #2,44,zz:print #2,xf\xf$
 close
 print "Restoring Spur.items file"
 open #1,dr$+"spur.items":open #2,"c:spur.items"
 position #1,84,a:input #1,xi\xi$
 position #2,84,zz:print #2,xi\xi$
 close
 print "Restoring Ally.items file"
 open #1,dr$+"ally.items":open #2,"c:ally.items"
 position #1,84,a:input #1,ai\ai$
 position #2,84,zz:print #2,ai\ai$
 close
 print "Restoring Spur.spells file"
 open #1,dr$+"spur.spells":open #2,"c:spur.spells"
 position #1,44,a:input #1,xs\xs$
 position #2,44,zz:print #2,xs\xs$
 close
 print "Restoring Spur.status file"
 open #1,dr$+"spur.status":open #2,"c:spur.status"
 position #1,32,a:input #1,zu$
 position #2,32,zz:print #2,zu$
 close
 print "Restoring locker file"
 open #1,dr$+"locker":open #2,"c:locker"
 position #1,84,a:input #1,zt\zw$
 position #2,84,zz:print #2,zt\zw$
 close
 zv$="Honor":print "Restoring "zv$
 i$=dr$+""+zv$:open #1,i$:i$="c:"+zv$:open #2,i$
 position #1,10,a:input #1,zt
 position #2,10,zz:print #2,zt
 close
 zv$="Spur.monsters":print "Restoring "zv$
 i$=dr$+""+zv$:open #1,i$:i$="c:"+zv$:open #2,i$
 position #1,44,a:input #1,zt\zw$
 position #2,44,zz:print #2,zt\zw$
 close
 zv$="Spur.chat":print "Restoring "zv$
 i$=dr$+""+zv$:open #1,i$:i$="c:"+zv$:open #2,i$
 position #1,64,a:input #1,zw$
 position #2,64,zz:print #2,zw$
 close:print \"Done"
 goto start
;
wr.user
 position #2,130,zz
 print #2,n1$,sn,zz,cl,cr,hp
 print #2,ps,pt,pi,pe,pw,pd
 print #2,gh,gl,bh,bl,sh,ar,pc,pr,ep,mk,mm,xp
 print #2,df,sl,sr
 close
 return
;
view.dat
 print \"(Reading Spur system data)"\
 dy$=dx$+"spur.data
 open #1,dy$
 input #1,g$,np,go,oh,ol,og,lg$
 input #1,lc,mc,ic,sc,wc,ac,cg
 input #1,pq,sd,mv,td,bd
 input #1,dh,dl:close
 return

dropped
 recall "a:var"
 link "a:main.seg","term1"

compile
 if a$="spur.compile" link "d:spur.compile","return"
 print "ok..":link "k:system.seg"



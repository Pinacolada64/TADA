
; spur.compile.s
 
 public return
 public compile

 dr$="d:"
 xy=0
; number of modules to compile:
 xz=31

 a$="load.spur":gosub compile1
 a$="spur.annex":gosub compile1
 a$="spur.armory":gosub compile1
 a$="spur.backup":gosub compile1
 a$="spur.bar":gosub compile1
 a$="spur.bar2":gosub compile1
 a$="spur.bar3":gosub compile1
 a$="spur.combat":gosub compile1
 a$="spur.control":gosub compile1
 a$="spur.duel":gosub compile1
 a$="spur.duel2":gosub compile1
;.. spur.gates is not in my installation.
; a$="spur.gates":gosub compile1
 a$="spur.guild":gosub compile1
 a$="spur.logon":gosub compile1
 a$="spur.main":gosub compile1
 a$="spur.misc":gosub compile1
 a$="spur.misc2":gosub compile1
 a$="spur.misc3":gosub compile1
 a$="spur.misc4":gosub compile1
 a$="spur.misc5":gosub compile1
 a$="spur.misc6":gosub compile1
 a$="spur.misc7":gosub compile1
 a$="spur.misc8":gosub compile1
 a$="spur.misc9":gosub compile1
 a$="spur.new":gosub compile1
 a$="spur.ship":gosub compile1
 a$="spur.shop":gosub compile1
 a$="spur.sub":gosub compile1
 a$="spur.sysop":gosub compile1
 a$="spur.use":gosub compile1
 a$="spur.util":gosub compile
 a$="spur.weapon":gosub compile

 print \"Done compiling."
 link dr$+"spur.sysop"

compile1
 i$=dr$+a$
 xy=xy+1
 print \"Module number "xy" of "xz"..";
 f$=i$+".S":open #1,f$:a=mark(1):close
 if a print f$" not found.":return
 f$=i$+".G":open #1,f$:a=mark(1):close
 if a=0 f$="DELETE "+f$:print \f$;:use "a:xdos",f$:print "..OK"
 x$=i$+".s":open #1,x$:print i$": "size(1)*256" bytes":close
 a$="spur.compile"
 print "Compile "i$:link i$,"compile"
;
return
 return
;
compile
 print "ok.."
 link "k:system.seg"


label0
 print 'multi-line
string continuing
on to the next
==================
line'

 rem ---
 print "single-line, un-terminated string
 rem ---

 print 'another multi-line
string... "quoted characters" work
blabla

':rem end of string

 rem separator
 rem ---------

; comment style 2

 print "regular string ending in semicolon; not a comment";: c=3: if x=4 then d=2

''' documentation comment

 ; whatever

label
 print "hi";:print "there" ; test - ";" vs. " ;" makes a difference
 text:home
 a=pdl(0)

label2
 rem comment

label3
 rem another comment

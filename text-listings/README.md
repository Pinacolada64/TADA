# text-listings

The original C64/[modBASIC](https://www.commodoreserver.com/BlogEntryView.asp?EID=EB7662805E4B4A7ABA2623257BCC642E) TADA modules, from before the Python server rewrite--kept for reference and as source material for porting flavor text and game logic. Written with [C64List](http://commodoreserver.com/BlogView.asp?BID=620460DB83BF4CC1AE7FEF4E9AB4A228), an easy-to-read, friendly text format where BASIC code uses `{:labels}` resolved to regular BASIC line numbers, plus a 6510 assembler for assembly language routines.

## Directory contents

`editors/`: Some notable things:

* `tep82.lbl`: Character editor (mostly for fixing bad values written during the "new player" routine). Later, once this becomes modularized, players with _Dungeon Master_ status will be allowed to use this.

* `ltk-editor.lbl`: Possibly going to be abandoned in favor of storing strings under ROM, and using a fancier input routine, once that is fully debugged.

* `teo.lbl`: TADA Object Editor. This file format will possibly be abandoned, but it has the bones of a good idea. If items have been destroyed and need to be re-introduced to the game, or if the value of a treasure needs to be adjusted, a `Dungeon Master` would conceivably use this program to do so.

`includes/`: files used by other files. Saves typing. All the modern programmers do it.

`installers/`: Not really traditional "installers" in the sense of copying files from an archive to directories, they do nevertheless change SEQuential files into RELative ones, usually.

`misc/`: Tests, weird one-off "I wonder how this works" ideas, unfinished stuff, unrealized features, maybe even from other future projects.

`tests/`: Tests of routines, hopefully not littering source code proper, but there's probably some of that, too.

## Assembly language routines

* Module Load: Takes code from "Module 64" from a Compute! article. This setup uses a main BASIC program ("kernel" in my terminology) and is always resident in RAM. The kernel uses lines 1000-. Loadable modules use lines 1-999, "linked" together with the kernel at load time. BASIC variables are preserved between loads (this requires the largest loaded module to be combined with the "kernel" when the kernel is started, which sets top-of-BASIC pointers to save the start-of-variables pointer). Modules can call any subroutine within the kernel ending in a RETURN.
* Input Any: A routine which handles disk file input. Traditionally, e.g. `INPUT #2,x$` will truncate lines of disk file data containing commas or colons, and can't handle binary data (such as my player log file). A SYS call returns all data into a string variable, getting up to a specified number of bytes, either stopping at or ignoring a carriage return.
* Bracket Text: Display a string such as "\[Hello] there" with "Hello" highlighted in a different output color.
* PopStack: Pops `return` addresses off the stack. There are a lot of uses of this in The Land of Spur, unfortunately.
* InString: Replicates `INSTR("search_through","search_for")` function in ACOS, or other BASICs, such as the C128.
* String Array System: By Jeff Jones. This allows strings to be stored beneath ROM. Hopefully it will save some BASIC RAM. I haven't implemented much other than a demo of it being used yet, however.
* Sliding Input: Originally by Creative Micro Designs. With help, I have enhanced this utility to integrate with BASIC. It passes a string from the SYS call to be edited, and unlike `INPUT`, traps against accidental `Clr/Home` keypresses (confirmation is provided if you really _do_ want to erase the string), allows `Inst/Del` usage (while defeating "quote mode"), and `f1` and `f7` move left and right by words. (If the allowed length of the input exceeds the width of the "window" for displaying the input, the input scrolls left or right, hence the name "Sliding Input.") Hit `Return` and the string is passed back to BASIC, replacing the original contents.

## modBASIC highlights

* Parameter passing: `gosub 1000(a,a$)` eliminates lots of temporary variable assignments
* Type-checking: `1000 fn b,b$` (issues a `?type mismatch  error` if the wrong variable type is passed to a routine)
* Local variables (`def c,c$`) avoids the need for doing things like `a=b:b=10:gosub <routine>:c=b:b=a` if there is a variable name clash between two routines.

Most of the variables from TLoS are [documented here](../programming-notes/spur%20variables.txt).

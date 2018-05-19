# TADA

(work in progress)

"Totally Awesome Dungeon Adventure" is a Commodore 64 re-implementation of the Apple BBS game "The Land of Spur." But instead of being a single-player, one-at-a-time, multi-user-dungeon as it was in the dial-up BBS days, I would like to eventually leverage the server-client technology of [CommodoreServer](https://www.commodoreserver.com) to have a real, multi-player game experience.

## Advantages of C64 framework:
* Common kernel routines: code isn't repeated throughout each module as is in TLOS.
* Modular: More, smaller modules make it hopefully easier to write/upgrade routines.
* [modBASIC](https://www.commodoreserver.com/BlogEntryView.asp?EID=EB7662805E4B4A7ABA2623257BCC642E): Parameter-passing and local variables unlike the laundry list of obscure variables used in TLOS, not all of which I have documented yet.
* [C64List](http://commodoreserver.com/BlogView.asp?BID=620460DB83BF4CC1AE7FEF4E9AB4A228): Written in an easy-to-read, friendly text format which can be translated to C64 BASIC, or assembled to 6510 assembly code
* Similar routine labels to TLOS source

## Assembly language routines:
* Module Load: Takes code from "Module 64" from a Compute! article. This setup uses a main BASIC program ("kernel" in my terminology) and is always resident in RAM. The kernel uses lines 1000-. Loadable modules use lines 1-999, "linked" together with the kernel at load time. BASIC variables are preserved between loads (this requires the largest loaded module to be combined with the "kernel" when the kernel is started, which sets top-of-BASIC pointers to save the start-of-variables pointer). Modules can call any subroutine within the kernel ending in a RETURN.
* Input Any: A routine which handles disk file input. Traditionally, e.g. `INPUT #2,x$` will truncate lines of disk file data containing commas or colons, and can't handle binary data (such as my player log file). A SYS call returns all data into a string variable, getting up to a specified number of bytes, either stopping at or ignoring a carriage return.
* Bracket Text: Display a string such as "\[Hello] there" with "Hello" highlighted in a different output color.
* PopStack: Pops `return` addresses off the stack. There are a lot of uses of this in The Land of Spur, unfortunately.
* InString: Replicates `INSTR("search_through","search_for")` function in ACOS, or other BASICs, such as the C128.
* String Array System: By Jeff Jones. This allows strings to be stored beneath ROM. Hopefully it will save some BASIC RAM. I haven't implemented much other than a demo of it being used yet, however.
* Sliding Input: Originally by Creative Micro Designs. With help, I have enhanced this utility to integrate with BASIC. It passes a string from the SYS call to be edited, and unlike `INPUT`, traps against accidental Clr/Home keypresses (confirmation is provided if you really _do_ want to erase the string), allows Inst/Del usage (while defeating "quote mode"), and `f1` and `f7` move left and right by words. (If the allowed length of the input exceeds the width of the "window" for displaying the input, the input scrolls left or right, hence the name "Sliding Input.") Hit `Return` and the string is passed back to BASIC, replacing the original contents.

## Want to play the original game?
It's telnettable: telnet://dura-bbs.net:6359

# TADA

(work in progress)

"Totally Awesome Dungeon Adventure" is a re-implementation of the Apple BBS game "The Land of Spur." But instead of being a single-player, one-at-a-time, multi-user-dungeon as it was in the dial-up BBS days, I would like to eventually leverage the server-client technology of [CommodoreServer](https://www.commodoreserver.com) to have a real, multi-player game experience.

## Advantages of C64 framework:
* Common kernel routines: code isn't repeated throughout each module as is in TLOS.
* Modular: More, smaller modules make it hopefully easier to write/upgrade routines.
* [modBASIC](https://www.commodoreserver.com/BlogEntryView.asp?EID=EB7662805E4B4A7ABA2623257BCC642E): Parameter-passing and local variables unlike the laundry list of obscure variables used in TLOS, not all of which I have documented yet.
* [C64List](http://commodoreserver.com/BlogView.asp?BID=620460DB83BF4CC1AE7FEF4E9AB4A228): Written in an easy-to-read, friendly text format which can be translated or assembled to C64 BASIC or assembly code
* Similar routine labels to TLOS source
* Assembly language routines: Module Load, InString (replicates INSTR() function in ACOS)

Want to play the original game? It's telnettable: telnet://dura-bbs.net:6359

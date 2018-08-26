# % is a wildcard
# $< is the first dependency
# $@ is the target
# $^ is all dependencies

C1541 = c1541
OUTPUT_DISK = test.d81
OUTPUT_PATH = ../text-listings

OBJECTS	= $(OUTPUT_PATH)/boot.prg \
combat-snippets.prg \
misc/stack.prg \
t.bar \
t.bar.olaf \
t.bar.skip \
t.bar.vinney \
t.bash \
t.bonuses \
t.cast \
t.charge \
t.combat \
t.desc \
t.die \
t.drop \
t.encounter \
t.flee \
t.follow \
t.get \
t.get.modbasic \
t.give \
t.heal \
t.inv \
t.lurk \
t.ma.armory \
t.ma.armory.weap \
t.ma.blacksmith \
t.ma.cleric \
t.ma.elevator \
t.ma.gen-store \
t.ma.hq \
t.ma.locker \
t.ma.news-who \
t.ma.wizard \
t.mount \
t.np \
t.order \
t.page \
t.quit \
t.quote \
t.ready \
t.shoppe \
t.startup \
t.stat.basic \
t.take \
t.unready \
t.weapon-info)

3krs.prg: 3-key-rollover-source.lbl

# "t.main" uses symbols from "ml-c500" when {include:'d} in t_np.prg
main: ../assembly-language/ml-c500.lbl ../text-listings/t_np.prg

	wine casm.exe $< -prg:$@ -ovr -verbose
	$(C1541) $(OUTPUT_DISK) -del $@ -write $@

# 'casm' targets are *.lbl files, but only for assembly language
# (c64list3_05.exe has an assembler built in, but it's slightly buggy)
# a convention is that the filename end in "-casm.lbl"
casm: %-casm.lbl
# TODO: establish build rules (mostly the same as "module" target)

# Include build date of module
# date +%b\ %d\ %Y\ %r
# Aug 26 2018 03:12:51 PM

# FIXME: Do this with every module build, make a function of this?
# Must end in CR/LF to keep DOS/wine happy
build-date:
	$(shell echo "print \"`date +%b\ %d\ %Y\ %r`\"\r\n" > build-date_basic.lbl)

# The "make disk" target will add all the *.prg files to a .d81 at once
# TODO: update disk directory timestamp, maybe with
# "cc1541 -f `date <format_code>` (output: "wed jun 27, 2018")?
# -- con: won't work with 1581
# https://bitbucket.org/PTV_Claus/cc1541/src

disk: test.d81
# from 'make' documentation ('files' function):
# If the command required each argument to be on a separate line of the input
# file [which c64list does!], you might write your recipe like this:
program: $(OBJECTS)
	$(file >$@.in) $(foreach O,$^,$(file >>$@.in,$O))
	$(CMD) $(CMDFLAGS) @$@.in
	@rm $@.in

# The "basic" build target builds "*.lbl" files into "*.prg" files,
# then puts them on (currently) "test.d81" disk image, with some
# filename transformation (see "build-plus_file.lbl" for examples)

# So giving "make boot.lbl"...
%.lbl:
# ...should resolve to:
# ($OUTPUT_PATH) is used to cd ../text-listings
#	             wine c64list3_05.exe boot.lbl -prg:boot.prg -ovr -verbose
#	$(shell echo "# wine c64list3_05.exe $(OUTPUT_PATH)/$(basename $@).lbl -prg:$(OUTPUT_PATH)/$(basename $@).prg -ovr -verbose")
	                wine c64list3_05.exe $(OUTPUT_PATH)/$(basename $@).lbl -prg:$(OUTPUT_PATH)/$(basename $@).prg -ovr -verbose
# and
#	           c1541 test.d81 -del "boot" -write "boot.prg" "boot"
# TODO: filename transformations: _ to . (t_main.prg -> t.main.prg, mainly)
#	$(shell echo "# $(C1541) $(OUTPUT_PATH)/$(OUTPUT_DISK) -del $(basename $@) -write $(OUTPUT_PATH)/$(basename $@).prg $(basename $@)")
	                $(C1541) $(OUTPUT_PATH)/$(OUTPUT_DISK) -del $(basename $@) -write $(OUTPUT_PATH)/$(basename $@).prg $(basename $@)

test.d81: $(OBJECTS)
	$(C1541) $(OUTPUT_DISK) \
	-write "boot.prg"		"boot" \
	-write "t_bar.prg"		"t.bar" \
	-write "t_bar_olaf.prg"		"t.bar.olaf" \
	-write "t_bar_skip.prg"		"t.bar.skip" \
	-write "t_bar_vinney.prg"	"t.bar.vinney" \
	-write "t_bash.prg"		"t.bash" \
	-write "t_bonuses.prg"		"t.bonuses" \
	-write "t_cast.prg"		"t.cast" \
	-write "t_charge.prg"		"t.charge" \
	-write "t_combat.prg"		"t.combat" \
	-write "t_desc.prg"		"t.desc" \
	-write "t_die.prg"		"t.die" \
	-write "t_drop.prg"		"t.drop" \
	-write "t_encounter.prg"	"t.encounter" \
	-write "t_flee.prg"		"t.flee" \
	-write "t_follow.prg"		"t.follow" \
	-write "t_get.prg"		"t.get" \
	-write "t_get_modbasic.prg"	"t.get.modbasic" \
	-write "t_give.prg"		"t.give" \
	-write "t_heal.prg"		"t.heal" \
	-write "t_inv.prg"		"t.inv" \
	-write "t_lurk.prg"		"t.lurk" \
	-write "t_ma_armory.prg"	"t.ma.armory" \
	-write "t_ma_armory_weap.prg"	"t.ma.armory.weap"\
	-write "t_ma_blacksmith.prg"	"t.ma.blacksmith" \
	-write "t_ma_cleric.prg"	"t.ma.cleric" \
	-write "t_ma_elevator.prg"	"t.ma.elevator" \
	-write "t_ma_gen-store.prg"	"t.ma.gen-store" \
	-write "t_ma_hq.prg"		"t.ma.hq" \
	-write "t_ma_locker.prg"	"t.ma.locker" \
	-write "t_ma_news-who.prg"	"t.ma.news-who" \
	-write "t_ma_wizard.prg"	"t.ma.wizard" \
	-write "t_mount.prg"		"t.mount" \
	-write "t_np.prg"		"t.np" \
	-write "t_order.prg"		"t.order" \
	-write "t_page.prg"		"t.page" \
	-write "t_quit.prg"		"t.quit" \
	-write "t_quote.prg"		"t.quote" \
	-write "t_ready.prg"		"t.ready" \
	-write "t_shoppe.prg"		"t.shoppe" \
	-write "t_startup.prg"		"t.startup" \
	-write "t_stat_basic.prg"	"t.stat.basic" \
	-write "t_take.prg"		"t.take" \
	-write "t_unready.prg"		"t.unready" \
	-write "t_weapon-info.prg"	"t.weapon-info")
	$@

clean:
# "-" prefix allows 'clean' to continue despite possible missing files
	-rm $(OUTPUT_PATH)/*.prg build-date_basic.lbl $(OUTPUT_PATH)/$(OUTPUT_DISK)
	$(C1541) -format "tada,rs" d81 $(OUTPUT_PATH)/$(OUTPUT_DISK)

# FIXME: not sure this really works
#	$(C1541) -format $(DISKNAME),$(ID) d64 $(DISKFILENAME)
# swap _ for . (/g = global, don't stop on 1st replacement), remove .prg extension:
#	for inputfile in $(EXASWMDIR)/*.swm.prg ; do outputfile=`echo $inputfile | sed "s/_/./g" | sed "s/.prg//"` ; \
#	$(CBMDISK) -attach $@ -write $$inputfile $${outputfile%.*} ; done;

# The "test" target just creates a few files for "make clean" to clean up
test:
	touch $(OUTPUT_PATH)/bla.prg build-date_basic.lbl $(OUTPUT_PATH)/test.d81
# list files in directories $(dirs) to $(files):
# https://www.gnu.org/software/make/manual/make.html#Foreach-Function

# From KDE documentation:
# This simple example sets the variable 'files' to the list of all files in the
# directories in the list 'dirs':
#      dirs := a b c d
#		  foreach <var>,<list>,<text>
#      files := $(foreach dir,$(dirs),$(wildcard $(dir)/*))

# Here TEXT is '$(wildcard $(dir)/*)'. The first repetition finds the value 'a'
# for 'dir', so it produces the same result as '$(wildcard a/*)'; the second
# repetition produces the result of '$(wildcard b/*)'; and the third, that of '$
# (wildcard c/*)'.

	dirs=$(OUTPUT_PATH)
# desired output:
# t_ma_armory.lbl t_ma_armory_weap.lbl [...]
	files=$(foreach dir,$(OBJECTS),$(wildcard $(dir)/*.lbl))

	VAR="bla bla bla"

	echo I am writing to ${OUTPUT_PATH}!
	$(info [Info]: VAR is [$(VAR)])

macy: $(OUTPUT_PATH)/*.lbl
# desired command line (this does work!):
# c1541 test.d81 -write boot.prg boot -write bla.prg bla -dir

# c64 filename: _ -> ., .prg extension removed:
	C64_FILENAME="$(subst _,.,$(patsubst %.lbl,%,$^)"
# filesystem filename:
	FS_FILENAME=$@
# attach target disk image:
	echo $(C1541) $(OUTPUT_PATH)/$(OUTPUT_DISK) \
# delete already existing filename:
	-del "$(C64_FILENAME)" \
# write file from filesystem into disk image with c64 filename transformation:
	-write "$(FS_FILENAME)" "$(C64_FILENAME)")

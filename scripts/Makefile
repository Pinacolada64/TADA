# % is a wildcard
# $< is the first dependency
# $@ is the target
# $^ is all dependencies

OBJECTS	= (text-listings/boot.prg \
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

# uses symbols from ml, includes t_np.prg
t_main.prg: assembly-language/ml-c500.lbl text-listings/t_np.prg

	wine casm.exe $< -prg:$@ -ovr -verbose
	c1541 3-key-rollover.d64 -del $@ -write $@

# FIXME: include build date of module
# must end in CR/LF to keep DOS/wine happy
date: `echo -e datefmt bla bla`\r\n > build-date_basic.lbl

disk: test.d81

test.d81: $(OBJECTS)
	$(C1541) \
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

# swap _ for . (/g = global, don't stop on 1st replacement), remove .prg extension:
#	for inputfile in $(EXASWMDIR)/*.swm.prg ; do outputfile=`echo $inputfile | sed "s/_/./g" | sed "s/.prg//"` ; \
#	$(CBMDISK) -attach $@ -write $$inputfile $${outputfile%.*} ; done;

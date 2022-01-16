import cmd2     # a more advanced version of 'cmd'
# import readline  # for cmd tab-completion

"""
This tests the Cmd2 module, a drop-in replacement for cmd.
https://github.com/python-cmd2/cmd2
"""

# Wonderful! cmd2 provides 'help -v', exactly how I wanted to show help topics:
# Documented commands (use 'help -v' for verbose/'help <topic>' for details):
# ======================================================================================================
# alias                 Manage aliases
# cast                  This is the help_cast() method.
#                       cast <foo>: Cast spell <foo>, assuming you have learned it
# edit                  Run a text editor and optionally open a file with it
# (etc.)

# Asynchronous alerts based on events happening in background threads:
# async_alert - display an important message to the user while they are at the prompt in between commands
# (maybe use for characters talking to you?)


def longest_list_length(items: list):
    """Display items, a group of ellipses, the length is determined by the longest string
     and something else afterwards is printed by the calling routine"""
    # e.g.,
    # item_one ...... foo
    # item_two ...... bar
    # item_three .... baz

    # return longest string length, plus 4 extra for spaces at either end:
    return len(max([x for x in items], key=len)) + 4


class Parser(cmd2.Cmd):
    prompt = '\nTADA> '

    # initialize list of spells:
    SPELL_NAMES = ['list', 'filfre', 'frobnicate', 'frobnitz', 'gnusto', 'melbor', 'trizbort', 'xyzzy']

    # Spell descriptions for 'cast list':
    # Periods are automatically added by 'cast list'
    SPELL_DESCS = ['List the spells you know',
                   'Create a magical light display of fireworks',
                   '',
                   '',
                   'Inscribe a magical spell in your spell book',
                   'Protects magic-users from harm by evil beings',
                   '',
                   '']

    # The default() method is called when none of the other do_*() command methods match.
    def default(self, arg):
        print('I do not understand that command. Type "help" for a list of commands.')

    # A very simple "quit" command to terminate the program:
    def do_quit(self, arg):
        """Quit the game."""
        # arg seems to be unused, but required by the function definition
        print(f'{arg=}')
        return True  # this exits the Cmd2 application loop in Parser.cmdloop()

    def do_cast(self, arg):
        if arg == '':
            print("""In a moment of forgetfulness rivaling the Wizard Frobozz himself,
your struggle to think of a spell name to cast is proving more than you can bear.""")
        else:
            # TODO: test tab-completion in bash
            # would be nice if we could do partial matches with something like:
            # if arg.startsith(arg) == arg.startswith(self.SPELLS)
            if arg in self.SPELL_NAMES:
                print(f"With a wave of your magic wand, you cast '{arg}'.")

                if arg == 'gnusto':
                    print("""
A softly glowing ink pot and quill pen appear, the pen nib scratching at an empty page of
your spell book. After a moment or two, a new spell appears therein, the magicked objects
vanishing.""")

                if arg == 'list':
                    print("Here are the spells you know:\n")
                    longest = longest_list_length(self.SPELL_NAMES)

                    # By default, when we make a field larger with formatters, Python will fill the field with
                    # whitespace characters. We can modify that to be a different character by specifying the
                    # character we want it to be directly following the colon: e.g.,
                    # >>> print("{:*^20s}".format("Sammy"))
                    count = 1
                    for item in self.SPELL_NAMES:
                        name = item + ' '
                        temp = self.SPELL_DESCS[count - 1]
                        if temp == '':
                            desc = '(This space intentionally left blank.)'
                        else:
                            desc = temp + '.'
                        # SPELL_DESCS is zero-based index, so subtract 1 from count
                        # print(f'{count:2}. {item:.<{longest}} {self.SPELL_DESCS[count - 1]}')
                        print(f'{count:2}. {name:.<{longest}} {desc}')
                        count += 1

                if arg == 'melbor':
                    print("Specifying <target> is in the works.")

            else:
                print(f"You don't know the spell '{arg}'.")

    def complete_cast(self, text, line, begidx, endidx):
        """https://pymotw.com/2/cmd/"""
        if not text:
            completions = self.SPELLS[:]
        else:
            completions = [f
                           for f in self.SPELLS
                           if f.startswith(text)
                           ]
        return completions

    def help_cast(self):
        print("This is the help_cast() method.")
        print("cast <foo>: Cast spell <foo>, assuming you have learned it.")

    def help_combat(self):
        print('Combat? How very unlike a Wizard to engage in mindless violence.')

    def do_say(self, arg):
        """Say <message> to other characters in the room.

'say <message>' is required."""
        if arg == '':  # 'if arg is None' does not work
            print("Please specify what to say.")
            return
        else:
            print(type(arg))
            print(f'You say, "{arg.sen}."')


if __name__ == '__main__':
    print("""
cmd2 demo
---------

'help' or '?' displays help, 'help -v' shows verbose help.
Pressing Return/Enter by itself repeats the last command.
""")

    # start parser parsing until returns True, thus ending program
    Parser().cmdloop()

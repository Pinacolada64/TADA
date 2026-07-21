import doctest
import logging
import re
from pathlib import Path
from pprint import pprint

C64LIST_DIRECTIVES = [
    '{include:',
    '{uses:',
    '{addsearchpath:',
    '{buildrev:',
    '{def:',
    '{undef:',
    '{ifdef:',
    '{ifndef:',
    '{else}',
    '{endif}',
    '{usedef:',
    '{asm}',
    '{endasm}',
    '{$:',
    '{%:',
    '{info:',
    '{warning:',
    '{error:',
    '{fatal:',
]

C64_CONSTANTS = {
    # VIC-II
    'BORDER':       '$d020',
    'BACKGROUND':   '$d021',
    'VIC_CTRL1':    '$d011',
    'VIC_CTRL2':    '$d016',
    'VIC_MEMCTRL':  '$d018',
    'RASTER':       '$d012',
    'SPRITE_EN':    '$d015',
    # SID
    'SID_VOL':      '$d418',
    'SID_FREQ1_LO': '$d400',
    'SID_FREQ1_HI': '$d401',
    # CIA1
    'CIA1_PRA':     '$dc00',
    'CIA1_PRB':     '$dc01',
    'CIA1_TOD_HR':  '$dc08',
    'CIA1_TOD_MIN': '$dc09',
    'CIA1_TOD_SEC': '$dc0a',
    'CIA1_TOD_10':  '$dc0b',
    # CIA2
    'CIA2_PRA':     '$dd00',
    # Screen / color RAM
    'SCREEN_RAM':   '$0400',
    'COLOR_RAM':    '$d800',
    # KERNAL
    'CHROUT':       '$ffd2',
    'GETIN':        '$ffe4',
}


def strip_comment(line: str) -> str:
    """
    Strips inline assembly comments (semicolon and everything after).
    Returns the original line unchanged if no comment is present.

    >>> strip_comment('lda #5          ; load 5')
    'lda #5          '

    >>> strip_comment('{const: SCRN $0400}      ; screen RAM')
    '{const: SCRN $0400}      '

    >>> strip_comment('lda #5')
    'lda #5'

    >>> strip_comment('; whole line comment')
    ''
    """
    if ';' in line:
        return line[:line.index(';')]
    return line


def strip_surrounding(line: str, left: str, right: str) -> str:
    """
    Strips exact substrings from left and right of a string.

    >>> strip_surrounding("{def:macro blah @1}", "{def:macro ", "}")
    'blah @1'

    >>> strip_surrounding("{const: BORDER $d020}", "{const: ", "}")
    'BORDER $d020'
    """
    if line.startswith(left):
        line = line[len(left):]
    if line.endswith(right):
        line = line[:-len(right)]
    return line


def is_c64list_directive(line: str) -> bool:
    """
    Returns True if the line is a C64List native directive
    that should be passed through to C64List unchanged.

    >>> is_c64list_directive('{include:somefile.asm}')
    True

    >>> is_c64list_directive('{def:macro border @1}')
    False

    >>> is_c64list_directive('{ifdef:debug}')
    True

    >>> is_c64list_directive('lda #$d020')
    False

    >>> is_c64list_directive('{const: BORDER $d020}')
    False
    """
    stripped = line.strip()
    if stripped.startswith('{def:macro '):
        return False
    for directive in C64LIST_DIRECTIVES:
        if stripped.startswith(directive):
            return True
    return False


def process_constants(code: list,
                      existing: dict = None) -> tuple[dict, list]:
    """
    Processes constant definitions and returns them as a dictionary,
    along with the remaining non-constant code.

    >>> code = ['{const: BORDER $d020}',
    ...         '{const: BACKGROUND $d021}',
    ...         'lda #5',
    ...         'sta BORDER']

    >>> process_constants(code)
    ({'BORDER': '$d020', 'BACKGROUND': '$d021'}, ['lda #5', 'sta BORDER'])

    >>> process_constants(['{const: BORDER $d020}', '{const: BORDER $d021}'])
    Traceback (most recent call last):
        ...
    SyntaxError: Line 2: Duplicate constant 'BORDER'

    >>> process_constants(['{const: SCREEN_RAM $9000}'], existing=C64_CONSTANTS)
    Traceback (most recent call last):
        ...
    SyntaxError: Line 1: Cannot redefine built-in constant 'SCREEN_RAM'

    >>> process_constants(['{const: SCRN $0400}      ; screen RAM'])
    ({'SCRN': '$0400'}, [])
    """
    if existing is None:
        existing = {}
    constants = {}
    non_const_code = []
    for line_num, line in enumerate(code, start=1):
        # strip comment before parsing, but keep original for output
        stripped_line = strip_comment(line).strip()
        if stripped_line.startswith('{const: '):
            inner = strip_surrounding(stripped_line, '{const: ', '}')
            parts = inner.split()
            if len(parts) != 2:
                raise SyntaxError(f"Line {line_num}: "
                                  f"Expected '{{const: NAME value}}', "
                                  f"got '{line}'")
            name, value = parts
            if name in existing:
                raise SyntaxError(f"Line {line_num}: "
                                  f"Cannot redefine built-in constant '{name}'")
            if name in constants:
                raise SyntaxError(f"Line {line_num}: "
                                  f"Duplicate constant '{name}'")
            constants[name] = value
            logging.info(f"Defined constant: {name} = {value}")
        else:
            non_const_code.append(line)  # append original, not stripped
    return constants, non_const_code


def expand_constants(code: list, constants: dict) -> list:
    """
    Replaces constant names in code lines with their values.

    >>> constants = {'BORDER': '$d020', 'BACKGROUND': '$d021'}
    >>> code = ['lda #5', 'sta BORDER', 'sta BACKGROUND']

    >>> expand_constants(code, constants)
    ['lda #5', 'sta $d020', 'sta $d021']
    """
    result = []
    for line in code:
        expanded = line
        for name, value in constants.items():
            expanded = re.sub(rf'\b{name}\b', value, expanded)
        result.append(expanded)
    return result


def process_macros(code: list):
    """
    Processes macro definitions and stores them in a dictionary.

    :param code: A list of lines containing code and macro definitions.

    :returns: A dictionary of macros, keyed by name and parameters.
    :returns: A list of non-macro code lines.

    >>> code = ['{def:macro border @1}',
    ...         'lda @1',
    ...         'sta $d020',
    ...         '{endmacro}',
    ...         '{macro: border #5}',
    ...         'sta $d021']

    >>> process_macros(code=code)
    ({'border @1': ['lda @1', 'sta $d020']}, ['{macro: border #5}', 'sta $d021'])
    """
    macros = {}
    non_macro_code = []
    current_macro = None

    for line_num, line in enumerate(code, start=1):
        # strip comment before parsing, keep original for output
        stripped_line = strip_comment(line).strip()
        logging.info(f"{line_num:3} {line}")

        if stripped_line.startswith('{def:macro '):
            macro_body = []
            logging.info(f'found macro definition: {line=}')
            macro_definition = strip_surrounding(stripped_line,
                                                 left="{def:macro ",
                                                 right="}")
            current_macro = macro_definition
            logging.info(f'after: {macro_definition=}')
            params = [param for param in macro_definition.split()[1:]
                      if param.startswith("@") and param[1].isdigit()]
            logging.info(f"{params=}. {len(params)=}")

            for next_line in code[line_num:]:
                next_stripped = strip_comment(next_line).strip()
                if next_stripped != '{endmacro}':
                    macro_body.append(next_line)  # keep original
                    logging.info(f'{macro_body=}')
                else:
                    logging.info(f"Found 'endmacro'")
                    macros[macro_definition] = macro_body
                    current_macro = None
                    break

            if current_macro:
                raise SyntaxError(f"Line {line_num}: "
                                  f"Unterminated macro definition '{current_macro}'")

        elif stripped_line == '{endmacro}':
            pass  # already consumed by inner loop, skip it

        elif any(line == body_line
                 for macro_body in macros.values()
                 for body_line in macro_body):
            pass  # skip macro body lines

        else:
            # regular code line or C64List directive - pass through
            if is_c64list_directive(stripped_line):
                logging.info(f"Passing C64List directive through: {line}")
            non_macro_code.append(line)  # append original, not stripped

    return macros, non_macro_code


def parse_macro_call(line: str) -> tuple[str, list[str]]:
    """
    Parses a macro call line into a name and argument list.

    >>> parse_macro_call("{macro: border #1}")
    ('border', ['#1'])

    >>> parse_macro_call("{macro: nested_loop #$de #$ad}")
    ('nested_loop', ['#$de', '#$ad'])
    """
    inner = strip_surrounding(line, "{macro: ", "}")
    parts = inner.split()
    name = parts[0]
    args = parts[1:]
    return name, args


def substitute_params(macro_body: list[str], args: list[str]) -> list[str]:
    """
    Replaces @1, @2 etc. in macro body lines with actual arguments.

    >>> substitute_params(['lda @1', 'sta $d020'], ['#5'])
    ['lda #5', 'sta $d020']

    >>> substitute_params(['ldx @2', 'ldy @1', 'dey', 'bne *-2'], ['#$de', '#$ad'])
    ['ldx #$ad', 'ldy #$de', 'dey', 'bne *-2']
    """
    result = []
    for line in macro_body:
        expanded = line
        for i, arg in enumerate(args, start=1):
            expanded = expanded.replace(f"@{i}", arg)
        result.append(expanded)
    return result


def expand_macros(non_macro_code: list, macros: dict) -> list:
    """
    Replaces macro calls in code with their expanded definitions.

    :param non_macro_code: list of lines of code
    :param macros: A dictionary containing defined macros.

    :return: A new list with macros replaced.

    >>> macros = {'nested_loop @1 @2': ['ldx @2', 'ldy @1', 'dey', 'bne *-2']}
    >>> expand_macros(['{macro: nested_loop #$de}'], macros)
    Traceback (most recent call last):
        ...
    SyntaxError: Line 1: Macro 'nested_loop' expects 2 argument(s), but got 1

    >>> expand_macros(['{macro: unknown #1}'], {})
    Traceback (most recent call last):
        ...
    SyntaxError: Line 1: Unknown macro 'unknown'
    """
    new_lines = []
    for line_num, code_line in enumerate(non_macro_code, start=1):
        stripped_line = strip_comment(code_line).strip()
        if stripped_line.startswith("{macro: "):
            name, args = parse_macro_call(stripped_line)

            matching_keys = [key for key in macros if key.split()[0] == name]

            if not matching_keys:
                raise SyntaxError(f"Line {line_num}: Unknown macro '{name}'")

            key = name + "".join(f" @{i + 1}" for i in range(len(args)))

            if key not in macros:
                expected_key = matching_keys[0]
                expected_count = len(expected_key.split()) - 1
                raise SyntaxError(f"Line {line_num}: Macro '{name}' expects "
                                  f"{expected_count} argument(s), "
                                  f"but got {len(args)}")

            expanded = substitute_params(macros[key], args)
            new_lines.extend(expanded)
        else:
            new_lines.append(code_line)  # append original, not stripped

    logging.debug("Code after macro expansion:")
    for line_num, line in enumerate(new_lines, start=1):
        logging.debug(f"{line_num:3}: {line}")
    return new_lines


def preprocess_file(input_path: str) -> str:
    """
    Reads an .asm file, runs it through the full preprocessing pipeline,
    and returns the output file path.

    :param input_path: Path to the input .asm file
    :return: Path to the preprocessed output file
    """
    input_file = Path(input_path)
    output_file = input_file.with_stem(input_file.stem + '_pp')

    logging.info(f"Reading: {input_file}")
    code = input_file.read_text().splitlines()
    logging.info(f"Read {len(code)} lines")

    # Step 1: process and expand constants
    constants, code_after_consts = process_constants(code,
                                                     existing=C64_CONSTANTS)
    all_constants = {**C64_CONSTANTS, **constants}
    logging.debug(f"Constants defined: {len(all_constants)}")

    # Step 2: expand constants throughout remaining code
    code_with_consts = expand_constants(code_after_consts, all_constants)

    # Step 3: process and expand macros
    macros, non_macro_code = process_macros(code_with_consts)
    logging.debug(f"Macros defined: {len(macros)}")

    # Step 4: expand macro calls
    result = expand_macros(non_macro_code, macros)

    logging.info(f"Writing: {output_file}")
    output_file.write_text('\n'.join(result) + '\n')
    logging.info(f"Wrote {len(result)} lines")

    return str(output_file)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Preprocessor for C64List assembly files. '
                    'Handles {const:} and {def:macro} directives '
                    'before passing to C64List.'
    )
    parser.add_argument('input',
                        nargs='?',
                        help='Input .asm file to preprocess')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--test', '-t',
                        action='store_true',
                        help='Run doctests instead of processing a file')

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    if args.test:
        results = doctest.testmod(verbose=True)
        raise SystemExit(0 if results.failed == 0 else 1)

    if not args.input:
        parser.print_help()
        raise SystemExit(1)

    input_file = Path(args.input)

    if not input_file.exists():
        print(f"Error: File not found: {input_file}")
        raise SystemExit(1)

    if input_file.suffix != '.asm':
        print(f"Warning: Input file does not have .asm extension: {input_file}")

    try:
        output_path = preprocess_file(args.input)
        print(f"Preprocessed: {input_file} -> {output_path}")
    except SyntaxError as e:
        print(f"Error: {e}")
        raise SystemExit(1)

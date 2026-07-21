"""
convert C64List symbols file...
    chrout            = $ffd2
    llen              = $0ca4
    ones_digit        = $0ca3

...to Vice label file:
  # al $addr .label
    al $ffd2 .chrout
    al $0c04 .llen
    al $0ca3 .ones_digit
"""
# TODO: accept command-line parameters
# import re
# swap_label_and_address = re.compile(r'(?P<address>\b\w+\b).+=.+(?P<label>\b\w+\b)')

import sys

c64list_labels_filename = sys.argv[1]
vice_labels_filename = sys.argv[2]

try:
    with open(c64list_labels_filename, "r") as symbol_file:
        symbol_data = symbol_file.read()
    print(symbol_data)

    vice_labels = []
    for line_num, text in enumerate(symbol_data.splitlines()):
        parts = text.split()
        if len(parts) != 3:
            continue  # skip blank lines and comments
        label, _, address = parts
        output = f"al {address} .{label}"
        print(output)
        vice_labels.append(output)

    print("Writing labels")
    with open(vice_labels_filename, "w") as f:
        for line, label in enumerate(vice_labels):
            f.write(f'{label}\n')

except FileNotFoundError:
    print(f"{c64list_labels_filename} not found")

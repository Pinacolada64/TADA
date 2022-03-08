#!/bin/env python3

import json
from dataclasses import dataclass
import logging


@dataclass
class Rations(object):
    number: int
    name: str
    kind: str  # magical, standard, cursed
    price: int
    flags: list

    def __str__(self):
        return f'#{self.number} {self.name}'


def read_stanza(filename):
    """
    Read block of data [3 lines] from file
    skipping '#'-style comments; `^` is stanza delimiter

    :return: data[], the info from the file
    """
    count = 0
    line = []
    while count < 3:
        # 'diskin()' discards '#'-style comments
        temp = diskin(filename)
        if temp != "^":
            line.append(temp)
            count += 1
    logging.info("Stanza:")
    count = 0
    for n in line:
        logging.info(f'{count=} {n=}')
        count += 1
    return line


def diskin(filename):
    # get a line of data from disk file, discarding '#'-style comments
    while True:
        data = filename.readline().strip('\n')
        if data.startswith("#") is False:
            logging.info(f'keep {data=}')
            return data
        else:
            logging.info(f'toss {data=}')


def convert(txt_filename, ration_json_filename):
    write = True

    ration_kind = {"F.": "food",
                   "D.": "drink",
                   "C.": "cursed"}

    ration_flags = {"x": "future expansion"}

    with open(txt_filename) as file:
        debug = False
        ration_list = []
        # get ration count:
        # enter a state where it's only looking for an integer value [ration count]
        num_rations = 999  # some unrealistic number to serve as a flag
        while num_rations == 999:
            # discard '#'-style comments:
            data = diskin(file)
            if debug:
                print(f'{data=}')
            break
        # hoping for an integer here:
        num_rations = int(data)
        if debug:
            print(f'{num_rations=}')
        # I eliminated "^" record separators in this file
        # _ = diskin(file)
        count = 0
        """
        sample data:
        TODO: finish this
        """
        # capture ration names, then convert to lowercase with .lower():
        while count < num_rations:
            count += 1
            data = read_stanza(file)
            # 1=active:
            status = int(data[0])
            # info: ration kind, name, flags
            info = data[1]
            # kind = "F."ood / "D."rink / "C."ursed
            kind = ration_kind[info[:2]]

            flag = info.rfind("|")
            start_name = 2
            if flag == -1:  # not found
                flag_list = None
                name = info[start_name:]
                logging.info("(No flags)")
            else:
                # '|' in ration name. it has ration flags:
                # trim name to before '|':
                # can also do: ration[start_name:ration.find('|')].rstrip()
                name = info[start_name:flag].rstrip()
                # clear per-ration flag list:
                flag_list = []
                # parse all the flags after the | symbol,
                # add their English keywords to flag_list
                logging.info(f'Flags: {info[flag + 1:]}')
                for k, v in ration_flags.items():
                    if k in info[flag + 1:]:
                        logging.info(f'with flag: {k=} {v=}')
                        flag_list.append(v)
            price = int(data[2])
            # toss "^" data block separator:
            # _ = diskin(file)
            print(f"""Parsed input:\n
{count=}
{name=}
{kind=}
{price=}
{flag_list=}
""")

            # TODO: maybe descriptions later
            """
            descLines = []
            moreLines = True
            while moreLines:
                line = diskin(file)
                if line != "^":
                    descLines.append(line)
                else:
                    moreLines = False
            ration_data['desc'] = " ".join(descLines)
            """

            ration_data = {"number": count,
                           'name': name,
                           'kind': kind,  # food / drink/ cursed
                           "price": price,
                           'flags': flag_list
                           }

            if debug:
                name = ration_data['name']
                kind = ration_data['kind']
                try:
                    flags = ration_data['flags']
                except ValueError:
                    flags = '(None)'
                logging.info(f'{count=} {name=} {kind=} {flags=}')
            # add based on dataclass:
            ration = Rations(**ration_data)
            logging.info(f"*** processed ration '{ration_data['name']}'")
            ration_list.append(ration)
            if debug:
                # if count % 20 == 0:
                _ = input("Hit Return: ")

        if write is True:
            with open(ration_json_filename, 'w') as ration_json:
                json.dump(ration_list, ration_json,
                          default=lambda o: {k: v for k, v in o.__dict__.items() if v}, indent=4)
            logging.info(f"wrote '{ration_json_filename}'")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] | %(message)s')
    logging.info("Logging is running")

    convert('rations.txt', 'rations.json')

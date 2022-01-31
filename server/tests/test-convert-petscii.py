import sys
import cbmcodecs2

if __name__ == '__main__':
    filename = sys.argv[1] if len(sys.argv) > 1 else None

    if filename is None:
        print("Please specify a .seq file to convert from PetSCII and display.")
        exit(1)

    try:
        with open(filename, encoding='petscii_c64en_lc') as f:
            count = 0
            for line in f:
                count += 1
                if count % 20 == 0:
                    _ = input('Press Enter to continue: ')
                    count = 0
                print(line.strip('\n'))
    except FileNotFoundError:
        print(f'{filename} does not exist. Exiting.')
        exit(1)

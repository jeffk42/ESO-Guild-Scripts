"""
Script to convert the ESO Guild Bank Ledger add-on's data file (GBLData.lua)
to two tab-delimited files: one containins all transactions, and one containing
just the bank's gold deposits for raffle purposes.
"""

import argparse
import os
import re


def strip_lua(input_str: str) -> str:
    r_str = re.sub(r'^GBLDataSavedVariables\s*=\n', '', input_str, flags=re.MULTILINE)
    r_str = re.sub(r'^\s*{\n', '', r_str, flags=re.MULTILINE)
    r_str = re.sub(r'^\s*},?\n', '', r_str, flags=re.MULTILINE)
    r_str = re.sub(r'^\s*\[\".*\"\]\s=.*\n', '', r_str, flags=re.MULTILINE)
    r_str = re.sub(r'^.*= \"', '', r_str, flags=re.MULTILINE)
    r_str = re.sub(r'\\t', '\t', r_str, flags=re.MULTILINE)
    r_str = re.sub(r'\",\n', '\n', r_str, flags=re.MULTILINE)
    return r_str


def lua2csv(source_file: str, dest_file: str):
    """
    Parameters
    ----------
    source_file
        The path to the source file to be converted
    dest_file
        The path to the converted file for output
    """
    with open(source_file, 'r') as reader:
        orig_lua = reader.read()

    all_content = strip_lua(orig_lua)

    dest_split = dest_file.split('.', 1)
    dest_file_raffle = dest_split[0] + '_raffle.' + dest_split[1]

    with open(dest_file, 'w') as writer:
        writer.write(all_content)

    raffle_content = re.sub(r'^[0-9]+\t@.+\t(?:(?!dep_gold).)+\t.*\t.*\t.*\t.*\t.*\t.*\n', '', all_content, flags=re.MULTILINE)

    with open(dest_file_raffle, 'w') as writer:
        writer.write(raffle_content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script that converts the ESO GBLData.lua file to a CSV",
    )

    # Add the arguments:
    #   - source_file: the source file we want to convert
    #   - dest_file: the destination where the output should go

    # Note: the use of the argument type of argparse.FileType could
    # streamline some things
    parser.add_argument(
        'source_file',
        help='The location of the source '
    )

    parser.add_argument(
        '--dest_file',
        help='Location of dest file (default: source_file appended with `_unix`',
        default=None
    )

    # Parse the args (argparse automatically grabs the values from
    # sys.argv)
    args = parser.parse_args()

    s_file = args.source_file
    d_file = args.dest_file

    # If the destination file wasn't passed, then assume we want to
    # create a new file based on the old one
    if d_file is None:
        file_path, file_extension = os.path.splitext(s_file)
        d_file = f'{file_path}_unix{file_extension}'

    lua2csv(s_file, d_file)
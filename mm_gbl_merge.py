import argparse
import re

GUILD_NAME = "AK Tamriel Trade"
RANK_FILTER = 1

class UserData:
  def __init__(self, username):
    self.username = username
    self.sales = 0
    self.purchases = 0
    self.taxes = 0
    self.rank = 0
    self.deposits = 0
    self.donations = 0

users = {}

def parse_data(gbl_file: str, mm_file: str, d_file: str):
    mm_lines = []
    mm_line_pos = 1
    with open(mm_file, 'r') as reader:
        mm_lines = reader.readlines()
    in_guild = False
    while not in_guild and mm_line_pos <= len(mm_lines):
        if re.match(rf'^\s*\[\"{GUILD_NAME}\"]\s=\s*$', mm_lines[mm_line_pos]) != None:
            in_guild = True
        mm_line_pos = mm_line_pos + 1
    
    # Account for open bracket
    if in_guild:
        mm_line_pos = mm_line_pos + 1
    
    while in_guild and mm_line_pos <= len(mm_lines):
        if re.match(r'^\s*\}\s*,$', mm_lines[mm_line_pos]):
            in_guild = False
        elif (match := re.match(r'^\s*\[[0-9]+]\s=\s\"(\S+)\",$', mm_lines[mm_line_pos])) is not None:
            user_values = match.group(1).split('&')
            new_user = UserData(user_values[0])
            new_user.sales = user_values[1]
            new_user.purchases = user_values[2]
            if len(user_values) == 5:
                new_user.taxes = user_values[3]
                new_user.rank = user_values[4]
            else:
                new_user.taxes = 0
                new_user.rank = user_values[3]

            users[user_values[0]] = new_user
        mm_line_pos = mm_line_pos + 1



    gbl_lines = []
    gbl_line_pos = 1
    with open(gbl_file, 'r') as reader:
        gbl_lines = reader.readlines()
    in_guild = False
    while not in_guild and gbl_line_pos <= len(gbl_lines):
        if re.match(rf'^\s*\[\"{GUILD_NAME}\"]\s=\s*$', gbl_lines[gbl_line_pos]) != None:
            in_guild = True
        gbl_line_pos = gbl_line_pos + 1
    
    # Account for open bracket
    if in_guild:
        gbl_line_pos = gbl_line_pos + 1
    
    while in_guild and gbl_line_pos <= len(gbl_lines):
        if re.match(r'^\s*\}\s*,$', gbl_lines[gbl_line_pos]):
            in_guild = False
        elif (match := re.match(r'^\s*\[[0-9]+\]\s=\s\"([0-9]+)\\t(@.+)\\t([a-z_]+)\\t([0-9nil]*)\\t([0-9nil]*)\\t(.*)\\t(.*)\\t([0-9\.nil]*)\\t.*$', gbl_lines[gbl_line_pos])) is not None:
            # group1: timestamp
            # group2: username
            # group3: transaction type
            # group4: gold amount (dep/wd) or nil
            # group5: item dep/wd count or nil
            # group6: item desc
            # group7: item link
            # group8: per item value (mm)

            if match.group(2) not in users.keys():
                print('User not found: ' + match.group(2))
            else:
                if (match.group(3) == 'dep_gold'):
                    users[match.group(2)].deposits = users[match.group(2)].deposits + int(match.group(4))
                elif (match.group(3) == 'dep_item' and match.group(8) != "nil"):
                    users[match.group(2)].donations = users[match.group(2)].donations + (int(match.group(5)) * float(match.group(8)))
            
        gbl_line_pos = gbl_line_pos + 1

    with open(d_file, 'w') as writer:
        for key in users.keys():
            writer.write(users[key].username + ',' + str(users[key].rank) + ',' + str(users[key].sales) + ',' + str(users[key].taxes) + ',' + str(users[key].donations) + ',' + str(users[key].deposits) +'\n')



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
        'source_gbl_file',
        help='The location of the source '
    )

    parser.add_argument(
    'source_mm_file',
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

    gbl_file = args.source_gbl_file
    mm_file = args.source_mm_file
    d_file = args.dest_file

    # If the destination file wasn't passed, then assume we want to
    # create a new file based on the old one
    if d_file is None:
        d_file = f'mm_gbl_merge.csv'

    parse_data(gbl_file, mm_file, d_file)
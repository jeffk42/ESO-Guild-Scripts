import argparse
import re
from datetime import datetime, timezone

# Guild name should be exactly as displayed in the MM or GBL output file
# in the line above the "real data" that looks like: ["Guild Name"] =
# This stops the script from accidentally importing data from other guilds.
GUILD_NAME = "AK Tamriel Trade"

# The raffle ticket price in gold. If a deposit is NOT divisible by this value
# with an integer result (minus the raffle modifier), the deposit will be 
# considered a non-eligible deposit.
# For example, with a ticket price of 500, a deposit of 5000 is considered an
# eligible raffle purchase, while a deposit of 5100 will not be included in
# the list of raffle purchases.
RAFFLE_TICKET_PRICE = 500

# The RAFFLE_MODIFIER must exist at the end of every deposit for it to count
# as a raffle ticket purchase. This is in addition to the ticket price
# division requirement.
# Examples assuming RAFFLE_TICKET_PRICE = 500, RAFFLE_MODIFIER = 1 :
#    Deposit: 5000 (no tickets, deposit doesn't end in "1")
#    Deposit: 5001 (10 tickets, 5000/500 = 10)
#    Deposit: 5101 (no tickets, 5100/500 is not a whole number)
#
# Set this value to 0 to allow ALL bank deposits to be eligible for raffle tickets
# as long as they are divisible by RAFFLE_TICKET_PRICE.
RAFFLE_MODIFIER = 1

# Guild leader rank is 1. Setting rank will also affect higher ranks, so setting
# this value to "3" will include not only the third rank, but also the second and first.
# Ranks corresponding to these filters are considered ineligible for the raffle,
# so all deposits to the bank will just be considered normal deposits.
RANK_RAFFLE_FILTER = 1

# DONATION_SUMMARY defines the items that you want to see in the overall summary.
# This lists every user in the guild at the time of your MM export. You can
# reorder, add, or remove items in this list to fit your preferred data format.
# Note that these are case sensitive!
# Possible options:
#   username:   The account name
#   rank:       The rank of the user in the guild (1 = guild leader)
#   sales:      The total sales corresponding to the selected range in MM (ie, 
#               "This Week", "Last Week", whatever was selected in the pull-down
#               at the time of the MM export operation)
#   taxes:      The amount of taxes collected for the guild based on sales.
#   deposits:   sum of all guild bank gold deposits in the GBLData file, going
#               back as far as the setting in the GBL add-on is set.
#   donations:  sum of the value of all guild bank ITEM deposits going back as
#               far as set in the GBL add-on. Item values are based on MM.
#
# Note: An empty string can be added to provide a blank column if needed, just add ""
# to the list.
DONATION_SUMMARY_FORMAT = [
    "username",
    "rank",
    "sales",
    "taxes",
    "deposits",
    "donations"
]

# Defines the format of the raffle entry file. Items can be rearranged or removed here
# just like in DONATION_SUMMARY_FORMAT.
RAFFLE_ENTRY_FORMAT = [
    "username",
    "date",
    "transactionId",
    "amount",
]

class UserData:
  def __init__(self, username):
    self.username = username
    self.sales = 0
    self.purchases = 0
    self.taxes = 0
    self.rank = 0
    self.deposits = 0
    self.donations = 0

class RaffleEntry:
  def __init__(self, username):
    self.username = username
    self.date = 0
    self.amount = 0
    self.transactionId = 0

# GBL regex capture groups
GBL = {
    "timestamp" : 1,
    "username" : 2,
    "transactionType" : 3,
    "goldAmount" : 4,
    "itemCount" : 5,
    "itemDescription" : 6,
    "itemLink" : 7,
    "itemValue" : 8,
    "transactionId" : 9
}

users = {}
raffle_tix = []

def parse_data(gbl_file: str, mm_file: str):

    ###############################################
    ##         Parse MasterMerchant.lua          ##
    ###############################################

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

    ###############################################
    ##            Parse GBLData.lua              ##
    ###############################################

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
        elif (match := re.match(r'^\s*\[[0-9]+\]\s=\s\"([0-9]+)\\t(@.+)\\t([a-z_]+)' + \
            r'\\t([0-9nil]*)\\t([0-9nil]*)\\t(.*)\\t(.*)\\t([0-9\.nil]*)\\t([0-9]+).*$', \
            gbl_lines[gbl_line_pos])) is not None:
            add_transaction_to_user(match)
            add_transaction_to_raffle(match)
            
        gbl_line_pos = gbl_line_pos + 1

    with open('donation_summary.csv', 'w') as writer:
        pos = 1
        for header in DONATION_SUMMARY_FORMAT:
            writer.write(header)
            if pos < len(DONATION_SUMMARY_FORMAT):
                writer.write(",")
                pos = pos + 1
            else:
                writer.write("\n")
      
        for key in users.keys():
            pos = 1
            for column in DONATION_SUMMARY_FORMAT:
                if (res:= str(getattr(users[key], column, "nil"))) != "nil":
                    writer.write(res)
                if pos < len(DONATION_SUMMARY_FORMAT):
                    writer.write(",")
                    pos = pos + 1
                else:
                    writer.write("\n")

    with open('raffle.csv', 'w') as writer:
        for raffle_entry in raffle_tix:
            pos = 1
            for column in RAFFLE_ENTRY_FORMAT:
                if (res:= str(getattr(raffle_entry, column, "nil"))) != "nil":
                    writer.write(res)
                if pos < len(RAFFLE_ENTRY_FORMAT):
                    writer.write(",")
                    pos = pos + 1
                else:
                    writer.write("\n")

def add_transaction_to_user(match):
    if match.group(GBL["username"]) not in users.keys():
        print('User not found: ' + match.group(GBL["username"]))
    else:
        if (match.group(GBL["transactionType"]) == 'dep_gold'):
            users[match.group(GBL["username"])].deposits = users[match.group(GBL["username"])].deposits + \
                int(match.group(GBL["goldAmount"]))
        elif (match.group(GBL["transactionType"]) == 'dep_item' and match.group(GBL["itemValue"]) != "nil"):
            users[match.group(GBL["username"])].donations = users[match.group(GBL["username"])].donations + \
                (int(match.group(GBL["itemCount"])) * int(float(match.group(GBL["itemValue"]))))

def add_transaction_to_raffle(match):
    if match.group(GBL["transactionType"]) == "dep_gold":
        if match.group(GBL["goldAmount"]) != "nil":
            amount = int(match.group(GBL["goldAmount"])) - RAFFLE_MODIFIER
            if amount % RAFFLE_TICKET_PRICE == 0:
                entry = RaffleEntry(match.group(GBL["username"]))
                entry.amount = amount
                entry.transactionId = match.group(GBL["transactionId"])
                entry.date = datetime.fromtimestamp(int(match.group(GBL["timestamp"])), \
                    timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                raffle_tix.append(entry)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script that creates useful CSV's from guild data.",
    )

    parser.add_argument(
        '--gbl',
        help='The location of the Guild Bank Ledger source ',
        default='GBLData.lua'
    )

    parser.add_argument(
        '--mm',
        help='The location of the Master Merchant source ',
        default='MasterMerchant.lua'
    )

    # Parse the args (argparse automatically grabs the values from
    # sys.argv)
    args = parser.parse_args()

    gbl_file = args.gbl
    mm_file = args.mm

    parse_data(gbl_file, mm_file)
import argparse
import re
from datetime import date, datetime, timezone, timedelta

# Guild name should be exactly as displayed in the MM or GBL output file
# in the line above the "real data" that looks like: ["Guild Name"] =
# This stops the script from accidentally importing data from other guilds.
GUILD_NAME = "AK Tamriel Trade"

# If True, prints column headers at the beginning of the output files.
ENABLE_HEADERS = False

# If True, this will enforce the ticket divisibility rule (see RAFFLE_TICKET_PRICE)
# and the RAFFLE_MODIFIER rule. If false, any deposit made to the bank will be considered
# for inclusion in the raffle.csv file.
ENABLE_RAFFLE_REQUIREMENTS = True

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
    "raffle",
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

# Defines a UserData object, which includes all available fields for the donation summary.
class UserData:
  def __init__(self, username):
    self.username = username
    self.sales = 0
    self.purchases = 0
    self.taxes = 0
    self.rank = 0
    self.raffle = 0
    self.deposits = 0
    self.donations = 0

# Defines a RaffleEntry object, which includes all available fields for the raffle.
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

# define date ranges for GBL data
startRange = datetime.fromtimestamp(0, timezone.utc)
endRange = datetime.now(timezone.utc)
startRaffle = datetime.fromtimestamp(0, timezone.utc)
endRaffle = datetime.now(timezone.utc)

def parse_data(week, gbl_file: str, mm_file: str, raffle_only: bool):
    if raffle_only:
        print('Generating a raffle-only report.\n')
    else:
        print('Attempting to generate report for week: ' + week + '\n')

    if not raffle_only:
        ###############################################
        ##         Parse MasterMerchant.lua          ##
        ###############################################

        mm_lines = []
        mm_line_pos = 1
        with open(mm_file, 'r') as reader:
            mm_lines = reader.readlines()

        # Find the right guild
        in_guild = False
        while not in_guild and mm_line_pos <= len(mm_lines):
            if re.match(rf'^\s*\[\"{GUILD_NAME}\"]\s=\s*$', mm_lines[mm_line_pos]) != None:
                in_guild = True
            mm_line_pos = mm_line_pos + 1
        
        # Account for open bracket
        if in_guild:
            mm_line_pos = mm_line_pos + 1
        
        while in_guild and mm_line_pos <= len(mm_lines):
            # Exit when current guild info has been exhausted
            if re.match(r'^\s*\}\s*,$', mm_lines[mm_line_pos]):
                in_guild = False
            # Read data into a UserData object
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

    # Find the right guild
    in_guild = False
    while not in_guild and gbl_line_pos <= len(gbl_lines):
        if re.match(rf'^\s*\[\"{GUILD_NAME}\"]\s=\s*$', gbl_lines[gbl_line_pos]) != None:
            in_guild = True
        gbl_line_pos = gbl_line_pos + 1
    
    # Account for open bracket
    if in_guild:
        gbl_line_pos = gbl_line_pos + 1
    
    while in_guild and gbl_line_pos <= len(gbl_lines):
        # Exit when current guild info has been exhausted
        if re.match(r'^\s*\}\s*,$', gbl_lines[gbl_line_pos]):
            in_guild = False
        # Capture all relevant data
        elif (match := re.match(r'^\s*\[[0-9]+\]\s=\s\"([0-9]+)\\t(@.+)\\t([a-z_]+)' + \
            r'\\t([0-9nil]*)\\t([0-9nil]*)\\t(.*)\\t(.*)\\t([0-9\.nil]*)\\t([0-9]+).*$', \
            gbl_lines[gbl_line_pos])) is not None:
            transaction_time = datetime.fromtimestamp(int(match.group(GBL["timestamp"])), timezone.utc)
            if not raffle_only:
                add_transaction_to_user(match, transaction_time)
            add_transaction_to_raffle(match, transaction_time)
            
        gbl_line_pos = gbl_line_pos + 1

    # Output summary of financial data in a comma separated file matching DONATION_SUMMARY_FORMAT.
    if not raffle_only:
        with open('donation_summary.csv', 'w') as writer:
            print_headers(writer, DONATION_SUMMARY_FORMAT)
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

    # Output raffle data in a comma separated file matching RAFFLE_ENTRY_FORMAT.
    with open('raffle.csv', 'w') as writer:
        print_headers(writer, RAFFLE_ENTRY_FORMAT)
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

# Print the column headers at the top of the output files, if ENABLE_HEADERS is set.
def print_headers(writer, header_obj):
    pos = 1
    if ENABLE_HEADERS:
        for header in header_obj:
            writer.write(header)
            if pos < len(header_obj):
                writer.write(",")
                pos = pos + 1
            else:
                writer.write("\n")

# This method builds the user dictionary with the username as the key and the associated UserData
# object as the value. It then updates the totals.
def add_transaction_to_user(match, transaction_time):
    
    if match.group(GBL["username"]) not in users.keys():
        print('User not found: ' + match.group(GBL["username"]))
    elif startRange <= transaction_time and endRange >= transaction_time:
        if (match.group(GBL["transactionType"]) == 'dep_gold') and match.group(GBL["goldAmount"]) != "nil":
            raffle_entry = get_raffle_purchase(match)
            if raffle_entry != None:
                users[match.group(GBL["username"])].raffle = users[match.group(GBL["username"])].raffle + raffle_entry.amount
            else:
                users[match.group(GBL["username"])].deposits = users[match.group(GBL["username"])].deposits + \
                    int(match.group(GBL["goldAmount"]))
        elif (match.group(GBL["transactionType"]) == 'dep_item' and match.group(GBL["itemValue"]) != "nil"):
            users[match.group(GBL["username"])].donations = users[match.group(GBL["username"])].donations + \
                (int(match.group(GBL["itemCount"])) * int(float(match.group(GBL["itemValue"]))))

# This method adds the gold deposit transaction to the raffle list, if the transaction meets the raffle requirements
def add_transaction_to_raffle(match, transaction_time):
    if startRaffle <= transaction_time and endRaffle >= transaction_time:
        if match.group(GBL["transactionType"]) == "dep_gold" and match.group(GBL["goldAmount"]) != "nil":
            entry = get_raffle_purchase(match)
            if entry != None:
                raffle_tix.append(entry)

# This method returns a RaffleEntry object if the transaction meets the raffle requirements.
# Otherwise it returns None.
def get_raffle_purchase(match):
    if  match.group(GBL["transactionType"]) == "dep_gold" and match.group(GBL["goldAmount"]) != "nil":
        amount = int(match.group(GBL["goldAmount"])) - (RAFFLE_MODIFIER if ENABLE_RAFFLE_REQUIREMENTS else 0)
        if not ENABLE_RAFFLE_REQUIREMENTS or (amount % RAFFLE_TICKET_PRICE == 0):
                entry = RaffleEntry(match.group(GBL["username"]))
                entry.amount = amount
                entry.transactionId = match.group(GBL["transactionId"])
                entry.date = datetime.fromtimestamp(int(match.group(GBL["timestamp"])), \
                    timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                return entry
        else: return None

def generate_date_ranges():
    global startRange, endRange, startRaffle, endRaffle
    # Set boundaries for transaction time, so we're not picking up
    # transactions for the wrong week.
    today = datetime.utcnow()
    
    if week == "this" or week == "last":
        offset = (today.weekday() - 1) % 7
        last_tuesday = today - timedelta(days=offset)
        # Today is considered "last Tuesday" if it's Tuesday, and that makes today the
        # start boundary for reading transactions. That's okay for any time
        # after rollover, but before rollover we should still be in the previous week.
        # Easy, ugly fix: If it's before rollover, pretend it's still yesterday for
        # the purposes of start range calculation.
        if (today.day == last_tuesday.day) and (today.hour < 19):
            today = today - timedelta(days=1)
            offset = (today.weekday() - 1) % 7
            last_tuesday = today - timedelta(days=offset)
        if week == "this":
            startRange = datetime(last_tuesday.year, last_tuesday.month, last_tuesday.day, 19,00,00,00,timezone.utc)
        elif week == "last":
            endRange = datetime(last_tuesday.year, last_tuesday.month, last_tuesday.day, 19,00,00,00,timezone.utc)
            startRange = endRange - timedelta(days=7)

    print('Setting summary start date of: ' + str(startRange))
    print('Setting summary end date of: ' + str(endRange))

    # Raffles go from Saturday 00:00 UTC to Saturday 00:00 UTC
    if week == "this" or week == "last":
        offset = (today.weekday() - 5) % 7
        last_sat = today - timedelta(days=offset)
        # if week == "this":
        startRaffle = datetime(last_sat.year, last_sat.month, last_sat.day, 00,00,00,00,timezone.utc)
        # elif week == "last":
            # endRaffle = datetime(last_sat.year, last_sat.month, last_sat.day, 00,00,00,00,timezone.utc)
            # startRaffle = endRaffle - timedelta(days=7)

    print('Setting raffle start date of: ' + str(startRaffle))
    print('Setting raffle end date of: ' + str(endRaffle))

# MAIN #
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

    parser.add_argument('--raffle-only', action='store_true')

    # Use to direct the script to copy the most recent data files to this directory
    parser.add_argument('--copy', action='store_true')

    parser.add_argument('--week', default='none')

    # Parse the args (argparse automatically grabs the values from
    # sys.argv)
    args = parser.parse_args()

    gbl_file = args.gbl
    mm_file = args.mm
    raffle_only = args.raffle_only
    week = args.week

    generate_date_ranges()
    parse_data(week, gbl_file, mm_file, raffle_only)
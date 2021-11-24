# The Guild_Stats script imports data from data files and generates csv's with information compiled
# for specific uses.
# Author: ESO @jeffk42

import argparse
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from shutil import copy2
import os

# Guild name should be exactly as displayed in the MM or GBL output file
# in the line above the "real data" that looks like: ["Guild Name"] =
# This stops the script from accidentally importing data from other guilds.
GUILD_NAME = "AK Tamriel Trade"

# The location of your ESO user directory. Note this is the data, not the full install.
# Default is the current user's Documents directory.
# If you need to change you can do something like this:
# SOURCE_DIR = "C:\\full\\path\\to\\ESO-directory"
SOURCE_DIR = os.path.expanduser("~") + "\\Documents\\Elder Scrolls Online"

# If True, prints column headers at the beginning of the output files.
ENABLE_HEADERS = False

# If True, prints the date/time (GMT) that the script was run as the first line.
PREFIX_DATE = True

# If False, no raffle data is generated and all raffle-related options below are ignored.
ENABLE_RAFFLE = True

# If true, this creates two raffle files: the normal raffle.csv and also a raffle-last.csv.
# The latter contains all of the entries for the previous raffle week. This is a convenience -
# Normally after the raffle deadline passes, you need to run the script with the --raffle-final
# flag to get the final data for the week that just ended. Then you need to re-run the script
# without the flag to start the new data. By setting OUTPUT_LAST_RAFFLE to True, you won't need
# to do this, because as soon as the deadline passes, the final data will be copied to raffle-last.csv
# and the new week will be started in raffle.csv.
OUTPUT_LAST_RAFFLE = True

RAFFLE = {
    # If True, this will enforce the ticket divisibility rule (see RAFFLE_TICKET_PRICE)
    # and the RAFFLE_MODIFIER rule. If false, any deposit made to the bank will be considered
    # for inclusion in the raffle.csv file.
    "enable_requirements": True,

    # The raffle ticket price in gold. If a deposit is NOT divisible by this value
    # with an integer result (minus the raffle modifier), the deposit will be
    # considered a non-eligible deposit.
    # For example, with a ticket price of 500, a deposit of 5000 is considered an
    # eligible raffle purchase, while a deposit of 5100 will not be included in
    # the list of raffle purchases.
    "ticket_price": 1000,

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
    "deposit_modifier": 1,

    # Guild leader rank is 1. Setting rank will also affect higher ranks, so setting
    # this value to "3" will include not only the third rank, but also the second and first.
    # Ranks corresponding to these filters are considered ineligible for the raffle,
    # so all deposits to the bank will just be considered normal deposits.
    "rank_filter": 1,

    # Defines the format of the raffle entry file. Items can be rearranged or removed here
    # just like in DONATION_SUMMARY_FORMAT.
    "raffle_format": [
        "username",
        "date",
        "transactionId",
        "amount",
    ],

    # RAFFLE TIME ZONE: The raffle ticket purchase deadline can either shift with
    # Daylight Savings Time, or it can remain the same regardless of DST.
    # If the raffle deadline should be at a set time regardless of DST
    # (for example, 8pm EST and 8pm EDT), the desired time zone should be entered below.
    #
    # If the deadline should change based on DST (for example, if the time should
    # be based on GMT and would be 8pm EDT but then become 7pm EST after the change back)
    # then enter 'UTC' as the time zone.
    #
    # For a list of available timezones, refer to the "TZ database name" column of the table
    # here: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
    #
    "timezone": 'US/Eastern',

    # RAFFLE DAY: This is an integer corresponding to the day of week that the raffle deadline falls on,
    # in the time zone selected above (so if you change the timezone, make sure the day
    # is still appropriate!). Monday = 0, Tuesday = 1, Sunday = 6, etc.
    "day": 4,

    # RAFFLE TIME: This is the time of the raffle deadline, based on the timezone set. Use the
    # format "HH:MM:SS" where the hours are using the 24-hour clock.
    "time": "20:00:00"
}

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
#   deposits:   sum of all guild bank gold deposits in the GBLData file, for the user
#               in the selected time frame (excluding raffle deposits).
#   raffle:     sum of all raffle gold deposits in the GBLData file, for the user
#               in the selected time frame.
#   donations:  sum of the value of all guild bank ITEM deposits for the user
#               in the selected time frame.
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
    "donations",
    "purchases"
]

# Removes the listed users from the output files. Useful for guild accounts, etc.
EXCLUDE_USERS = [
    "@aktt.guild"
]


##############################################################################################
# Values above can be easily modified to meet specific needs, but below this point it's
# probably best to avoid unless you know what you're doing. :)
##############################################################################################

SOURCE_FILES = {
    "gbl": "GBLData.lua",
    "mm": "MasterMerchant.lua"
}

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
    "timestamp": 1,
    "username": 2,
    "transactionType": 3,
    "goldAmount": 4,
    "itemCount": 5,
    "itemDescription": 6,
    "itemLink": 7,
    "itemValue": 8,
    "transactionId": 9
}

users = {}
raffle_tix = []

# define date ranges for GBL data
startRange = datetime.fromtimestamp(0, timezone.utc)
endRange = datetime.now(tz=ZoneInfo('UTC'))
startRaffle = datetime.fromtimestamp(0, timezone.utc)
endRaffle = datetime.now(tz=ZoneInfo('UTC'))

def convert_datetime_timezone(dt, tz2):
    dt = dt.astimezone(ZoneInfo(tz2))
    return dt

def parse_data(week, gbl_file: str, mm_file: str, raffle_only:bool, raffle_final: bool):
    global raffle_tix

    raffle_tix = []
    if not raffle_only:
        print('Attempting to generate report for week: ' + week + '\n')
    else:
        print("This is a raffle-only round")

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
        elif (match := re.match(r'^\s*\[[0-9]+\]\s=\s\"([0-9]+)\\t(@.+)\\t([a-z_]+)' +
                                r'\\t([0-9nil]*)\\t([0-9nil]*)\\t(.*)\\t(.*)\\t([0-9\.nil]*)\\t([0-9]+).*$',
                                gbl_lines[gbl_line_pos])) is not None:
            transaction_time = datetime.fromtimestamp(
                int(match.group(GBL["timestamp"])), timezone.utc)
            if match.group(GBL["timestamp"]) not in EXCLUDE_USERS:
                if not raffle_only:
                    add_transaction_to_user(match, transaction_time)
                add_transaction_to_raffle(match, transaction_time)

        gbl_line_pos = gbl_line_pos + 1

    # Output summary of financial data in a comma separated file matching DONATION_SUMMARY_FORMAT.
    if not raffle_only:
        with open('donation_summary.csv', 'w') as writer:
            if PREFIX_DATE:
                writer.write(datetime.now(timezone.utc).strftime(
                    '%m/%d/%y %H:%M:%S') + '\n')
            print_headers(writer, DONATION_SUMMARY_FORMAT)
            for key in users.keys():
                pos = 1
                if key not in EXCLUDE_USERS:
                    for column in DONATION_SUMMARY_FORMAT:
                        if (res := str(getattr(users[key], column, "nil"))) != "nil":
                            writer.write(res)
                        if pos < len(DONATION_SUMMARY_FORMAT):
                            writer.write(",")
                            pos = pos + 1
                        else:
                            writer.write("\n")

    if ENABLE_RAFFLE:
        # Output raffle data in a comma separated file matching RAFFLE_ENTRY_FORMAT.
        raffle_filename = 'raffle-last.csv' if raffle_final else 'raffle.csv'
        with open(raffle_filename, 'w') as writer:
            print_headers(writer, RAFFLE["raffle_format"])
            for raffle_entry in raffle_tix:
                pos = 1

                for column in RAFFLE["raffle_format"]:
                    if (res := str(getattr(raffle_entry, column, "nil"))) != "nil":
                        writer.write(res)
                    if pos < len(RAFFLE["raffle_format"]):
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
                users[match.group(GBL["username"])].raffle = users[match.group(
                    GBL["username"])].raffle + raffle_entry.amount
            else:
                users[match.group(GBL["username"])].deposits = users[match.group(GBL["username"])].deposits + \
                    int(match.group(GBL["goldAmount"]))
        elif (match.group(GBL["transactionType"]) == 'dep_item' and match.group(GBL["itemValue"]) != "nil"):
            users[match.group(GBL["username"])].donations = users[match.group(GBL["username"])].donations + \
                (int(match.group(GBL["itemCount"])) *
                 int(float(match.group(GBL["itemValue"]))))

# This method adds the gold deposit transaction to the raffle list, if the transaction meets the raffle requirements


def add_transaction_to_raffle(match, transaction_time):
    if not ENABLE_RAFFLE:
        return
    if startRaffle <= transaction_time and endRaffle >= transaction_time:
        if match.group(GBL["transactionType"]) == "dep_gold" and match.group(GBL["goldAmount"]) != "nil":
            entry = get_raffle_purchase(match)
            if entry != None:
                raffle_tix.append(entry)

# This method returns a RaffleEntry object if the transaction meets the raffle requirements.
# Otherwise it returns None.


def get_raffle_purchase(match):
    if not ENABLE_RAFFLE:
        return None
    if match.group(GBL["transactionType"]) == "dep_gold" and match.group(GBL["goldAmount"]) != "nil":
        amount = int(match.group(GBL["goldAmount"])) - \
            (RAFFLE["deposit_modifier"] if RAFFLE["enable_requirements"] else 0)
        if not RAFFLE["enable_requirements"] or (amount % RAFFLE["ticket_price"] == 0):
            entry = RaffleEntry(match.group(GBL["username"]))
            entry.amount = amount
            entry.transactionId = match.group(GBL["transactionId"])
            entry.date = datetime.fromtimestamp(int(match.group(GBL["timestamp"])),
                                                timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            return entry
        else:
            return None

# Generate the appropriate date boundaries for the request. For the donation summary, depending on "week",
# this is either from the most recent trader rollover until now, or from the previous rollover to the most recent.
# Raffles have a different schedule so for now we'll just get from last raffle to now.


def generate_date_ranges(week, raffle_final=False):
    global startRange, endRange, startRaffle, endRaffle
    # Set boundaries for transaction time, so we're not picking up
    # transactions for the wrong week.
    today = datetime.now(tz=ZoneInfo('UTC'))

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
            startRange = datetime(last_tuesday.year, last_tuesday.month,
                                  last_tuesday.day, 19, 00, 00, 00, timezone.utc)
        elif week == "last":
            endRange = datetime(last_tuesday.year, last_tuesday.month,
                                last_tuesday.day, 19, 00, 00, 00, timezone.utc)
            startRange = endRange - timedelta(days=7)

    print('Setting summary start date of: ' + str(startRange))
    print('Setting summary end date of: ' + str(endRange))

    # Raffles go from Saturday 00:00 UTC to Saturday 00:00 UTC
    raffle_time_array = RAFFLE["time"].split(':')
    
    
    # negative number modulo positive number is positive
    localNow = convert_datetime_timezone(today, RAFFLE["timezone"])
    offset = (localNow.weekday() - RAFFLE["day"]) % 7
    last_week = localNow - timedelta(days=offset)

    raffleDeadline = datetime(last_week.year, last_week.month, last_week.day,
                               int(raffle_time_array[0]),
                               int(raffle_time_array[1]),
                               int(raffle_time_array[2]), 00, ZoneInfo(RAFFLE["timezone"]))

    # when it's not yet the raffle deadline, but it's the same day as the raffle deadline,
    # we need to manually back up the start point to a week earlier.
    if raffleDeadline > localNow and offset == 0:
        offset = 7
        last_week = localNow - timedelta(days=offset)

    if not raffle_final:
        startRaffle = datetime(last_week.year, last_week.month, last_week.day,
                               int(raffle_time_array[0]),
                               int(raffle_time_array[1]),
                               int(raffle_time_array[2]), 00, ZoneInfo(RAFFLE["timezone"]))
    else:
        endRaffle = datetime(last_week.year, last_week.month, last_week.day,
                               int(raffle_time_array[0]),
                               int(raffle_time_array[1]),
                               int(raffle_time_array[2]), 00, ZoneInfo(RAFFLE["timezone"]))
        startRaffle = endRaffle - timedelta(days=7)

    print('Setting raffle start date of: ' + str(startRaffle))
    print('Setting raffle end date of: ' + str(endRaffle))

# Copy the data files automatically when the script is run. If this option is not selected, the files
# will need to be manually copied to the script directory prior to running.


def copy_datafiles(noCopy=False):
    if noCopy:
        return
    dir = "\\live\\SavedVariables\\"
    print('Attempting to copy current data....')
    output = copy2(SOURCE_DIR + dir + SOURCE_FILES["gbl"], SOURCE_FILES["gbl"])
    print("File copied: " + output)
    output = copy2(SOURCE_DIR + dir + SOURCE_FILES["mm"], SOURCE_FILES["mm"])
    print("File copied: " + output)


# MAIN #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script that creates useful CSV's from guild data.",
    )

    # Used to specify a non-standard filename for the GBLData.lua file.
    parser.add_argument(
        '--gbl',
        help='The location of the Guild Bank Ledger source ',
        default=SOURCE_FILES["gbl"]
    )

    # Used to specify a non-standard filename for the MasterMerchant.lua file.
    parser.add_argument(
        '--mm',
        help='The location of the Master Merchant source ',
        default=SOURCE_FILES["mm"]
    )

    # Ignores the MM export and only updates the raffle entries in raffle.csv.
    parser.add_argument('--raffle-only', action='store_true')

    # To be used after the raffle ticket purchase deadline, this gets the final
    # results for the week leading up to the deadline but not after. Use this to get
    # the final ticket list to be used for the drawing.
    parser.add_argument('--raffle-final', action='store_true')

    # Use to direct the script to copy the most recent data files to this directory
    parser.add_argument('--no-copy', action='store_true')

    # 'this' or 'last'. These correspond to 'this week' and 'last week' in Master Merchant.
    # To get the final tally for the recently completed week after rollover, use 'last'.
    # To get the results from rollover to now, use 'this'.
    parser.add_argument('--week', default='this')

    # Parse the args (argparse automatically grabs the values from
    # sys.argv)
    args = parser.parse_args()

    gbl_file = args.gbl
    mm_file = args.mm
    raffle_only = args.raffle_only
    week = args.week
    raffle_final = args.raffle_final

    copy_datafiles(args.no_copy)
    if OUTPUT_LAST_RAFFLE:
        generate_date_ranges(week, False)
        parse_data(week, gbl_file, mm_file, raffle_only=raffle_only, raffle_final=False)
        generate_date_ranges(week, True)
        parse_data(week, gbl_file, mm_file, raffle_only=True, raffle_final=True)
    else:
        generate_date_ranges(week, raffle_final)
        parse_data(week, gbl_file, mm_file, raffle_only, raffle_final)
# streamlit_app.py
import streamlit as st
import os
import subprocess

# Initialize session state flag
if "ready_for_download" not in st.session_state:
        st.session_state.ready_for_download = False

st.title("ESO Guild Stats Uploader")

title = st.text_input("Export User (must match ESO account that ran the exports)", "@jeffk42")

genre = st.radio(
    "Which week? (MM must be set accordingly)",
    ["This", "Last"],
    captions=[
        "This week.",
        "Last Week.",
    ],
)

gbl_file = st.file_uploader("Upload GBLData.lua", type="lua")
mm_file = st.file_uploader("Upload MasterMerchant.lua", type="lua")

if gbl_file and mm_file:
    with open("GBLData.lua", "wb") as f:
        f.write(gbl_file.read())
    with open("MasterMerchant.lua", "wb") as f:
        f.write(mm_file.read())

    if st.button("Run Guild Stats"):
        subprocess.run(["python", "guild_stats_web.py", "--week=" + genre.lower(), "--user=@jeffk42", "--no-copy"])
        st.session_state.ready_for_download = True
        st.success("CSV files generated successfully!")
        
#        with open("donation_summary.csv", "rb") as f:
#            st.download_button("Download donation_summary.csv", f, file_name="donation_summary.csv")
#        with open("raffle.csv", "rb") as f:
#            st.download_button("Download raffle.csv", f, file_name="raffle.csv")

# Show download buttons if ready
if st.session_state.ready_for_download:
    if genre == "This":
        col1, col2 = st.columns(2)
        with col1:
            with open("donation_summary.csv", "rb") as f:
                st.download_button("Download donation_summary.csv", f, file_name="donation_summary.csv")
        with col2:
            with open("raffle.csv", "rb") as f:
                st.download_button("Download raffle.csv", f, file_name="raffle.csv")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            with open("donation_summary.csv", "rb") as f:
                st.download_button("Download donation_summary.csv", f, file_name="donation_summary.csv")
        with col2:
            with open("raffle.csv", "rb") as f:
                st.download_button("Download raffle.csv", f, file_name="raffle.csv")
        with col3:
            with open("raffle-last.csv", "rb") as f:
                st.download_button("Download raffle-last.csv", f, file_name="raffle-last.csv")



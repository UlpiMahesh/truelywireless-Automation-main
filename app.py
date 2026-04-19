import streamlit as st
from playwright_service import run_allocation, run_amounts
import pandas as pd

st.title("📊 Truely Wireless Automation")

df = pd.read_excel("data/marketlogins.xlsx")

markets = df["Market"].dropna().unique().tolist()

selected = st.multiselect("Select Markets", markets)

col1, col2 = st.columns(2)

if col1.button("Get Allocation"):
    with st.spinner("Running Allocation..."):
        file = run_allocation(selected)

    with open(file, "rb") as f:
        st.download_button("Download Allocation", f, file_name="allocation.xlsx")

if col2.button("Get Amounts"):
    with st.spinner("Running Amounts..."):
        file = run_amounts(selected)

    with open(file, "rb") as f:
        st.download_button("Download Amounts", f, file_name="amounts.xlsx")
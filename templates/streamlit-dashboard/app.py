import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("Dashboard")

tab1, tab2 = st.tabs(["Data Explorer", "About"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        n = st.slider("Number of points", 10, 1000, 100)
    with col2:
        st.metric("Sample Size", n)

    data = pd.DataFrame(
        {
            "x": np.random.randn(n),
            "y": np.random.randn(n),
            "category": np.random.choice(["A", "B", "C"], n),
        }
    )
    st.scatter_chart(data, x="x", y="y", color="category")
    st.dataframe(data.describe())

with tab2:
    st.markdown("""
    ## About

    This dashboard was created with CapsuleLab.

    Edit `app.py` to customize your dashboard.
    """)

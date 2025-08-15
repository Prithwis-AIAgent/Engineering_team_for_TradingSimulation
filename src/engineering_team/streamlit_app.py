import streamlit as st
import os
from src.engineering_team.crew import crew  # Import your CrewAI team
import subprocess

st.set_page_config(page_title="Trading Simulation Team", page_icon="🤖", layout="wide")

st.title("🤖 Engineering Team for Trading Simulation")
st.markdown("""
This is a **multi-agent AI system** built with CrewAI that simulates a software development team working on a trading simulation platform.
Click **Run Simulation** to see the results.
""")

# API Key setup (optional if already in .env)
api_key = st.text_input(
    "Enter your OPENAI_API_KEY (leave blank to use .env)", type="password"
)
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

# Run simulation button
if st.button("🚀 Run Simulation"):
    with st.spinner("Running the engineering team simulation..."):
        try:
            # Run the CrewAI process
            crew.run()  # Direct call if your crew.py supports it

            # Alternative: If you want to use CLI instead of Python import
            # subprocess.run(["crewai", "run"], check=True)

            # Load and display the report
            if os.path.exists("report.md"):
                with open("report.md", "r", encoding="utf-8") as f:
                    report = f.read()
                st.success("Simulation completed!")
                st.markdown(report)
            else:
                st.warning("Simulation finished but no report.md found.")
        except Exception as e:
            st.error(f"Error running simulation: {e}")

# Footer
st.markdown("---")
st.markdown(
    "Built with [CrewAI](https://crewai.com) and [Streamlit](https://streamlit.io) 🚀"
)

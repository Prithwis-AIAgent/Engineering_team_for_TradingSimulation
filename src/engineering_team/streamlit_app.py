import streamlit as st
import subprocess
import os
from datetime import datetime
from engineering_team.crew import EngineeringTeam

st.title("Trading Simulation Platform")

# Button to run the simulation
if st.button("Run Trading Simulation"):
    with st.spinner("Running simulation..."):
        # Run the main simulation script using subprocess
        result = subprocess.run(["crewai", "run"], capture_output=True, text=True)
        if result.returncode == 0:
            st.success("Simulation completed successfully!")
        else:
            st.error(f"Simulation failed with error:\n{result.stderr}")

# Display report if exists
report_path = "report.md"
if os.path.exists(report_path):
    st.subheader("Simulation Report")
    with open(report_path, "r") as file:
        report_content = file.read()
    st.markdown(report_content)
else:
    st.info("No simulation report found yet. Run the simulation to generate one.")

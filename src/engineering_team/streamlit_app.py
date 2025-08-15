import streamlit as st
from datetime import date
import os
import sys

# Add the project root to the Python path to allow for module imports
# This helps in locating the 'engineering_team' module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

try:
    # Correctly import EngineeringTeam from your project structure
    from engineering_team.crew import EngineeringTeam
except ImportError:
    st.error(
        "Failed to import EngineeringTeam. Make sure the file structure is correct and all dependencies are installed."
    )

    # Add a placeholder class to prevent the app from crashing completely if the import fails
    class EngineeringTeam:
        def __init__(self, inputs):
            pass

        def run(self):
            return "Error: Could not run the analysis due to an import failure. Please check the application logs."


from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def run_engineering_crew(companies, from_date, to_date):
    """
    Initializes and runs the EngineeringTeam with the given parameters.
    """
    # Ensure API keys are set from Streamlit secrets for deployment
    os.environ["OPENAI_API_KEY"] = st.secrets.get(
        "OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")
    )
    os.environ["SERPER_API_KEY"] = st.secrets.get(
        "SERPER_API_KEY", os.environ.get("SERPER_API_KEY")
    )
    os.environ["SEC_API_API_KEY"] = st.secrets.get(
        "SEC_API_API_KEY", os.environ.get("SEC_API_API_KEY")
    )

    # Check if all required API keys are available
    if not all(
        [
            os.environ.get("OPENAI_API_KEY"),
            os.environ.get("SERPER_API_KEY"),
            os.environ.get("SEC_API_API_KEY"),
        ]
    ):
        st.error(
            "API keys are not configured. Please set OPENAI_API_KEY, SERPER_API_KEY, and SEC_API_API_KEY in your environment or Streamlit secrets."
        )
        return None

    # Prepare the inputs for the crew
    inputs = {
        "companies": companies,
        "from_date": from_date.strftime("%Y-%m-%d"),
        "to_date": to_date.strftime("%Y-%m-%d"),
    }

    # Instantiate and run the crew
    engineering_crew = EngineeringTeam(inputs)
    result = engineering_crew.run()
    return result


# --- Streamlit App UI ---

st.set_page_config(page_title="AI Trading Simulation", layout="wide")

st.title("📈 AI-Powered Trading Simulation")
st.markdown("""
Welcome to the AI Trading Simulation app! This tool leverages a team of AI agents to perform in-depth analysis of public companies.
Provide the company ticker symbols and a date range to receive a comprehensive trading analysis report.
""")

# --- Sidebar for User Inputs ---
with st.sidebar:
    st.header("Simulation Parameters")

    # Input for company tickers
    companies_input = st.text_input(
        "Company Tickers (comma-separated)",
        "TSLA, AAPL",
        help="Enter the stock ticker symbols for the companies you want to analyze.",
    )

    # Date range selection
    today = date.today()
    one_year_ago = today.replace(year=today.year - 1)

    from_date_input = st.date_input(
        "Start Date",
        one_year_ago,
        min_value=date(2010, 1, 1),
        max_value=today,
        help="Select the start date for the analysis period.",
    )

    to_date_input = st.date_input(
        "End Date",
        today,
        min_value=from_date_input,
        max_value=today,
        help="Select the end date for the analysis period.",
    )

    # Run button
    run_button = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

# --- Main Content Area ---
st.header("Analysis Report")

if run_button:
    # Validate inputs before running
    if not companies_input:
        st.warning("Please enter at least one company ticker.")
    elif from_date_input > to_date_input:
        st.error("Error: The start date cannot be after the end date.")
    else:
        # Show a spinner while the analysis is in progress
        with st.spinner("🤖 The AI team is analyzing... This may take a few minutes."):
            try:
                # Execute the main logic with the correct function
                final_report = run_engineering_crew(
                    companies_input, from_date_input, to_date_input
                )

                if final_report:
                    st.success("Analysis Complete!")
                    # Display the final report
                    st.markdown(final_report)
                else:
                    # Handle cases where the crew execution might fail silently
                    st.error(
                        "The analysis could not be completed. Please check the logs or API key configuration."
                    )

            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.exception(e)  # Provides a full traceback for debugging
else:
    st.info(
        "Please configure the parameters in the sidebar and click 'Run Analysis' to start."
    )

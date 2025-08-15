# Engineering Team for Trading Simulation

A multi-agent AI system powered by **CrewAI** that simulates a software development team tasked with autonomously building a trading simulation platform. The team consists of four specialized agents—Engineering Lead, Frontend Engineer, Backend Engineer, and Test Engineer—working together to execute buy/sell strategies.

---

## 🚀 Features

- 🤖 **Multi-Agent Architecture**: Each agent has a unique role, responsibilities, and tools.
- 🛠 **Modular & Customizable**: Configure and extend agents and tasks via YAML.
- ⚡ **Dependency Management via UV**: Powered by [UV](https://docs.astral.sh) for seamless setup.
- 🖱 **Easy Execution**: Kick off the team with a single CLI command.
- 📄 **Report Generation**: Outputs a `report.md` summarizing performance or findings.

---

## 📋 Prerequisites

- Python **3.10-3.13**
- Python package installer **pip**
- CrewAI dependency manager **uv**

---

## ⚙️ Installation

Install **uv**:

```bash
pip install uv


🛠 Configuration

Customize the system using the following files under src/engineering_team/config/:

agents.yaml — define agent roles and capabilities.

tasks.yaml — outline tasks or workflows to execute.

You can also extend functionality by modifying:

crew.py — introduce new tools or agent logic.

main.py — define inputs for simulation runs.

Add your API key in a .env file:

OPENAI_API_KEY=your_api_key_here

▶️ Running the Simulation

Execute the trading simulation with:

crewai run


This launches the agent team and generates report.md in the project root reflecting the simulation outcome.

📂 Project Structure
Engineering_team_for_TradingSimulation/
├── src/
│   └── engineering_team/
│       ├── config/
│       │   ├── agents.yaml
│       │   └── tasks.yaml
│       ├── crew.py
│       └── main.py
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md

📚 Support & Resources

CrewAI Documentation: https://docs.crewai.com

CrewAI Website: https://crewai.com

Join CrewAI Discord: https://discord.com

For questions or issues, please open an issue in this repository.

📜 License

Distributed under the [Your License]—see LICENSE for details.
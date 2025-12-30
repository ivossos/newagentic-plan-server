# FastMCP Planning Agent

Agentic MCP server for Oracle EPM Planning, based on the FastMCP framework and intelligence patterns from the FCCS Agent.

## Features
- **Agentic Reasoning**: Complex Planning queries handled by LLM orchestrator.
- **Oracle EPM Integration**: Direct interaction with Planning REST APIs.
- **Reinforcement Learning**: Tool selection optimization via RLE (Reinforcement Learning Engine).
- **Interactive Dashboard**: Streamlit-based monitoring for RLE performance.
- **Persistent Context**: Memory management for long-running sessions.

---

## 🏁 Windows Installation Guide

Follow these steps to set up the FastMCP Planning Agent on your Windows machine.

### 1. Prerequisites
Ensure you have the following installed:
- **Python 3.10 or higher**: [Download from python.org](https://www.python.org/downloads/windows/)
  - *Important*: Check the box **"Add Python to PATH"** during installation.
- **Git**: [Download from git-scm.com](https://git-scm.com/download/win)

### 2. Clone the Repository
Open PowerShell or Command Prompt and run:
```powershell
git clone https://github.com/ivossos/FastMCP-plan-agent.git
cd FastMCP-plan-agent
```

### 3. Create a Virtual Environment (Recommended)
This keeps the project dependencies isolated from your system Python.
```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 4. Install Dependencies
Install the package in editable mode with all necessary libraries:
```powershell
pip install -e .
```

### 5. Configuration
You need to provide your Oracle EPM Planning and AI API credentials.
1. Create a file named `.env` in the root directory.
2. Add the following variables (replacing with your actual data):

```env
PLANNING_URL=https://your-epm-instance.oraclecloud.com
PLANNING_USERNAME=your-username
PLANNING_PASSWORD=your-password
PLANNING_API_VERSION=v3
PLANNING_MOCK_MODE=false

# Database path (relative to project root)
DATABASE_URL=sqlite:///./data/planning_agent.db

# AI Provider Keys
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
MODEL_ID=gemini-2.0-flash

# RLE Settings
RL_ENABLED=true
```

### 6. Running the Agent
To start the MCP server (stdio mode):
```powershell
python -m cli.fastmcp_stdio
```

### 7. Launching the RLE Dashboard
To see the Reinforcement Learning Engine metrics and tool performance:
```powershell
streamlit run dashboard.py
```

---

## 🛠️ Project Structure
- `planning_agent/`: Core agent logic, tools, and intelligence.
- `data/`: Contains exported metadata templates (`.csv`) and local DB.
- `cli/`: Command-line interface entries.
- `dashboard.py`: Streamlit application for monitoring.

## 🤝 Contributing
Feel free to open issues or submit pull requests for improvements.

## 📄 License
MIT License

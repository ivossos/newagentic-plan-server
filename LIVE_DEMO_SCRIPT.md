# Oracle EPM Planning Agent: 30-Minute Live Demo Script

## Pre-Demo Checklist

```bash
# 1. Start the Planning Agent MCP Server
cd C:\Users\ivoss\Downloads\Projetos\agentic\newagentic-plan-server
.\venv\Scripts\activate
python -m cli.fastmcp_stdio

# 2. Start Web API (in separate terminal)
python -m web.server

# 3. Start Dashboard (in separate terminal)
streamlit run dashboard.py

# 4. Open Claude Desktop with MCP configured
# 5. Open browser to http://localhost:8501 (dashboard)
# 6. Open browser to http://localhost:8080 (API)
```

---

## DEMO SECTION 1: Introduction & Basic Queries (5 minutes)

### 1.1 Opening - Show the Problem

**SAY:**
> "Let me first show you what EPM Planning users deal with today. To get a simple revenue number, you need to construct a JSON payload like this..."

**SHOW this complex API payload:**
```json
{
  "suppressMissingBlocks": true,
  "pov": {
    "members": [
      ["E501"],
      ["Actual"],
      ["FY25"],
      ["Working"],
      ["USD"],
      ["No Future1"],
      ["Total CostCenter"],
      ["Total Region"]
    ]
  },
  "columns": [
    {
      "dimensions": ["Period"],
      "members": [["Dec"]]
    }
  ],
  "rows": [
    {
      "dimensions": ["Account"],
      "members": [["400000"]]
    }
  ]
}
```

**SAY:**
> "You need to know all 10 dimensions, exact member names, the correct JSON structure... Now let me show you the alternative."

---

### 1.2 First Query - Simple Revenue

**OPEN Claude Desktop**

**TYPE THIS PROMPT:**
```
What is the total revenue for Chicago in December 2024?
```

**EXPECTED RESPONSE:**
- Agent identifies intent: `data_retrieval`
- Extracts entities: entity=E501, period=Dec, year=FY24
- Calls `smart_retrieve` tool
- Returns formatted revenue number

**SAY:**
> "Notice I just asked in plain English. The agent understood 'Chicago' means entity E501, 'December 2024' means period Dec in FY24, and 'total revenue' maps to account 400000."

---

### 1.3 Follow-up Query - Context Memory

**TYPE THIS PROMPT:**
```
Now show me the breakdown by revenue stream
```

**EXPECTED RESPONSE:**
- Agent remembers Chicago, December, 2024 from context
- Calls `smart_retrieve_revenue` for Rooms, F&B, Other
- Returns breakdown table

**SAY:**
> "I didn't repeat Chicago or December - the agent remembered our context. This is the context memory system at work."

---

### 1.4 Different Entity

**TYPE THIS PROMPT:**
```
What about Seoul? Same breakdown.
```

**EXPECTED RESPONSE:**
- Switches entity to E100 (Lotte Seoul)
- Keeps period context
- Returns Seoul revenue breakdown

**SAY:**
> "Seamless context switching. The agent understood 'Seoul' maps to E100 while keeping our time context."

---

## DEMO SECTION 2: Dimension Exploration (5 minutes)

### 2.1 List All Dimensions

**TYPE THIS PROMPT:**
```
What dimensions are available in this Planning application?
```

**EXPECTED RESPONSE:**
- Calls `get_dimensions`
- Returns list: Account, Entity, Scenario, Version, Years, Period, Currency, CostCenter, Region, Future1

**SAY:**
> "This is essential for new users or when working with unfamiliar applications."

---

### 2.2 Explore Entity Hierarchy

**TYPE THIS PROMPT:**
```
Show me the Entity hierarchy - what hotels do we have?
```

**EXPECTED RESPONSE:**
- Calls `get_members` for Entity dimension
- Shows hierarchy: Total Entity > Regional groupings > Individual hotels

**SAY:**
> "The agent explores the dimension hierarchy. We can see E501 is Chicago, E100 is Seoul, E500 is L7, etc."

---

### 2.3 Search for Members

**TYPE THIS PROMPT:**
```
Find all members related to "Food" in the Account dimension
```

**EXPECTED RESPONSE:**
- Calls `find_members` with search_term="Food"
- Returns: F&B Revenue (420000), Food Cost accounts, etc.

**SAY:**
> "Powerful search across thousands of members. Finance teams often know concepts but not exact codes."

---

### 2.4 Account Details

**TYPE THIS PROMPT:**
```
What accounts roll up under Total Operating Expenses?
```

**EXPECTED RESPONSE:**
- Calls `get_member` with expansion
- Shows children of 600000 or similar expense parent

**SAY:**
> "Hierarchical drill-down. Essential for understanding the chart of accounts structure."

---

## DEMO SECTION 3: Variance Analysis (5 minutes)

### 3.1 Actual vs Forecast

**TYPE THIS PROMPT:**
```
Compare Chicago's Actual vs Forecast revenue for Q4 2024
```

**EXPECTED RESPONSE:**
- Agent creates multi-step plan
- Fetches Actual Q4 data
- Fetches Forecast Q4 data (in parallel!)
- Calculates variance
- Returns comparison table with variance amounts and percentages

**SAY:**
> "Watch the execution - Actual and Forecast data are fetched in parallel. The orchestrator optimized this automatically."

---

### 3.2 Year-over-Year Analysis

**TYPE THIS PROMPT:**
```
How does this year's Chicago revenue compare to last year?
```

**EXPECTED RESPONSE:**
- Calls `smart_retrieve_variance` with YoY parameters
- Returns FY24 vs FY23 comparison
- Shows growth/decline percentages

**SAY:**
> "Year-over-year analysis is a single prompt. The agent handles the complexity of cross-year comparisons."

---

### 3.3 Detailed Variance with Insights

**TYPE THIS PROMPT:**
```
Explain why Chicago's Q4 revenue is different from forecast. Break it down by segment.
```

**EXPECTED RESPONSE:**
- Multi-step execution
- LLM synthesis provides narrative explanation
- Identifies which segments over/under performed

**SAY:**
> "This is where the LLM reasoning shines. It doesn't just give numbers - it synthesizes insights from the data."

---

### 3.4 Multi-Entity Comparison

**TYPE THIS PROMPT:**
```
Compare Q4 Actual revenue across all our Asian hotels
```

**EXPECTED RESPONSE:**
- Identifies Asian entities (E100 Seoul, E500 L7, E800 Signiel)
- Fetches data for each
- Returns comparison table

**SAY:**
> "Cross-entity analysis with a single natural language query."

---

## DEMO SECTION 4: Job Management & Business Rules (4 minutes)

### 4.1 Check Job Status

**TYPE THIS PROMPT:**
```
Are there any jobs running right now?
```

**EXPECTED RESPONSE:**
- Calls `list_jobs`
- Shows recent jobs with status (Running, Completed, Failed)

**SAY:**
> "Instant visibility into background processes. No need to navigate to the Jobs console."

---

### 4.2 Specific Job Details

**TYPE THIS PROMPT:**
```
What's the status of the last calculation job?
```

**EXPECTED RESPONSE:**
- Filters for calculation jobs
- Shows detailed status including start time, duration, any errors

**SAY:**
> "Drill down into specific job types."

---

### 4.3 Execute a Business Rule (DEMO ONLY - be careful)

**TYPE THIS PROMPT:**
```
What business rules are available to run?
```

**EXPECTED RESPONSE:**
- Lists available rules/calc scripts
- Shows descriptions

**SAY:**
> "In a real scenario, you could say 'Run the monthly aggregation rule' and the agent would execute it. I won't run it now to avoid affecting live data."

---

## DEMO SECTION 5: Discovery Tools for Custom Apps (5 minutes)

### 5.1 Discover Unknown Application

**TYPE THIS PROMPT:**
```
Discover the complete structure of this Planning application
```

**EXPECTED RESPONSE:**
- Calls `discover_app_structure`
- Returns:
  - All dimensions with types
  - Dense vs Sparse classification
  - Plan types (FinPlan, FinRPT, etc.)
  - Sample members from each dimension

**SAY:**
> "This is crucial for consultants or new team members. No documentation needed - the agent discovers the structure automatically."

---

### 5.2 Profile Data Locations

**TYPE THIS PROMPT:**
```
Profile the data in FinPlan - where does data actually exist?
```

**EXPECTED RESPONSE:**
- Calls `profile_data`
- Samples intersections
- Reports which combinations have actual values

**SAY:**
> "In large Planning apps, data may only exist at certain intersections. This tool finds where the data actually lives."

---

### 5.3 Dynamic Grid Building

**TYPE THIS PROMPT:**
```
Build me a grid to retrieve Employee headcount by Cost Center for Q1
```

**EXPECTED RESPONSE:**
- Calls `build_dynamic_grid`
- Returns ready-to-use grid definition
- Handles POV defaults automatically

**SAY:**
> "For power users who need custom grids - the agent constructs them based on natural language descriptions."

---

### 5.4 Export Metadata

**TYPE THIS PROMPT:**
```
Export the full metadata for this application so I can analyze it offline
```

**EXPECTED RESPONSE:**
- Calls `export_app_metadata`
- Returns complete dimension and member data
- Can be saved to CSV/JSON for offline analysis

**SAY:**
> "Complete metadata export for documentation or offline analysis."

---

## DEMO SECTION 6: Reinforcement Learning in Action (4 minutes)

### 6.1 Show the Dashboard

**OPEN BROWSER to http://localhost:8501**

**SAY:**
> "This is the RL Engine dashboard. Let's look at what the system has learned."

**POINT OUT:**
- Total executions count
- Average success rate
- Tool performance table
- Successful sequences

---

### 6.2 Demonstrate Feedback

**GO BACK TO Claude Desktop**

**TYPE THIS PROMPT:**
```
Show me Chicago's monthly revenue trend for 2024
```

**WAIT FOR RESPONSE**

**TYPE THIS PROMPT:**
```
Rate that last response - it was very helpful, 5 stars
```

OR use the tool directly:
```
rate_last_tool("good")
```

**SAY:**
> "User feedback directly updates the RL policy. This 5-star rating increases the Q-value for the tool chain that was used."

---

### 6.3 View Updated Metrics

**REFRESH the Streamlit dashboard**

**SAY:**
> "Notice the execution count increased and if we had more data, you'd see the success rate and ratings update in real-time."

---

### 6.4 Show Tool Recommendations

**TYPE THIS PROMPT:**
```
What tools would you recommend for analyzing our forecast accuracy?
```

**EXPECTED RESPONSE:**
- Agent suggests: smart_retrieve_variance, smart_retrieve
- Shows confidence scores based on RL policy

**SAY:**
> "The agent now recommends tools based on learned policies, not just hardcoded rules."

---

## DEMO SECTION 7: Advanced Queries & Edge Cases (3 minutes)

### 7.1 Complex Multi-Step Query

**TYPE THIS PROMPT:**
```
Give me a complete financial summary for Chicago Q4 2024:
- Total Revenue by segment
- Total Expenses
- Net Income
- Comparison to both Forecast and Prior Year
```

**EXPECTED RESPONSE:**
- Creates complex execution plan
- Multiple parallel tool calls
- LLM synthesizes comprehensive summary

**SAY:**
> "A complex analyst request handled in seconds. Multiple data points, multiple comparisons, synthesized into a coherent report."

---

### 7.2 Handling Ambiguity

**TYPE THIS PROMPT:**
```
Show me the numbers for last month
```

**EXPECTED RESPONSE:**
- Agent may ask for clarification: "Which metric? Which entity?"
- Or makes reasonable defaults and states assumptions

**SAY:**
> "When queries are ambiguous, the agent either asks for clarification or makes reasonable assumptions and clearly states them."

---

### 7.3 Error Handling

**TYPE THIS PROMPT:**
```
Get revenue for entity XYZ123
```

**EXPECTED RESPONSE:**
- Graceful error: "Entity XYZ123 not found"
- Suggests similar valid entities

**SAY:**
> "Invalid inputs are handled gracefully with helpful error messages."

---

## DEMO SECTION 8: API & Integration Demo (3 minutes)

### 8.1 Show REST API

**OPEN BROWSER to http://localhost:8080**

**SAY:**
> "This is the REST API that powers integrations with ChatGPT and other systems."

**NAVIGATE to http://localhost:8080/tools**

**SAY:**
> "Complete tool catalog available via API."

---

### 8.2 Execute via API

**OPEN a terminal or Postman**

**RUN THIS CURL:**
```bash
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_application_info",
    "arguments": {},
    "session_id": "demo-session"
  }'
```

**SAY:**
> "Any tool can be called programmatically. This enables integration with custom applications, Power Automate, or any HTTP-capable system."

---

### 8.3 Show OpenAPI Spec

**NAVIGATE to http://localhost:8080/api-schema.json**

**SAY:**
> "Full OpenAPI specification for ChatGPT Custom GPT integration. This schema enables ChatGPT to understand and call our tools."

---

## CLOSING (1 minute)

### Summary

**SAY:**
> "In 30 minutes, we've seen:
>
> 1. **Natural language queries** replacing complex API calls
> 2. **Context memory** enabling conversational interactions
> 3. **Variance analysis** with automatic parallel execution
> 4. **Discovery tools** for unknown applications
> 5. **Reinforcement learning** that improves with every interaction
> 6. **REST API** for integration with any system
>
> This transforms Oracle EPM Planning from a technical tool into an intelligent assistant that understands what finance teams actually need."

---

## Quick Reference: All Demo Prompts

### Basic Queries
```
What is the total revenue for Chicago in December 2024?
Now show me the breakdown by revenue stream
What about Seoul? Same breakdown.
```

### Dimension Exploration
```
What dimensions are available in this Planning application?
Show me the Entity hierarchy - what hotels do we have?
Find all members related to "Food" in the Account dimension
What accounts roll up under Total Operating Expenses?
```

### Variance Analysis
```
Compare Chicago's Actual vs Forecast revenue for Q4 2024
How does this year's Chicago revenue compare to last year?
Explain why Chicago's Q4 revenue is different from forecast. Break it down by segment.
Compare Q4 Actual revenue across all our Asian hotels
```

### Job Management
```
Are there any jobs running right now?
What's the status of the last calculation job?
What business rules are available to run?
```

### Discovery Tools
```
Discover the complete structure of this Planning application
Profile the data in FinPlan - where does data actually exist?
Build me a grid to retrieve Employee headcount by Cost Center for Q1
Export the full metadata for this application so I can analyze it offline
```

### Reinforcement Learning
```
Rate that last response - it was very helpful, 5 stars
rate_last_tool("good")
What tools would you recommend for analyzing our forecast accuracy?
```

### Advanced
```
Give me a complete financial summary for Chicago Q4 2024:
- Total Revenue by segment
- Total Expenses
- Net Income
- Comparison to both Forecast and Prior Year

Show me the numbers for last month
Get revenue for entity XYZ123
```

---

## Troubleshooting During Demo

### If MCP Connection Fails
```bash
# Restart the stdio server
python -m cli.fastmcp_stdio
```

### If API Returns Errors
```bash
# Check logs
tail -f agent_stderr.log
```

### If Dashboard Doesn't Load
```bash
# Reinstall streamlit
pip install streamlit --upgrade
streamlit run dashboard.py
```

### If Claude Desktop Doesn't See Tools
1. Check `claude_desktop_config.json` path is correct
2. Restart Claude Desktop completely
3. Verify Python path in config

---

## Backup Demo: Mock Mode

If live EPM connection fails, switch to mock mode:

```env
# In .env file
PLANNING_MOCK_MODE=true
```

This returns simulated data that still demonstrates all features.

---

*End of Live Demo Script*

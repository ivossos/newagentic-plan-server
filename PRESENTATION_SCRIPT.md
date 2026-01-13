# Oracle EPM Planning Agent: 30-Minute Presentation Script

## Presentation Overview

| Section | Duration | Topics |
|---------|----------|--------|
| 1. Introduction & Problem | 3 min | Why we built this, the pain points |
| 2. Architecture Overview | 5 min | High-level system design |
| 3. Intelligence Layer | 7 min | Intent classification, LLM reasoning, orchestration |
| 4. Reinforcement Learning | 5 min | Q-learning, feedback loop, adaptive tool selection |
| 5. Live Demo | 7 min | End-to-end demonstration |
| 6. Deployment & Integration | 3 min | MCP, REST API, Claude Desktop |
| Q&A Buffer | ~5 min | Questions and discussion |

---

## SECTION 1: Introduction & Problem Statement (3 minutes)

### Opening Hook

> "Imagine asking your enterprise planning system: 'Show me our Chicago hotel's Q4 revenue versus forecast, broken down by revenue stream.' And getting an instant, accurate answer with actionable insights."

### The Current Pain Points

**Slide: "The EPM Challenge"**

Today's Oracle EPM Planning users face significant friction:

1. **Complex REST APIs** - The Planning REST API requires specific grid definitions with all 10 dimensions correctly specified
2. **Tribal Knowledge** - Users need to know exact member names, dimension structures, and API formats
3. **Manual Processes** - Extracting data requires building complex payloads, running jobs, waiting for results
4. **No Natural Language** - Finance teams can't just "ask" for data - they need technical intermediaries

**Slide: "Our Solution"**

We built an **Agentic AI Assistant** that:
- Understands natural language queries about financial data
- Automatically constructs the correct API calls
- Learns from user feedback to improve over time
- Works with any custom Planning application structure

> "Let me show you how we transformed EPM Planning from a technical tool into a conversational partner."

---

## SECTION 2: Architecture Overview (5 minutes)

### System Architecture

**Slide: "Three-Layer Architecture"**

```
                    +------------------+
                    |  User Interface  |
                    | (Claude Desktop, |
                    |  ChatGPT, Web)   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  MCP/REST Layer  |
                    | (fastmcp_stdio,  |
                    |    FastAPI)      |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |                    |                    |
+-------v-------+    +-------v-------+    +------v------+
|  Intelligence |    |     Agent     |    |   Services  |
|    Layer      |    |     Core      |    |   (RL, DB)  |
+---------------+    +---------------+    +-------------+
        |                    |                    |
        +--------------------+--------------------+
                             |
                    +--------v---------+
                    | Oracle EPM Cloud |
                    |  Planning REST   |
                    +------------------+
```

### Key Components

**The Agent Core** (`planning_agent/agent.py`)
- Central coordinator with 30+ tools
- Session state management
- Tool execution with RL hooks

> "Every tool call flows through the agent core, allowing us to track, learn, and optimize."

**The Intelligence Layer**
- Intent Classifier: Understands what users want
- LLM Reasoner: Handles complex queries
- Orchestrator: Coordinates multi-step operations
- Context Memory: Maintains session continuity

**The Services Layer**
- Feedback Service: Tracks tool performance
- RL Service: Q-learning for tool selection
- SQLite/PostgreSQL storage

---

## SECTION 3: Intelligence Layer Deep Dive (7 minutes)

### Intent Classification System

**Slide: "Understanding User Intent"**

Our intent classifier handles 10 different intent types:

| Intent Type | Example Query |
|-------------|---------------|
| Data Retrieval | "What was Chicago's Q4 revenue?" |
| Dimension Exploration | "Show me the account hierarchy" |
| Variance Analysis | "Compare Actual vs Forecast for 2024" |
| Job Management | "Check the status of my calculation job" |
| Business Rule | "Run the monthly consolidation rule" |
| Data Management | "Copy Forecast to Budget" |

**The Classification Pipeline:**

```python
# Step 1: Pattern Matching
patterns = [
    r"(?:get|retrieve|show).{0,30}(?:data|value|revenue)",
    r"(?:variance|compare).{0,20}(?:actual|forecast)",
]

# Step 2: Keyword Scoring
keywords = ["revenue", "expense", "profit", "forecast"]

# Step 3: Entity Extraction
entities = {
    "period": "Q4",
    "entity": "E501",  # Chicago
    "scenario": "Actual"
}

# Step 4: Confidence Calculation
confidence = (pattern_score * 0.50) + (keyword_score * 0.30) + (entity_score * 0.20)
```

> "This hybrid approach gives us 85%+ accuracy on common queries, with LLM fallback for edge cases."

### LLM Reasoning Engine

**Slide: "When Rules Aren't Enough"**

For complex or ambiguous queries, we escalate to Claude:

```python
class LLMReasoner:
    """LLM-powered reasoning using Claude API"""

    async def classify_intent_async(self, query, entities, context):
        # Uses Claude to understand complex queries
        # Returns structured intent with suggested tools

    async def synthesize_results(self, results, query, context):
        # Combines multiple tool results into coherent response
        # Generates insights and recommendations
```

**Real Example:**
- Query: "Why is our Chicago revenue down compared to last quarter?"
- This triggers:
  1. Intent classification (variance analysis)
  2. Data retrieval for both quarters
  3. LLM synthesis explaining the variance

### The Orchestrator

**Slide: "Multi-Step Operation Coordination"**

The orchestrator manages complex queries requiring multiple tools:

```python
class PlanningOrchestrator:
    async def process(self, user_query, session_id):
        # 1. Classify intent
        intent = await self._classify_intent(query)

        # 2. Enrich context from memory
        enriched = context_memory.get_suggested_params()

        # 3. Generate execution plan
        plan = planner.create_plan(intent, entities, tools)

        # 4. Execute plan (parallel when possible)
        results = await self._execute_plan(plan)

        # 5. Synthesize results
        synthesis = await llm_reasoner.synthesize_results(results)

        return OrchestratorResponse(...)
```

**Key Innovation: Parallel Execution**

```python
# Group steps by parallel_group
if len(group_steps) > 1:
    tasks = [self._execute_step(step) for step in group_steps]
    results = await asyncio.gather(*tasks)
```

> "For a variance analysis, we can fetch Actual and Forecast data simultaneously, cutting response time in half."

---

## SECTION 4: Reinforcement Learning Engine (5 minutes)

### Q-Learning for Tool Selection

**Slide: "The Agent That Learns"**

Traditional systems are static. Our agent improves with every interaction:

```python
class RLService:
    """Q-learning for tool selection optimization"""

    def update_policy(self, tool_name, context_hash, reward, ...):
        # Q-learning update rule:
        # Q(s,a) = Q(s,a) + α * (r + γ * max Q(s',a') - Q(s,a))

        td_target = reward + self.discount_factor * future_value
        new_value = old_value + self.learning_rate * (td_target - old_value)
```

### Reward Calculation

**Slide: "What Drives Learning"**

```python
class RewardCalculator:
    @staticmethod
    def calculate_reward(execution_doc):
        reward = 0.0

        # Success: +10 or -5
        if execution_doc.get("success"):
            reward += 10.0
        else:
            reward -= 5.0

        # User rating: -4 to +4
        if user_rating:
            reward += (user_rating - 3) * 2.0

        # Performance bonus
        if execution_time < avg_time * 0.8:
            reward += 2.0

        return reward  # Range: approximately -9 to +16
```

### The Feedback Loop

**Slide: "Human-in-the-Loop Learning"**

```
User Query
    |
    v
Tool Execution -----> Immediate Reward (success/failure)
    |
    v
Results Shown
    |
    v
User Rating (1-5) --> Delayed Reward (updates Q-value retroactively)
    |
    v
Policy Updated
```

**API for Feedback:**
```bash
POST /api/feedback
{
    "execution_id": 123,
    "rating": 5,
    "feedback": "Perfect result!"
}
```

### Tool Recommendations

**Slide: "Smart Tool Selection"**

The system recommends tools based on learned policies:

```python
def get_tool_recommendations(self, context_hash, available_tools):
    recommendations = []

    for tool_name in available_tools:
        confidence = 0.5  # Base confidence

        # Factor 1: Historical success rate
        if success_rate > 0.8:
            confidence += 0.2

        # Factor 2: User ratings
        if avg_rating >= 4.0:
            confidence += 0.15

        # Factor 3: Execution speed
        if avg_time < 1000:  # Under 1 second
            confidence += 0.1

        # Factor 4: RL policy value (Q-value)
        confidence += min(0.2, action_value / 10.0)

        recommendations.append({
            "tool_name": tool_name,
            "confidence": confidence,
            "reason": factors
        })

    return sorted(recommendations, key=lambda x: x["confidence"], reverse=True)
```

> "After just 100 queries, our agent typically shows 15-20% improvement in tool selection accuracy."

---

## SECTION 5: Live Demo (7 minutes)

### Demo Setup

**Prerequisites shown on screen:**
- Claude Desktop connected
- Planning Agent running
- Sample Planning application

### Demo Scenario 1: Simple Data Query (2 min)

**Script:**

> "Let's start with a simple query. I'll ask Claude: 'What's our Chicago hotel revenue for December 2024?'"

*Type in Claude Desktop:*
```
What's the Chicago hotel revenue for December 2024?
```

*Show the response and explain:*

> "Notice how the agent:
> 1. Classified this as a 'data_retrieval' intent
> 2. Extracted entities: entity=E501 (Chicago), period=Dec, year=FY24
> 3. Used the 'smart_retrieve' tool
> 4. Formatted the response with context"

### Demo Scenario 2: Variance Analysis (2 min)

**Script:**

> "Now let's ask for something more complex: 'Compare Chicago's Q4 Actual vs Forecast revenue by segment'"

*Type in Claude Desktop:*
```
Compare Chicago Q4 Actual vs Forecast revenue by segment
```

*Highlight the multi-step execution:*

> "The orchestrator created a plan with multiple steps:
> 1. Get Actual data for Rooms, F&B, Other
> 2. Get Forecast data (in parallel!)
> 3. Calculate variances
> 4. Synthesize insights with LLM"

### Demo Scenario 3: Discovery Mode (2 min)

**Script:**

> "What if someone connects to an unfamiliar Planning application? Let me show you the discovery tools."

*Type:*
```
Discover the structure of this Planning application
```

*Show output:*

> "The agent discovered:
> - 10 dimensions with their types
> - Sample members from each
> - Dense vs sparse classification
> - Available plan types"

### Demo Scenario 4: Dashboard Review (1 min)

**Open Streamlit dashboard:**
```bash
streamlit run dashboard.py
```

*Point out:*
- Total executions
- Success rates by tool
- User ratings
- Successful tool sequences (learned patterns)

> "This dashboard shows the RL engine in action. Notice how 'smart_retrieve' has the highest confidence score after learning from user feedback."

---

## SECTION 6: Deployment & Integration (3 minutes)

### Deployment Options

**Slide: "Three Ways to Deploy"**

**Option 1: Claude Desktop (MCP)**
```json
// claude_desktop_config.json
{
  "mcpServers": {
    "planning-agent": {
      "command": "python",
      "args": ["-m", "cli.fastmcp_stdio"],
      "cwd": "C:\\path\\to\\planning-agent"
    }
  }
}
```

**Option 2: REST API (Web/ChatGPT)**
```bash
python -m web.server
# Available at http://localhost:8080
```

Endpoints:
- `GET /tools` - List all available tools
- `POST /execute` - Execute any tool
- `POST /api/feedback` - Submit user ratings
- `GET /.well-known/mcp.json` - MCP discovery

**Option 3: Docker Deployment**
```bash
docker build -t planning-agent .
docker run -p 8080:8080 planning-agent
```

### Integration with ChatGPT

**Slide: "ChatGPT Custom GPT Integration"**

```
+------------+     +----------------+     +------------------+
|  ChatGPT   | --> | Planning Agent | --> | Oracle EPM Cloud |
| Custom GPT |     |   REST API     |     |    Planning      |
+------------+     +----------------+     +------------------+
```

The API provides:
- OpenAPI spec at `/api-schema.json`
- SSE stream at `/mcp` for live updates
- Full tool execution via POST

### Configuration

**Slide: "Environment Setup"**

```env
# Required
PLANNING_URL=https://your-epm-instance.oraclecloud.com
PLANNING_USERNAME=your-username
PLANNING_PASSWORD=your-password

# AI Integration
ANTHROPIC_API_KEY=your-claude-api-key
MODEL_ID=claude-sonnet-4-20250514

# RL Configuration
RL_ENABLED=true
RL_EXPLORATION_RATE=0.1
RL_LEARNING_RATE=0.1
RL_DISCOUNT_FACTOR=0.9

# Database
DATABASE_URL=sqlite:///./data/planning_agent.db
```

---

## SECTION 7: Key Takeaways & Q&A

### Summary Slide

**"What Makes This Special"**

1. **Natural Language Interface** - Finance teams can query EPM without technical knowledge

2. **Self-Improving** - The RL engine continuously optimizes tool selection based on success and user feedback

3. **Universal Compatibility** - Works with any custom Planning app through discovery tools

4. **Multi-Modal Deployment** - Claude Desktop, ChatGPT, Web API, or direct integration

5. **Enterprise Ready** - Full audit trail, session management, feedback tracking

### Technical Innovations

| Feature | Traditional Approach | Our Approach |
|---------|---------------------|--------------|
| API Calls | Manual grid building | Auto-generated from intent |
| Learning | Static rules | Q-learning with feedback |
| Context | Stateless queries | Session memory + context enrichment |
| Multi-step | Manual orchestration | Parallel execution pipeline |
| Unknown Apps | Requires documentation | Dynamic discovery tools |

### Future Roadmap

1. **FCCS Integration** - Consolidation-specific tools and workflows
2. **Predictive Analytics** - LLM-powered variance explanations
3. **Approval Workflows** - Multi-user approval chains
4. **Excel Integration** - Business rule generation from formulas

---

## Q&A Preparation

### Anticipated Questions & Answers

**Q: How does this handle authentication to Oracle EPM?**
> A: We use Basic Auth with the Planning REST API. The credentials are stored securely in environment variables. For enterprise deployment, we recommend integration with a secrets manager.

**Q: What happens if the LLM generates incorrect API calls?**
> A: The system has multiple safeguards:
> 1. Intent classification validates the query type
> 2. Entity extraction uses regex patterns for dimension members
> 3. The Planning client validates the grid structure before submission
> 4. Error results are fed back into the RL engine as negative rewards

**Q: How much data is needed to train the RL model?**
> A: The Q-learning approach is sample-efficient. We typically see meaningful improvements after 50-100 queries. The system also uses transfer learning from successful sequences, so patterns learned in one session apply to new users.

**Q: Can this work with Smart View or other Oracle tools?**
> A: The current implementation uses the REST API. Smart View integration would require additional development, though the architecture is extensible. We do export metadata that could be used with Smart View data forms.

**Q: What's the latency like for typical queries?**
> A: Simple data retrieval: 1-2 seconds
> Multi-step variance analysis: 3-5 seconds (parallel execution)
> Discovery of new app: 5-10 seconds (one-time)

---

## Closing Statement

> "We've transformed Oracle EPM Planning from a technical tool requiring specialized knowledge into a conversational partner that understands what finance teams actually need. The combination of intelligent intent classification, LLM reasoning, and reinforcement learning creates an agent that not only works today but gets smarter with every interaction.

> Thank you for your time. I'm happy to take questions or dive deeper into any technical aspect of the system."

---

## Appendix: Technical Deep Dives (For Extended Q&A)

### A1: The Grid Definition Challenge

The Oracle Planning REST API requires specific grid definitions:

```json
{
  "suppressMissingBlocks": true,
  "pov": {
    "members": [
      ["Total Entity"],
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
      "members": [["411110"]]
    }
  ]
}
```

Our `smart_retrieve` tools abstract this complexity entirely.

### A2: Tool Catalog

| Category | Tools | Description |
|----------|-------|-------------|
| Application | get_application_info, get_rest_api_version | Basic app info |
| Data | smart_retrieve, smart_retrieve_revenue, smart_retrieve_monthly, smart_retrieve_variance, export_data_slice | Data retrieval |
| Dimensions | get_dimensions, get_members, get_member | Dimension exploration |
| Jobs | list_jobs, get_job_status, execute_job | Job management |
| Discovery | discover_app_structure, explore_dimension, find_members, build_dynamic_grid | Custom app support |
| Inference | smart_infer, infer_member, infer_hierarchy | Semantic matching |
| Feedback | submit_feedback, rate_last_tool, get_rle_dashboard | RL integration |

### A3: Context Memory Schema

```python
class ContextMemory:
    """Session context for multi-turn conversations"""

    def update_from_entities(self, session_id, entities):
        # Remember: entity, period, scenario, etc.

    def update_from_result(self, session_id, tool_name, result):
        # Learn from successful operations

    def get_suggested_params(self, session_id, tool_name):
        # Suggest parameters based on context
```

This enables conversations like:
- "Show Chicago revenue" -> E501, Q4, Actual
- "Now compare to forecast" -> Remembers E501, Q4, uses Forecast

---

*End of Presentation Script*

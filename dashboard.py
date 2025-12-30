import streamlit as st
import asyncio
import pandas as pd
import sys
import os

# Add the project root to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from planning_agent.agent import initialize_agent
from planning_agent.tools.feedback import get_rle_dashboard

st.set_page_config(
    page_title="Planning RLE Dashboard",
    page_icon="🤖",
    layout="wide"
)

async def load_data():
    # Initialize the agent to ensure services are ready
    await initialize_agent()
    return await get_rle_dashboard()

def main():
    st.title("🤖 Planning Reinforcement Learning Dashboard")
    st.markdown("---")
    
    # Use a placeholder for the dashboard content
    dashboard_placeholder = st.empty()
    
    try:
        # Run the async data loading
        result = asyncio.run(load_data())
        
        if result["status"] == "success":
            data = result["data"]
            summary = data["summary"]
            
            with dashboard_placeholder.container():
                # Summary Section
                st.subheader("📊 System Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                # Format success rate
                success_rate = summary.get("avg_success_rate", 0)
                if success_rate <= 1.0:
                    success_rate_str = f"{success_rate:.1%}"
                else:
                    success_rate_str = f"{success_rate}"

                col1.metric("Total Executions", summary.get("total_executions", 0))
                col2.metric("Avg Success Rate", success_rate_str)
                col3.metric("Active Tools", summary.get("active_tools", 0))
                col4.metric("RL Status", "Active ✅" if summary.get("rl_enabled") else "Inactive ❌")
                
                st.markdown("---")
                
                # Tool Performance Section
                st.subheader("🛠️ Tool Performance")
                performance_data = data.get("tool_performance", [])
                
                if performance_data:
                    df = pd.DataFrame(performance_data)
                    
                    # Rename columns for better display
                    column_mapping = {
                        "tool_name": "Tool Name",
                        "total_calls": "Total Calls",
                        "success_rate": "Success Rate",
                        "avg_execution_time_ms": "Avg Latency (ms)",
                        "avg_user_rating": "User Rating"
                    }
                    df = df.rename(columns=column_mapping)
                    
                    # Reorder columns to show the most important first
                    cols = [c for c in column_mapping.values() if c in df.columns]
                    df = df[cols]
                    
                    # Display the dataframe with formatting
                    st.dataframe(
                        df.style.format({
                            "Success Rate": lambda x: f"{x:.1%}" if isinstance(x, (int, float)) else x,
                            "Avg Latency (ms)": lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x,
                            "User Rating": lambda x: f"{x:.1f} ⭐" if isinstance(x, (int, float)) and x > 0 else "No ratings"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No tool performance data available yet. Start using the agent to see metrics!")
                
                st.markdown("---")
                
                # Successful Paths Section
                st.subheader("📈 Successful Tool Sequences")
                paths = data.get("recent_successful_paths", [])
                
                if paths:
                    for i, path in enumerate(paths):
                        st.text(f"Path {i+1}:")
                        st.code(" ➔ ".join(path))
                else:
                    st.info("No multi-tool sequences recorded yet.")
                    
        else:
            st.error(f"❌ Error loading dashboard: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        st.error(f"❌ An unexpected error occurred: {str(e)}")
        st.exception(e)

if __name__ == "__main__":
    main()


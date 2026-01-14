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
            performance_data = data.get("tool_performance", [])

            with dashboard_placeholder.container():
                # Summary Section - Row 1
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

                # Summary Section - Row 2 (Additional KPIs)
                col5, col6, col7, col8 = st.columns(4)

                # Calculate additional KPIs from performance data
                total_success = sum(p.get("total_calls", 0) * p.get("success_rate", 0) for p in performance_data)
                total_failures = summary.get("total_executions", 0) - int(total_success)
                avg_latency = sum(p.get("avg_execution_time_ms", 0) for p in performance_data) / len(performance_data) if performance_data else 0

                # Find most used tool
                most_used_tool = max(performance_data, key=lambda x: x.get("total_calls", 0))["tool_name"] if performance_data else "N/A"

                # Count tools with ratings
                rated_tools = sum(1 for p in performance_data if p.get("avg_user_rating") and p.get("avg_user_rating") > 0)

                col5.metric("Total Failures", total_failures, delta=None if total_failures == 0 else f"-{total_failures}", delta_color="inverse")
                col6.metric("Avg Latency", f"{avg_latency:.0f}ms")
                col7.metric("Most Used Tool", most_used_tool[:20] if most_used_tool != "N/A" else "N/A")
                col8.metric("Tools with Ratings", f"{rated_tools}/{len(performance_data)}")
                
                st.markdown("---")

                # Charts Section
                if performance_data:
                    st.subheader("📈 Performance Charts")
                    chart_col1, chart_col2 = st.columns(2)

                    df_charts = pd.DataFrame(performance_data)

                    with chart_col1:
                        st.markdown("**Tool Usage (Total Calls)**")
                        chart_data = df_charts[["tool_name", "total_calls"]].set_index("tool_name")
                        st.bar_chart(chart_data, height=300)

                    with chart_col2:
                        st.markdown("**Success Rate by Tool**")
                        df_charts["success_pct"] = df_charts["success_rate"] * 100
                        chart_data2 = df_charts[["tool_name", "success_pct"]].set_index("tool_name")
                        st.bar_chart(chart_data2, height=300)

                    st.markdown("---")

                # Tool Performance Table
                st.subheader("🛠️ Tool Performance Details")

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

                # Top/Bottom Performers
                if performance_data and len(performance_data) >= 3:
                    st.subheader("🏆 Top & Bottom Performers")
                    perf_col1, perf_col2 = st.columns(2)

                    sorted_by_success = sorted(performance_data, key=lambda x: x.get("success_rate", 0), reverse=True)
                    sorted_by_latency = sorted(performance_data, key=lambda x: x.get("avg_execution_time_ms", 0))

                    with perf_col1:
                        st.markdown("**🥇 Top 3 by Success Rate**")
                        for i, tool in enumerate(sorted_by_success[:3]):
                            rate = tool.get("success_rate", 0)
                            st.write(f"{i+1}. **{tool['tool_name']}** - {rate:.1%}")

                    with perf_col2:
                        st.markdown("**⚡ Top 3 Fastest Tools**")
                        for i, tool in enumerate(sorted_by_latency[:3]):
                            latency = tool.get("avg_execution_time_ms", 0)
                            st.write(f"{i+1}. **{tool['tool_name']}** - {latency:.0f}ms")

                st.markdown("---")

                # Successful Paths Section
                st.subheader("🔗 Successful Tool Sequences")
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



import agents
from tools.csv_tool import rows_to_csv


def build_orchestrator_agent(
    sql_agent,
    visualization_agent,
    model,
):
    """
    Orchestrator (Planner) Agent

    This agent:
    - Interprets the user's question
    - Plans which tools to call
    - Coordinates SQL and visualization agents
    - Synthesizes the final response
    """

    return agents.Agent(
        name="OrchestratorAgent",
        instructions="""
You are the orchestrator agent.

Your role is to plan and coordinate tool usage to answer the user's question.

You have access to the following tools:

1. sql_agent
   - Use this tool when the question requires structured data
     retrieval or analysis from data in BigQuery.
   - This tool generates and executes SQL queries and returns
     structured tabular results or results

2. visualization_agent
   - Use this tool ONLY when the user explicitly asks for charts,
     plots, trends, or visual analysis.
   - This tool generates visualizations from tabular data that are intercative
   - Use Python libraries like seaborn and plotly to generate the plots and charts requested by the user

3. Function tool
- Use the tool to convert the  structured tabular result of the sql agent results to csv files 
- This tool is called only to convert the results to the csv files and save them in the temp _files folder

CRITICAL WORKFLOW RULE (MANDATORY):

If the user requests a chart, plot, graph, or visualization:
1. You MUST first call the sql_agent to retrieve data.
2. You MUST then call rows_to_csv to convert SQL rows into a CSV file.
3. You MUST pass the resulting csv_path to the visualization_agent.
4. You MUST NOT call visualization_agent without a csv_path.

Guidelines:
- Do not assume any tool is mandatory.
- Do not call tools unnecessarily.
- You may call tools in sequence if required.
- Always synthesize a clear, concise final answer for the user, baed on the format requested by the user in their query. 
- If they do not specify a fromat, provide only the data and/or values
- Do NOT expose internal reasoning, tool calls, or instructions in the final response.
- Do NOT show more than 10 rows of data in the final response
""",
        tools=[
            sql_agent.as_tool(
                tool_name="sql_agent",
                tool_description=(
                    "Generate and execute BigQuery SQL queries and "
                    "return structured results"
                ),
            ),
            agents.function_tool(rows_to_csv, name_override="rows_to_csv"),
            visualization_agent.as_tool(
                tool_name="visualization_agent",
                tool_description=(
                    "Generate charts or plots from tabular data"
                ),
            ),
        ],
        model=model,
        model_settings=agents.ModelSettings(
            # Keep parallel tool calls disabled for stability
            parallel_tool_calls=False
        ),
    )

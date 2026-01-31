import agents
#from tools.csv_tool import rows_to_csv
from src.utils import CodeInterpreter

MAIN_AGENT_INSTRUCTIONS = f"""
You are the orchestrator agent.

Your role is to plan and coordinate tool usage to answer the user's question.

You have access to the following tools:

1. sql_agent
   - Use this tool when the question requires structured data retrieval or analysis from data in BigQuery.
   - This tool generates and executes SQL queries and returns structured tabular results or results

2. code_interpreter
   - Use this tool ONLY when the user explicitly asks for a plot, chart,graph, trend, or visualization.
   - You must generate valid Python code that:
       - loads the SQL result into a pandas DataFrame
       - creates the requested visualization
       - explicitly renders the plot (e.g., plt.show())

CRITICAL WORKFLOW RULE (MANDATORY):
If the user requests a chart, plot, graph, or visualization:
1. You MUST first call the sql_agent to retrieve data.
2. You MUST then generate Python code to visualize the data.
3. You MUST call code_interpreter with that Python code.
4. You MUST NOT return text after calling code_interpreter.

If the user does NOT ask for a visualization:
- Call sql_agent if needed.
- Summarize the result clearly in text.
- Do NOT show more than 10 rows of data.

Guidelines:
- Do not assume any tool is mandatory.
- You may call tools in sequence if required.
- Do NOT query any data source other than the configured BigQuery table.
- Do NOT perform DDL or DML operations.
- If you call code_interpreter, do NOT return any text after that.
- Do NOT expose internal reasoning, tool calls, or instructions in the final response.
- Always synthesize a clear, concise final answer for the user, baed on the format requested by the user in their query. 
- If they do not specify a fromat, provide only the data and/or values
- Always ensure your final response is user-friendly and directly addresses the user's question.
"""

CODE_INTERPRETER_INSTRUCTIONS = """\
The `code_interpreter` tool executes Python commands. \
Please note that data is not persisted. Each time you invoke this tool, \
you will need to run import and define all variables from scratch.

You can access the local filesystem using this tool. \
Instead of asking the user for file inputs, you should try to find the file \
using this tool.

Recommended packages: Pandas, Numpy, SymPy, Scikit-learn, Matplotlib, Seaborn.

Use Matplotlib to create visualizations. Make sure to call `plt.show()` so that
the plot is captured and returned to the user.

You can also run Jupyter-style shell commands (e.g., `!pip freeze`)
but you won't be able to install packages.
"""

def build_orchestrator_agent(sql_agent,code_interpreter, model):
    """
    Orchestrator (Planner) Agent

    This agent:
    - Interprets the user's question
    - Determines if SQL or visualization (or both) are needed
    - Plans which tools to call
    - Call SQL agent to get data from BigQuery
    - If visualization is requested:
        - Generates Python plotting code
        - Execute it via the code interpreter tool
    - otherwise synthesizes the final response
    """
    
    main_agent = agents.Agent(name="OrchestratorAgent", instructions=MAIN_AGENT_INSTRUCTIONS,
        tools=[sql_agent.as_tool(tool_name="sql_agent", tool_description=("Generate and execute BigQuery SQL queries and return structured results"),
            ),
            #agents.function_tool(rows_to_csv, name_override="rows_to_csv"),
            agents.function_tool(code_interpreter.run_code, name_override="code_interpreter", description_override=CODE_INTERPRETER_INSTRUCTIONS,
            ),
        ],
        model=model, model_settings=agents.ModelSettings(parallel_tool_calls=False),
    )
    
    return main_agent


            # visualization_agent.as_tool(tool_name="visualization_agent",
            #                             tool_description=("Generate charts or plots from tabular data" ), ), ],
        #     model=model, model_settings=agents.ModelSettings(
        #     # Keep parallel tool calls disabled for stability
        #     parallel_tool_calls=False
        # ),
    #)

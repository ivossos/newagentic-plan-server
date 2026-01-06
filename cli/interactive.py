"""Interactive CLI with keyboard shortcuts for rating tool executions."""

import asyncio
import sys
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit("cli", 1)[0])

from planning_agent.agent import initialize_agent, close_agent, execute_tool, get_tool_definitions
from planning_agent.tools.feedback import rate_last_tool, get_recent_executions
from planning_agent.services.feedback_service import get_feedback_service


# Styling
STYLE = Style.from_dict({
    'prompt': '#4fc3f7 bold',
    'tool': '#81c784',
    'success': '#4caf50',
    'error': '#f44336',
    'rating': '#ffc107',
    'hint': '#888888',
})

# Last execution tracking
_last_execution_id: Optional[int] = None
_last_tool_name: Optional[str] = None


def print_colored(text: str, color: str = 'white'):
    """Print colored text."""
    colors = {
        'cyan': '\033[96m',
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
        'gray': '\033[90m',
        'white': '\033[97m',
        'reset': '\033[0m'
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


def print_header():
    """Print CLI header."""
    print()
    print_colored("=" * 60, 'cyan')
    print_colored("  Planning Agent - Interactive CLI with RL Feedback", 'cyan')
    print_colored("=" * 60, 'cyan')
    print()
    print_colored("Commands:", 'yellow')
    print("  /tools     - List available tools")
    print("  /history   - Show recent executions")
    print("  /help      - Show help")
    print("  /quit      - Exit")
    print()
    print_colored("Rating shortcuts (after tool execution):", 'yellow')
    print("  g or 5  - Good (5 stars)")
    print("  b or 1  - Bad (1 star)")
    print("  2,3,4   - Specific rating")
    print("  Enter   - Skip rating")
    print()


def print_tool_result(tool_name: str, result: dict):
    """Print tool execution result."""
    global _last_execution_id, _last_tool_name

    status = result.get("status", "unknown")
    execution_id = result.get("execution_id")

    _last_execution_id = execution_id
    _last_tool_name = tool_name

    print()
    if status == "success":
        print_colored(f"[{tool_name}] Success", 'green')
        data = result.get("data", {})
        if isinstance(data, dict):
            for key, value in list(data.items())[:5]:  # Show first 5 items
                print(f"  {key}: {value}")
            if len(data) > 5:
                print(f"  ... and {len(data) - 5} more fields")
        else:
            print(f"  {str(data)[:200]}")
    else:
        print_colored(f"[{tool_name}] Error: {result.get('error', 'Unknown error')}", 'red')

    if execution_id:
        print_colored(f"  (execution_id: {execution_id})", 'gray')


async def prompt_for_rating() -> Optional[int]:
    """Prompt user for rating with keyboard shortcuts."""
    global _last_execution_id

    if not _last_execution_id:
        return None

    print()
    print_colored("Rate this result: [g]ood/[b]ad or 1-5 (Enter to skip): ", 'yellow')

    # Simple input for rating
    try:
        # Use a short timeout for rating input
        rating_input = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, input),
            timeout=10.0
        )
    except asyncio.TimeoutError:
        print_colored("  (rating skipped - timeout)", 'gray')
        return None

    rating_input = rating_input.strip().lower()

    if not rating_input:
        print_colored("  (rating skipped)", 'gray')
        return None

    # Map input to rating
    rating_map = {
        'g': 5, 'good': 5, '5': 5,
        'b': 1, 'bad': 1, '1': 1,
        '2': 2, '3': 3, '4': 4,
        'ok': 3, 'o': 3
    }

    rating = rating_map.get(rating_input)

    if rating:
        result = await rate_last_tool(str(rating))
        if result.get("status") == "success":
            stars = "*" * rating
            print_colored(f"  Rating submitted: {stars} ({rating}/5)", 'green')
        else:
            print_colored(f"  Failed to submit rating: {result.get('error')}", 'red')
        return rating
    else:
        print_colored(f"  Invalid rating: {rating_input}", 'red')
        return None


async def handle_command(command: str) -> bool:
    """Handle CLI commands. Returns False to exit."""
    cmd = command.strip().lower()

    if cmd in ('/quit', '/exit', '/q'):
        return False

    elif cmd == '/tools':
        tools = get_tool_definitions()
        print()
        print_colored("Available tools:", 'cyan')
        for tool in tools:
            print(f"  - {tool['name']}")
            desc = tool.get('description', '')[:60]
            if desc:
                print_colored(f"    {desc}", 'gray')
        print()

    elif cmd == '/history':
        result = await get_recent_executions(limit=10)
        if result.get("status") == "success":
            executions = result.get("data", {}).get("executions", [])
            print()
            print_colored("Recent executions:", 'cyan')
            for e in executions:
                rating_str = f"{'*' * e['user_rating']}" if e.get('user_rating') else "not rated"
                status = "OK" if e.get('success') else "FAIL"
                print(f"  [{e['execution_id']}] {e['tool_name']} - {status} - {rating_str}")
            print()
        else:
            print_colored("Failed to get history", 'red')

    elif cmd == '/help':
        print_header()

    else:
        print_colored(f"Unknown command: {command}", 'red')
        print("Type /help for available commands")

    return True


async def execute_query(query: str):
    """Execute a tool query."""
    # Parse simple format: tool_name arg1=val1 arg2=val2
    parts = query.split()
    if not parts:
        return

    tool_name = parts[0]
    arguments = {}

    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            # Try to parse as number
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            arguments[key] = value

    # Check if tool exists
    tools = get_tool_definitions()
    tool_names = [t['name'] for t in tools]

    if tool_name not in tool_names:
        print_colored(f"Unknown tool: {tool_name}", 'red')
        print(f"Available tools: {', '.join(tool_names[:5])}...")
        return

    print_colored(f"Executing: {tool_name}({arguments})", 'gray')

    try:
        result = await execute_tool(tool_name, arguments, session_id="interactive")
        print_tool_result(tool_name, result)
        await prompt_for_rating()
    except Exception as e:
        print_colored(f"Error: {e}", 'red')


async def main_loop():
    """Main interactive loop."""
    session = PromptSession()

    print_header()

    while True:
        try:
            # Get input
            user_input = await session.prompt_async(
                HTML('<prompt>planning> </prompt>'),
                style=STYLE
            )

            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith('/'):
                should_continue = await handle_command(user_input)
                if not should_continue:
                    break
            else:
                # Execute as tool query
                await execute_query(user_input)

        except KeyboardInterrupt:
            print()
            print_colored("Use /quit to exit", 'yellow')
        except EOFError:
            break


async def async_main():
    """Async entry point."""
    print_colored("Initializing agent...", 'gray')
    await initialize_agent()

    try:
        await main_loop()
    finally:
        print_colored("Closing agent...", 'gray')
        await close_agent()
        print_colored("Goodbye!", 'cyan')


def main():
    """Entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)


if __name__ == "__main__":
    main()

from planning_agent.fastmcp_server import build_fastmcp_server


def main() -> None:
    server = build_fastmcp_server()
    server.run("stdio")


if __name__ == "__main__":
    main()


import sys

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport


def prompt_api_key() -> str:
    api_key = input("Linear API key: ").strip()
    if not api_key:
        print("API key is required.")
        sys.exit(1)
    return api_key


def create_client(api_key: str) -> Client:
    transport = RequestsHTTPTransport(
        url="https://api.linear.app/graphql",
        headers={"Authorization": api_key},
    )
    return Client(transport=transport, fetch_schema_from_transport=True)


def get_teams(client: Client):
    query = gql(
        """
        query GetTeams {
            teams {
                nodes {
                    id
                    name
                    key
                }
            }
        }
        """
    )
    result = client.execute(query)
    return result["teams"]["nodes"]


def get_projects(client: Client, team_id: str):
    query = gql(
        """
        query GetProjects($teamId: String!) {
            team(id: $teamId) {
                projects {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """
    )
    result = client.execute(query, variable_values={"teamId": team_id})
    return result["team"]["projects"]["nodes"]


def get_team_data(client: Client, team_id: str):
    query = gql(
        """
        query GetTeamData($teamId: String!) {
            team(id: $teamId) {
                states {
                    nodes {
                        id
                        name
                        type
                    }
                }
                labels {
                    nodes {
                        id
                        name
                        color
                    }
                }
            }
        }
        """
    )
    result = client.execute(query, variable_values={"teamId": team_id})
    return result["team"]


def choose_team(teams):
    for i, team in enumerate(teams, 1):
        print(f"{i}. {team['name']} (Key: {team['key']}, ID: {team['id']})")
    while True:
        choice = input("Select a team (number): ").strip()
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(teams):
                return teams[index]
        print("Invalid choice.")


def main() -> int:
    api_key = prompt_api_key()
    try:
        client = create_client(api_key)
    except Exception as exc:
        print(f"Failed to connect: {exc}")
        return 1

    try:
        teams = get_teams(client)
    except Exception as exc:
        print(f"Failed to fetch teams: {exc}")
        return 1

    if not teams:
        print("No teams found.")
        return 1

    team = choose_team(teams)
    team_id = team["id"]

    print(f"\nSelected team: {team['name']} (ID: {team_id})")

    try:
        projects = get_projects(client, team_id)
    except Exception as exc:
        print(f"Failed to fetch projects: {exc}")
        return 1

    if projects:
        print("\nProjects (optional):")
        for project in projects:
            print(f"- {project['name']} (ID: {project['id']})")

    try:
        team_data = get_team_data(client, team_id)
    except Exception as exc:
        print(f"Failed to fetch team data: {exc}")
        return 1

    print("\nStates:")
    for state in team_data["states"]["nodes"]:
        print(f"- {state['name']} (ID: {state['id']}, Type: {state['type']})")

    print("\nLabels:")
    for label in team_data["labels"]["nodes"]:
        print(f"- {label['name']} (ID: {label['id']}, Color: {label['color']})")

    print("\n.env entries:")
    print("LINEAR_API_KEY=<your_api_key>")
    print(f"LINEAR_TEAM_ID={team_id}")
    print("LINEAR_PROJECT_ID=<project_id>")
    print("LINEAR_STATE_TODO_ID=<state_id>")
    print("LINEAR_STATE_BACKLOG_ID=<state_id>")
    print("LINEAR_LABEL_URGENT_ID=<label_id>")
    print("LINEAR_LABEL_HIGH_PRIORITY_ID=<label_id>")
    print("LINEAR_LABEL_MEDIUM_PRIORITY_ID=<label_id>")
    print("LINEAR_LABEL_LOW_PRIORITY_ID=<label_id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

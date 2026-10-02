from dotenv import load_dotenv
load_dotenv()

from langsmith import Client

client = Client()
runs = list(client.list_runs(project_name="trustflow", limit=20))

if not runs:
    print("No traces found.")
else:
    for i, r in enumerate(runs):
        print(f"[{i}] {r.id}  |  {r.name}")

    idx = int(input("\nPick a number to dump: "))
    print(runs[idx].model_dump_json(indent=2))
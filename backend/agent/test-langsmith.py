from langsmith import Client
client = Client()
runs = list(client.list_runs(project_name="acme-agent", limit=5))
print(runs)
import json
import yaml

with open('default_data.json', 'r') as f:
    data = json.load(f)

with open('odl.yaml', 'r') as f:
    odl_projects = yaml.load(f.read())

odl_modules = []
for group, projects in odl_projects.items():
    odl_modules += [{
            "module": project,
            "uri": "https://git.opendaylight.org/gerrit/{}".format(project),
            "organization": "odl"} for project in projects]

odl_module_groups = [{
        "module_group_name": group,
        "modules": projects
    } for group, projects in odl_projects.items()]

print(json.dumps(odl_modules, indent=4))
print(json.dumps(odl_module_groups, indent=4))

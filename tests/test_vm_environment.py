from pathlib import Path
from importlib.metadata import requires, version
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
import yaml


def test_vm_environment_contains_runtime_dependencies_without_test_tools():
    env=yaml.safe_load((Path(__file__).resolve().parents[1]/'environment.yml').read_text())
    entries=next(item['pip'] for item in env['dependencies'] if isinstance(item,dict))
    pins={canonicalize_name(x.split('==')[0]):x.split('==')[1] for x in entries if '==' in x}
    assert not {'pytest','pluggy','iniconfig','pygments','playwright'} & pins.keys()
    assert {'torch','torchvision','streamlit','cloudinary','fastapi','httpx','av','opencv-python','pydantic-settings','python-multipart'} <= pins.keys()
    for name,v in pins.items():
        assert version(name)==v
        for raw in requires(name) or []:
            dep=Requirement(raw)
            if dep.marker is not None and not dep.marker.evaluate({'extra':''}):continue
            key=canonicalize_name(dep.name)
            # pip itself is supplied by Conda, not the pip package list.
            if key=='pip':continue
            assert key in pins,(name,key)
            assert dep.specifier.contains(pins[key]),(name,dep,pins[key])

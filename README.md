# Simple Python Versioning Manager

When working on a simpe python project, you don't want to handle the setup.py, Makefile if any, and all the release pipeline. Spvm aims to that part for you.

## Installation
spvm is on pypi.org and can be installed with a 
```
pip install spvm
```

## Requirements
- python 3
- docker*
- a pypi.org account*
- a repo for your project (github for instance)

(*: no necessary but available)

## Quickstart
The spvm syntax tries to be simmilar to git and npm:
- To initialize a spvm project use `` spvm init ``
- You can run `` spvm major/minor/patch`` to update the verison of your project
- Use ``spvm test`` to launch the tests on your project
- Use ``spvm repair`` to run autopep8 on your project to make it pep8 compliant
- Use ``spvm -s update`` to update the project's dependencies and check their signatures when available
<br><br><hr>

> Where is the version stored? In the ``setup.py`` ? In the ``__init__.py``?

Because we wanted all the project's data to be in one place we made a package.json like object containing the project info: ``pyp.json``

The version and the other project information such as the author's name, email are propagated in the setup.py and the ``__init__.py``

You can find the ``pyp.json`` template on ``spvm/res/pyp.json``:

```
{
    "project_info": {
        "name": "",
        "description": "",
        "license": "ISC",
        "url": ""
    },
    
    "project_authors": [
       {
        "name": "",
        "url": "",
        "email": ""
       }
    ],
    
    "project_vcs": {
        "code_repository": "",
        "docker_repository": "",
        "pypi_repository": "",
        
        "exclude_packages": ["test"],
        "version": "0.0.0",
        "ignored_errors": "E121,E123,E126,E226,E24,E704,W503,W504,E501",
        "release": {
            "commit_template": "Inscreased version to %s",
            "docker_tags": "latest,%s",
            "tag_template": "%s",
            "package_signing_key": "",
            "git_signing_key": ""
        }
    },

    "scripts": {
        "pre-test": "",
        "test": "pypi",
        "post-test":""
    },

    "project_requirements": {
        "python_version": ">=3.4, <4",
        "python_packages": []
    }
    
}
```


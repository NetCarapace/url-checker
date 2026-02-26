# URLChecker
URLChecker is a tool that allows to:
- check the validity of a provided URL,
- check if the content behind the URL is safe (reputation, etc.).

The modular application is built on top of:
- a serie of scripts that can be used locally,
- an Web Application backend that allows to interface to the script (API).

url-checker is a secure Python Flask web platform providing centralized URL validation, reachability testing, and
security assessment services. The platform maintains persistent state tracking for submitted URLs across three
dimensions: validity (schema and format), reachability (network connectivity), and security (threat intelligence).
It leverages an hybrid orchestration model with synchronous quick-response checks for validation and reachability, while
delegating computationally intensive security analysis to asynchronous job queues. The architecture leverages scheduling
workers integrated with a message broker for distributed task processing, ensuring scalability and fault tolerance.
RESTful API endpoints enable programmatic access with Bearer token authentication and comprehensive OpenAPI
documentation. All analysis results are persisted in MariaDB, providing historical tracking and audit trails for
compliance requirements. An optional deployment template demonstrates production-ready configuration with a hardened
web server behind Nginx reverse proxy handling SSL termination and rate limiting, complemented by systemd service
lifecycle management examples. The architecture facilitates a future bi-directional integration with external security
platforms such as MISP, enabling seamless threat intelligence sharing (POC exists with url-checker- tools).
Design choices prioritize future: scalability, administrative frontend extensibility, and streamlined facilitation of
development handover with, building on top of previous work, an integrated and documented development helpers suite.


## Getting started

## Collaboration, Contributing
- Our Definition of Done (DoD) is:
  - Tested,
  - ideally, Reviewed (mandatory in the applicable context),
  - Merged to ```main``` and Deployable from ```main``` if a new version was to be Released (see below).

- We follow Gitlab Flow for collaboration which is a [text](VERSION)simplification of the GitFlow, making it easier to couple with
DevOps and CI/CD principles (https://about.gitlab.com/topics/version-control/what-is-gitlab-flow/)
  - On top of that, we maintain files like ```RELEASE_NOTES.md```and ```UPGRADING_NOTES.md```,
  - With Gitblab UI, we release a new version from ```main``` branch on top of a version Git tag,
  - A new version can be associated to Gitlab Milestone to which various tasks and issues were done,
  - The Makefile recipe ```bump_version``` can be used to bump the new version and create the new version commit in a
  standardized way and in order to reduce overhead with Gitlab GUI to the maximum,
  - A merge to ```main``` creates a new commit in ```main``` and triggers the Build, Test and Deliver stages in
  ```main``` branch (so a successful pipeline after merging can be seen as a final step of our DoD approach),
  - A new commit related to the version bump, in ```main``` branch, also triggers these stages of CI/CD.

- In an effort of transparency and collaboration promotion, we maintain the file ```CONTRIBUTORS.md``` to leverage the
full Restena Team accountability accross teams while:
  - keeping in the light people who actively contributed to the repository,
  - avoiding to maintain dupplicate headers in each file with redundant things like ```version```, ```ownership```, etc.

- We share the same Development configuration by using pre-commit hooks. In practice::
  - it is the responsibility of the Developper to configure its own IDE so that the pre-configured formatter
  and linter does not complain (the later ```Security and formatting/linting pipelines```)
  - the Developper needs therefore configure the pre-commit locally so that he can correct its formatting and code
  patterns with the feedback provided by Formatters and Linters.

- Contribution are therefore welcomed in the form of opening Gitlab Issues and if possible providing the code that solve
the point: a Merge Request is then opened based on the Issue. It might be necessary to group Issues into a bigger Epic.

## Development

A development helper is provided in the form of a Makefile.
Inspiration is taken from (MIT License, see contrib subfolders, license files kept for legacy), improvements from it
will be backported:
- [my-devops-playground/makedeb-a-la-spoti](https://gitlab.com/tCR-lux/my-devops-playground/-/tree/master/Python/makedeb-a-la-spoti) Copyright © Cédric Renzi
- [my-devops-playground/packpy-src](https://gitlab.com/tCR-lux/my-devops-playground/-/tree/master/Python/packpy-src) Copyright © Cédric Renzi

Type ```make help``` from the king directory of this repository in order to get more insights.

Access to mariadb database in Dev:
- GUI Client for MariaDB: https://doc.ubuntu-fr.org/adminer
- make run_dev_infra
- http://localhost/adminer/?server=127.0.01&username=urlchecker&db=urlchecker
- make run_dev_infra (it will also stop the Apache2 server that is necessary for adminer)

## Test and Deploy

### Security and formatting/linting pipelines (TODO Gitlab -> GitHub)
Each commit pushed to any branch triggers:
- a Secret scanner,
- a Security scanner,
- a formatting and linting block of task. In case this fails, the pipeline does not go further.

### Building, Testing and Delivering pipelines (TODO Gitlab -> GitHub)
- Each commit to any branch triggers Tests (which does not require Build with Python and which allow to provide faster
Testing results to the Developper). It is advised to rely on the same Test mechanism both in CI/CD and on the local
Development environment (example: launcher script),
- A new commit in the ```main``` branch triggers ```Build``` and ```Deliver``` stages.

### Deployment
The deployment is kept manual with the brother repository ```urlchecker-deploy```

### Badges (tbd)
The status of the repository is easily identifiable with badges calculated at each pipeline runs and displayed in the
```README.md```.

## Documentation

{{ Mode detailed documentation is created in the ```doc``` folder. A ```Makefile``` helper is provided to construct
documentation on top of the content of this folder }}

## Product general description
## Product vision
The Product Vision is provided on NGSOTI/Restena websites.

## Roadmap
The Roadmap is maintained on GitHub in the shape of future milestones, associated future releases, and GitHub Issues
and/or Epics and/or defined Tasks associated to the Milestone.

## License
This software is licensed under [GNU Affero General Public License version 3](http://www.gnu.org/licenses/agpl-3.0.html)

```
Copyright (C) 2026 Fondation Restena
Copyright (C) 2026 Cédric Renzi
```

See details in LICENSE file for 3rd parties.

As mentionned in the collaboration section above, the Contributors hall-of-fame is maintained separately
the file ```CONTRIBUTORS.md```.

## Funding

URLChecker is co-funded by [Restena](https://www.restena.lu/) and by the European Union under [NGSOTI](https://restena.lu/fr/project/ngsoti) (Next Generation Security Operator Training Infrastructure) project.

![EU logo](https://www.vulnerability-lookup.org/images/eu-funded.jpg)
![NGSOTI logo](https://restena.lu/files/styles/large/public/inline-images/ngsoti-logo-verti-col.png)
![Restena logo](https://restena.lu/sites/restena.lu/themes/site_theme/images/logo.svg)

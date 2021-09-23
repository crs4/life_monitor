[![main workflow](https://github.com/crs4/life_monitor/actions/workflows/main.yaml/badge.svg)](https://github.com/crs4/life_monitor/actions/workflows/main.yaml)
[![docs workflow](https://github.com/crs4/life_monitor/actions/workflows/docs.yaml/badge.svg)](https://github.com/crs4/life_monitor/actions/workflows/docs.yaml)


<div align="center" style="text-align: center; margin-top: 50px;">
<img src="/docs/life_monitor_logo.png" alt="Life-Monitor logo"
     width="300px" style="margin-top: 50px;" align="center" />
</div>

<br/>
<br/>

LifeMonitor is a testing and monitoring service for computational
workflows. Head over to the [LifeMonitor web
site](https://crs4.github.io/life_monitor) for more information and instructions.


## Getting Started

You can easily set up your own ready-to-use LifeMonitor instance using the
docker-compose deployment we distribute with this repository. A `Makefile`
provides you with the basic actions necessary to manage the deployment.
Type `make help` to list the available options.

You can get a development / testing deployment of LifeMonitor with the
following commands:

0. `docker network create life_monitor`, to create the Docker network;
1. `make start`, to start the main LifeMonitor services;
2. `make start-aux-services`, to start the preconfigured instances of WorkflowHub and Jenkins.

To register the WorkflowHub instance with LifeMonitor, run:

```
docker-compose exec lm /bin/bash -c "flask registry add seek seek ehukdECYQNmXxgJslBqNaJ2J4lPtoX_GADmLNztE8MI DuKar5qYdteOrB-eTN4F5qYSp-YrgvAJbz1yMyoVGrk https://seek:3000 --redirect-uris https://seek:3000"
```

You should now have the following services up and running:

* **LifeMonitor** @ https://localhost:8443
* **WorkflowHub** @ https://seek:3000
* **Jenkins** @ http://localhost:8080

For additional information, please refer to the [LifeMonitor administration
guide](https://crs4.github.io/life_monitor/lm_admin_guide).


<br><br><br>
<div align="center" style="text-align: center;">
  <div><b style="font-size: larger">Acknowledgements</b></div>
  <div>
    Life Monitor is being developed as part of the <a href="https://www.eosc-life.eu/">EOSC-Life project</a>.
  </div>
  <img alt="EOSC-Life, CRS4, BBMRI-ERIC Logos"
       src="https://github.com/crs4/life_monitor/raw/master/docs/footer-logo.svg"
	   width="350" align="center"/>
</div>

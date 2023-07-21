# Interactive heater regulator
A loose collection of scripts and services to regulate an old Vaillant heater via Raspberry Pi.
The regulator is a simple python script and is executed through a systemd service in a screen terminal.
To gather and visualize all kinds of metrics the script exposes data to prometheus. The metrics
can be shown in a Grafana dashboard.

## Table of contents
* [Technologies](#technologies)
* [Setup](#setup)
* [Status](#status)
* [Contact](#contact)

## Technologies
* Python
* Prometheus
* Grafana

## Setup
1. Install Prometheus and Grafana
2. Clone the repository
3. Create virtualenv and install requirements.txt
4. Edit and move `heizung.service` and `prometheus.service` to `/etc/systemd/system`
5. Enable the systemd services
6. After a reboot check `screen -r Heizung` for an interactive shell to the regulator

## Status
Project is: _active_.

## Contact
Created by [@ma-adrian] - feel free to contact me!

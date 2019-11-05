[![Build Status](https://travis-ci.org/ambianic/ambianic-edge.svg?branch=master)](https://travis-ci.org/ambianic/ambianic-edge) [![Docker Automated](https://img.shields.io/docker/cloud/automated/ambianic/ambianic.svg)](https://hub.docker.com/r/ambianic/ambianic/builds) [![Docker Build](https://img.shields.io/docker/cloud/build/ambianic/ambianic.svg)](https://hub.docker.com/r/ambianic/ambianic/builds) [![codecov](https://codecov.io/gh/ambianic/ambianic-core/branch/master/graph/badge.svg)](https://codecov.io/gh/ambianic/ambianic-core)
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fambianic%2Fambianic-core.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fambianic%2Fambianic-core?ref=badge_shield) [![CodeFactor](https://www.codefactor.io/repository/github/ambianic/ambianic-edge/badge)](https://www.codefactor.io/repository/github/ambianic/ambianic-edge)

![Ambianic logo][logo]

# Project mission
Helpful AI for Home and Business Automation

Local data, custom AI models, federated learning

# Project Status
At this time, Ambianic is in active early formation stages. Lots of design and implementation decisions are made daily with focus on advancing the project to an initial stable version as soon as possible.

If you are willing to take the risk that comes with early stage code and are able to dive deep into Python, Javascript, Gstreamer, and Tensorflow code, then please keep reading. Otherwise click on the Watch button above (Releases Only option) to be notified when we release a stable end user version.

# Product design guidelines

When the product is officially released, it must show tangible value to first time users with minimal initial investment.
- Less than 15 minutes setup time
- Less than $75 in hardware costs
  + Primary target platform: Raspberry Pi 4 B, 4GB RAM, 32GB SDRAM
- No coding required to get started
- Decomposable and hackable

# How to run in development mode
If you are interested to try the development version, follow these steps:
1. Clone this git repository.
2. `./ambianic-start.sh`
3. Study `config.yaml` and go from there.

# Documentation

An introduction to the project with user journey, architecture and other high level artifacts are [now available here](https://ambianic.github.io/ambianic-docs/).

Additional content is coming in daily as the project advances to its official release. 

# Contributing
Your constructive feedback and help are most welcome!

If you are interested in becoming a contributor to the project, please read the [Contributing](CONTRIBUTING.md) page and follow the steps. Looking forward to hearing from you!

[logo]: https://avatars2.githubusercontent.com/u/52052162?s=200&v=4

# Acknowledgements

This project has been inspired by the prior work of many bright people. Special gratitude to:
* [Yong Tang](https://github.com/yongtang) for his guidance as Tensorflow SIG IO project lead
* [Robin Cole](https://github.com/robmarkcole) for his invaluable insights and code on home automation AI with Home Assistant
* [Blake Blackshear](https://github.com/blakeblackshear) for his work on Frigate and vision for the home automation AI space

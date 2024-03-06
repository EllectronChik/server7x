<a name="readme-top"></a>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/EllectronChik/server7x">
    <img src="favicon.svg" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">7x Team League Server</h3>

  <p align="center">
    Server side of the project dedicated to holding team leagues on StartCraft 2 game
    <br />
    <a href="https://github.com/EllectronChik/client7x/issues">Report Bug</a>
    ·
    <a href="https://github.com/EllectronChik/client7x/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

This backend project powers a platform for managing team leagues in StarCraft 2. It enables users to register teams, join tournaments, and report match outcomes.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [![Django][django_shield]][django_url]
* [![Channels][channels_shield]][channels_url]
* [![Celery][celery_shield]][celery_url]
* [![Redis][redis_shield]][redis_url]
* [![MariaDB][mariadb_shield]][mariadb_url]
* [![Blizzard API][blizzard_shield]][blizzard_url]



<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

- [ ] Python 3
- [ ] Mariadb
- [ ] Redis
- [ ] Git

### Installation

_Before running the server, make sure you have all the required dependencies installed && set up the mariadb database._

1. Clone the repository
    ```bash
    git clone https://github.com/EllectronChik/server7x.git
    ```

    ```bash
    cd server7x
    ```

2. Create a virtual environment
    ```bash
    python -m venv venv
    ```
3. Activate the virtual environment
    ```bash
    source venv/bin/activate
    ```
4. Install dependencies
    ```bash
    pip install -r requirements.txt
    ```

5. Create a .env file with the following content
    ```bash
      SECRET_KEY={{SECRET_KEY}}

      DEBUG_VALUE={{DEBUG_VALUE}}

      DATABASE_NAME={{DATABASE_NAME}}
      DATABASE_USER={{DATABASE_USER}}
      DATABASE_PASSWORD={{DATABASE_PASSWORD}}
      DATABASE_HOST={{DATABASE_HOST}}
      DATABASE_PORT={{DATABASE_PORT}}

      REDIS_HOST={{REDIS_HOST}}
      REDIS_PORT={{REDIS_PORT}}

      WEBSOCKET_AUTH_TIMEOUT={{WEBSOCKET_AUTH_TIMEOUT}} # value in seconds, default 5

      ALLOWED_HOSTS={{ALLOWED_HOSTS}}
    ```

6. Create a .ini file with the following content
    ```bash
      [BLIZZARD]
      blizzard_api_id = {{BLIZZARD_API_ID}}
      blizzard_api_secret = {{BLIZZARD_API_SECRET}}
      blizzard_api_token = # Can be left blank
    ```

7. Run the initialization script
    ```bash
    python manage.py start_database
    ```

8. Run the server
    ```bash
    python manage.py runserver
    ```

9. Run the celery beat
    ```bash
    celery -A server7x beat -l info
    ```

10. Run the celery worker
    ```bash
    celery -A server7x worker -l info
    ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[django_shield]: https://img.shields.io/badge/django-4.2.5-blue?style=for-the-badge&logo=django&logoColor=white
[django_url]: https://www.djangoproject.com/
[channels_shield]: https://img.shields.io/badge/channels-4.0.0-blue?style=for-the-badge&logo=channels&logoColor=white
[channels_url]: https://channels.readthedocs.io/en/stable
[celery_shield]: https://img.shields.io/badge/celery-5.3.6-blue?style=for-the-badge&logo=celery&logoColor=white
[celery_url]: https://docs.celeryq.dev/en/stable/
[redis_shield]: https://img.shields.io/badge/redis-5.0.14-blue?style=for-the-badge&logo=redis&logoColor=white
[redis_url]: https://redis.io/
[mariadb_shield]: https://img.shields.io/badge/mariadb-11.3.2-blue?style=for-the-badge&logo=mariadb&logoColor=white
[mariadb_url]: https://mariadb.com
[blizzard_shield]: https://img.shields.io/badge/blizzard-API-blue?style=for-the-badge&logo=blizzard&logoColor=white
[blizzard_url]: https://develop.battle.net/
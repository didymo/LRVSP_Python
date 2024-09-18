# Install

Copy config.template.py to config.py and fill out the paths to the drupal base installation (contains /vendor and /web) and the log file. Also fill out the database details for the communication database.

# Systemd Service File Installation
`lrvspDaemon.template.service` is a template that you can use to create a systemd service file to run the daemon on boot.
## Simple Install
If run from inside the `LRVSP_Python` directory, the following snippet of shell script will automatically configure the service as follows:
1. A python venv will be created in `./venv`
2. The daemon will be run as the (at the time of configuring) currently logged in user.
3. The dameon will be run using the venv created in (1)
```bash
python3 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt
deactivate
export GROUP=$(id -gn)
export LRVSP_PYTHON_VENV="$(realpath ./venv)"
export LRVSP_PYTHON_ROOT="$(realpath .)"
envsubst < lrvspDaemon.template.service | sudo tee /etc/systemd/system/lrvspDaemon.service
sudo systemctl daemon-reload
```

After this, you should be free to start the daemon (with `systemctl start lrvspDaemon.service`) or enable it for future boots (`systemctl enable lrvspDaemon.service`).
## Customised Install
If the above configuration is not to your liking, consider the following:
1. Is the daemon being run using a venv, or using system packages?
- If using a venv, replace `$LRVSP_PYTHON_VENV` in the file with the absolute path to your venv (i.e. `/home/$USER/LRVSP_Python/venv`)
- If not using a venv, change `LRVSP_PYTHON_VENV/bin/python` in the `Exec` field to `python`, and remove `$LRVSP_PYTHON_VENV/bin:` from the `Environment="PATH`
2. Are you planning on running the daemon as the (at the time of configuring) currently logged in user?
- If yes,
  - Replace `$USER` in the file with the username of the currently logged in user (or the username of the user you wish to use).
  - Replace `$GROUP` in the file with the group name of the currently logged in user (or the groupname of the user you wish to use).
    This is usually the same as the username, but can be found by running `id -gn`.
  - Replace `$HOME` with the home directory of the currently logged in user (or the home directory of the user you wish to use).
- If no,
  - Remove the `USER`, `GROUP`, and `Environment="HOME` fields from the file
3. Set `$LRVSP_PYTHON_VENV` to the root directory of the project
4. Copy the file to `/etc/systemd/system/lrvspDaemon.service`, and reload systemd using `systemctl daemon-reload`.

After this, you should be free to start the daemon (with `systemctl start lrvspDaemon.service`) or enable it for future boots (`systemctl enable lrvspDaemon.service`).

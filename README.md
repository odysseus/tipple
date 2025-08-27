# Tipple: Microblogging for Flask

## Shell Commands Reminder

This is just a reminder of the shell commands that need to be run when the database does not exist:

```bash
$ export FLASK_APP=tipple
$ export TIPPLE_ENV=development
$ flask db init
$ flask db migrate -m "put a useful message here"
$ flask db upgrade
$ flask run
```

web: gunicorn --worker-class eventlet -w $(($(nproc) * 2)) mainpg:app

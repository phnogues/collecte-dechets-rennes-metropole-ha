# Image de test : Home Assistant + pytest-homeassistant-custom-component (Linux).
# docker build -t collecte-ha-test -f tests/docker/Dockerfile tools
# docker run --rm -v "$PWD:/src" -w /src collecte-ha-test
FROM python:3.14
COPY requirements.txt requirements-ha.txt /tmp/
RUN pip install --no-cache-dir --root-user-action=ignore -r /tmp/requirements.txt -r /tmp/requirements-ha.txt
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

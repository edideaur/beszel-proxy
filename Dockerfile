FROM python:3.12-alpine
WORKDIR /app
COPY beszel-proxy.py .
EXPOSE 6767
CMD ["python3", "beszel-proxy.py"]

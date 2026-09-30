FROM python:3.12-alpine
WORKDIR /app
COPY bridge.py .
USER 1000:1000
EXPOSE 8025
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8025/health').status == 200 else 1)"
CMD ["python", "-u", "bridge.py"]

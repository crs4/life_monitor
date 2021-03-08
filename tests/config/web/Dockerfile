FROM python:rc-alpine

# Install requirements
COPY app.py requirements.txt /
RUN pip3 install --no-cache-dir -r /requirements.txt

# Set a default secret token
ENV SECRET_TOKEN="Bearer 1234567890"

# Set default data path
ENV DATA_PATH="/data"

# Default entrpoint
ENTRYPOINT [ "python3" ]
CMD [ "/app.py" ]
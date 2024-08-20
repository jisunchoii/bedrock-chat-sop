FROM amazon/aws-lambda-python:3.11

WORKDIR /var/task/lambda-chat

COPY lambda_function.py /var/task/
COPY . ..

RUN /var/lang/bin/python3.11 -m pip install --upgrade pip
RUN /var/lang/bin/python3 -m pip install --upgrade -r /var/task/requirements.txt
 
CMD ["lambda_function.lambda_handler"]
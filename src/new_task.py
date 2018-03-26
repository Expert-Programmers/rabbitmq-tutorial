#!/usr/bin/env python
import sys
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
# connection = pika.BlockingConnection(pika.ConnectionParameters(host='172.17.0.2'))  # docker container ip address
channel = connection.channel()

channel.queue_declare(queue='task_queue', durable=True)

message = ' '.join(sys.argv[1:]) or 'Hello World'

channel.basic_publish(exchange='',
                      routing_key='task_queue',
                      body=message,
                      properties=pika.BasicProperties(
                          delivery_mode=2,  # 确保消息是持久的
                      ))
print(" [x] Sent %r" % message)
connection.close()

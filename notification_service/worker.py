import json
import pika
import time

def start_worker():
    connection = None
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
            break
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ not ready yet, retrying in 5s...")
            time.sleep(5)

    channel = connection.channel()

    def callback(ch,method,properties,body):
        print("task recieved")

        data = json.loads(body)
        email = data['user_email']
        task_id = data['task_id']

        print(f"processing {task_id}..")
        print(f"Sending email to {email}..")
        time.sleep(2)

        print("Email Sent Successfully")

    channel.basic_consume(
        queue='task_events',
        on_message_callback=callback,
        auto_ack=True
    )

    print("Waiting for message")
    channel.start_consuming()

if __name__ == '__main__':
    start_worker()
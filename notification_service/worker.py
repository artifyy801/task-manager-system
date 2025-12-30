import pika
import time
import json
from fpdf import FPDF
import sys
import os

# --- 1. Define the PDF Generator Function ---
def generate_pdf(user_email):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=f"Bank Statement for: {user_email}", ln=1, align="C")
    pdf.cell(200, 10, txt="--------------------------------------------------", ln=2, align="L")
    pdf.cell(200, 10, txt="1. Netflix Subscription      - $15.00", ln=3, align="L")
    pdf.cell(200, 10, txt="2. Salary Deposit            + $3000.00", ln=4, align="L")
    pdf.cell(200, 10, txt="3. Grocery Store             - $45.20", ln=5, align="L")
    
    filename = f"statement_{user_email.split('@')[0]}.pdf"
    pdf.output(filename)
    print(f"     [v] PDF generated: {filename}")

# --- 2. Define the Callback Function (Must be before main!) ---
def callback(ch, method, properties, body):
    print(" [x] Task received")
    data = json.loads(body)
    user_email = data.get('user_email')
    
    # Simulate processing
    print(f"     Processing for: {user_email}...")
    
    # Check if this is a banking request
    if "Statement" in data.get('title', ''):
        generate_pdf(user_email)
        time.sleep(2) # Fake "heavy work" delay
    
    # Create the update message for the frontend
    update_msg = {
        "user_email": user_email,
        "status": "COMPLETED",
        "message": "Your Bank Statement is ready for download!"
    }

    # Send feedback to the API (task_updates queue)
    # ch.queue_declare(queue='task_updates') 
    ch.basic_publish(
        exchange='',
        routing_key='task_updates',
        body=json.dumps(update_msg)
    )
    
    print(f"     [v] Feedback sent for {user_email}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

# --- 3. The Main Function ---
def main():
    # Connect to RabbitMQ
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=rabbitmq_host)
    )
    channel = connection.channel()

    # Declare the queues (Fixes the 404 error)
    channel.queue_declare(queue='task_events', durable=True)
    channel.queue_declare(queue='task_updates')

    print(' [*] Waiting for tasks. To exit press CTRL+C')

    # Start consuming (Now 'callback' is defined!)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='task_events', on_message_callback=callback)

    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
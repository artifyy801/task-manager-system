Getting Started
Prerequisites
Docker & Docker Compose installed on your machine.

Installation & Running
1. Clone the repository:

   git clone https://github.com/artifyy801/task-manager-system.git
   cd task-manager-system

2. Run the System: This command builds the images and starts all 6 containers (including DBs) in the correct dependency order.

   docker-compose up --build

 3. Access the Application:

    Frontend Dashboard: http://localhost:3000
    RabbitMQ Management: http://localhost:15672 (User/Pass: guest)
    API Docs: http://localhost:8001/docs


Testing the Flow

Register/Login: Open the Frontend  and create an account.

Generate Statement: Click "Generate Monthly Statement".

Watch the Magic:

The request is sent to the Task Service.

Task Service pushes a message to RabbitMQ.


Notification Worker picks it up, generates a PDF, and simulates a delay.

Once done, the Frontend receives a Real-Time Notification via WebSocket.

# 介绍

RabbitMQ是一个消息代理：它接受和转发消息。你可以把它想象成一个邮局：当你把你想要发布的邮件放在邮箱中时，你可以确定邮差先生最终将邮件发送给你的收件人。在这个比喻中，RabbitMQ是邮政信箱，邮局和邮递员。

RabbitMQ和邮局的主要区别在于它不处理纸张，而是接受，存储和转发二进制数据块 -- 消息。

请注意，生产者，消费者和消息代理不必驻留在同一主机上; 实际上在大多数应用程序中它们不是同一主机上。

## Hello World!

**(using the Pika Python client)**

> pip3 install pika

在本教程的这一部分，我们将使用Python编写两个小程序; 发送单个消息的生产者（发送者），以及接收消息并将其打印出来的消费者（接收者）。这是一个消息传递的“Hello World”。

在下图中，“P”是我们的生产者，“C”是我们的消费者。中间的盒子是一个队列 - RabbitMQ代表消费者保存的消息缓冲区。

我们的整体设计将如下所示：

![](https://img.vim-cn.com/c3/195b9c4944119ebc3ac0d398b5c88c6ee1635b.png)

    生产者将消息发送到“hello”队列，消费者接收来自该队列的消息。

### 发送

![](https://img.vim-cn.com/00/7b8d064558478c7e96128df720e5ab7988f938.png)

我们的第一个程序 *send.py* 会向队列发送一条消息。我们需要做的第一件事是与RabbitMQ服务器建立连接。

```python
#!/usr/bin/env python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
```

我们现在连接到本地上的的代理 - 因此是 *'localhost'*。如果我们想连接到另一台机器上的代理，我们只需在此指定其名称或IP地址。

接下来，在发送之前，我们需要确保收件人队列存在。如果我们发送消息到不存在的位置，RabbitMQ将只删除该消息。我们来创建一个将传递消息的 *hello* 队列：

```python
channel.queue_declare(queue='hello')
```

此时我们准备发送消息。我们的第一条消息将只包含一个字符串 "Hello World!"我们想把它发送给我们的 *hello* 队列。

在RabbitMQ中，消息永远不会直接发送到队列，它总是需要经过交换。我们现在需要知道的是如何使用由空字符串标识的默认交换。这种交换是特殊的 - 它允许我们准确地指定消息应该到达哪个队列。队列名称需要在routing_key参数中指定：

```python
channel.basic_publish(exchange='',
                      routing_key='hello',
                      body='Hello World！')
print(" [x] Sent 'Hello World!'")
```

在退出程序之前，我们需要确保网络缓冲区被刷新，并且我们的消息被实际传送到RabbitMQ。我们可以通过轻轻关闭连接来完成。

```python
connection.close()
```

### 接收

![](https://img.vim-cn.com/cc/4f260212af5829f14336f14eeff1d33c919bfe.png)

我们的第二个程序 *receive.py* 将接收队列中的消息并将它们打印在屏幕上。

再次，我们首先需要连接到RabbitMQ服务器。负责连接到Rabbit的代码与以前相同。

下一步，就像以前一样，要确保队列存在。使用queue_declare创建一个队列是幂等的 - 我们可以根据需要多次运行该命令，并且只会创建一个。

```python
channel.queue_declare()
```

您可能会问为什么我们再次声明队列 - 我们已经在之前的代码中声明了它。如果我们确信队列已经存在，我们可以避免这种情况。例如，如果 *send.py* 程序之前运行过。但我们还不确定首先运行哪个程序。在这种情况下，重复在两个程序中重复声明队列是一种很好的做法。

    列出队列

    您可能希望看到RabbitMQ有什么队列以及它们中有多少条消息。您可以使用rabbitmqctl工具（作为特权用户）执行此操作：
    
    > sudo rabbitmqctl list_queues

    在Windows上，省略sudo：

    > rabbitmqctl.bat list_queues


从队列接收消息更为复杂。它通过向队列订阅 *回调函数* 来工作。每当我们收到一条消息，这个回调函数就被皮卡库调用。在我们的例子中，这个函数会在屏幕上打印消息的内容。

```python
def callback(ch, method, propertites, body):
    print(" [x] Received {}".format(body))
```

接下来，我们需要告诉RabbitMQ这个特定的回调函数应该从我们的hello队列接收消息：

```python
channel.basic_consume(callable, queue='hello', no_ack=True)
```

为了让这个命令成功，我们必须确保我们想要订阅的队列存在。幸运的是，我们对此有信心 - 我们已经使用*queue_declare*创建了一个队列。

NO_ACK参数，后面(几篇之后)会有解释。

最后，我们进入一个永无止境的循环，等待数据并在必要时运行回调。

```python
print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()
```

### 把它放在一起

*send.py*的完整代码：
```python
#!/usr/bin/env python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()


channel.queue_declare(queue='hello')

channel.basic_publish(exchange='',
                      routing_key='hello',
                      body='Hello World!')
print(" [x] Sent 'Hello World!'")
connection.close()
```

*receive.py*的完整代码：

```python
#!/usr/bin/env python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='hello')


def callback(ch, method, propertites, body):
    print(" [x] Received {}".format(body))


channel.basic_consume(callable,
                      queue='hello',
                      no_ack=True)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()
```

现在我们可以在终端上试用我们的程序。首先，让我们开始一个消费者，它将持续运行等待交付：

```
python receive.py
# => [*] Waiting for messages. To exit press CTRL+C
# => [x] Received 'Hello World!'
```

现在开始制作。生产者计划将在每次运行后停止：

```
python send.py
# => [x] Sent 'Hello World!'
```

欢呼！我们能够通过RabbitMQ发送我们的第一条消息。正如您可能已经注意到的，*receive.py* 程序不会退出。它会随时准备接收更多消息，并可能会被Ctrl-C中断。

尝试在新终端中再次运行 *send.py*。

![](https://img.vim-cn.com/60/5e98664093a8795e78a850b5e5cfca048b7936.png)

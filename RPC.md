# 远程过程调用(RPC)

**(using the Pika Python client)**

## 本章节教程重点介绍的内容

在第二篇教程中，我们学习了如何使用工作队列在多个工作人员之间分配耗时的任务。

但是如果我们需要在远程计算机上运行某个功能并等待结果呢？那么，这是一个不同的事情。
这种模式通常称为远程过程调用(RPC)。

在本教程中，我们将使用RabbitMQ构建一个RPC系统：一个客户端和一个可扩展的RPC服务器。
由于我们没有任何值得分发的耗时任务，我们将创建一个返回斐波那契数字的虚拟RPC服务。

### 客户端界面

为了说明如何使用RPC服务，我们将创建一个简单的客户端类。它将公开一个名为call的方法 ，
它发送一个RPC请求并阻塞，直到收到答案：

```python
fibonacci_rpc = FibonacciRpcClient()
result = fibonacci_rpc.call(4)
print("fib(4) is %r" % result)
```

    *有关RPC的说明*

    虽然RPC是计算中很常见的模式，但它经常被吹毛求疵。当程序员不知道函数调用是本地的还是
    慢速的RPC时会出现这些问题。像这样的混乱导致不可预知的问题，并增加了调试的不必要的复杂性，
    而不是我们想要的简化软件。

    铭记这一点，请考虑以下建议：

      * 确保显而易见哪个函数调用是本地的，哪个是远程的。
      * 记录您的系统。清楚组件之间的依赖关系。
      * 处理错误情况。当RPC服务器长时间关闭时，客户端应该如何反应？

    有疑问时避免RPC。如果可以的话，你应该使用异步管道 - 而不是类似于RPC的阻塞，
    其结果被异步推送到下一个计算阶段。

### 回调队列

一般来说，通过RabbitMQ来执行RPC是很容易的。客户端发送请求消息，服务器回复响应消息。
为了接收响应，客户端需要发送一个“回调”队列地址和请求。让我们试试看：

```python
result = channel.queue_declare(exclusive=True)
callback_queue = result.method.queue

channel.basic_publish(exchange='',
                      routing_key='rpc_queue',
                      properties=pika.BasicProperties(
                            reply_to = callback_queue,
                            ),
                      body=request)
```

    消息属性

    AMQP 0-9-1协议预定义了一组包含14个属性的消息。大多数属性很少使用，但以下情况除外：

    delivery_mode：将消息标记为持久（值为2）或瞬态（任何其他值）。你可能会记得第二篇教程中的这个属性。
    content_type：用于描述编码的MIME类型。例如，对于经常使用的JSON编码，将此属性设置为application/json是一种很好的做法。
    reply_to：通常用于命名回调队列。
    correlation_id：用于将RPC响应与请求关联起来。

### 相关ID

在上面介绍的方法中，我们建议为每个RPC请求创建一个回调队列。这是非常低效的，
但幸运的是有一个更好的方法 - 让我们为每个客户端创建一个回调队列。

这引发了一个新问题，在该队列中收到回复后，不清楚回复属于哪个请求。那是什么时候使用*correlation_id*属性。
我们将把它设置为每个请求的唯一值。稍后，当我们在回调队列中收到消息时，我们将查看此属性，
并基于此属性，我们将能够将响应与请求进行匹配。如果我们看到未知的*correlation_id*值，
我们可以放心地丢弃该消息 - 它不属于我们的请求。

您可能会问，为什么我们应该忽略回调队列中的未知消息，而不是抛出错误？
这是由于服务器端可能出现竞争状况。虽然不太可能，但在发送给我们答案之后，但在发送请求的确认消息之前，
RPC服务器可能会死亡。如果发生这种情况，重新启动的RPC服务器将再次处理该请求。
这就是为什么在客户端，我们必须优雅地处理重复的响应，理想情况下RPC应该是等幂的。

### 总结

![](https://img.vim-cn.com/77/6421b870f66733dad0c50531088049591a14b6.png)

我们的RPC会像这样工作：

  * 当客户端启动时，它创建一个匿名独占回调队列。
  * 对于RPC请求，客户端将发送具有两个属性的消息：*reply_to*，该消息设置为回调队列和*correlation_id*，该值设置为每个请求的唯一值。
  * 该请求被发送到*rpc_queue*队列。
  * RPC worker(又名：服务器)正在等待该队列上的请求。当出现请求时，它执行该作业，并使用*reply_to*字段中的队列将结果发送回客户端。
  * 客户端在回调队列中等待数据。当出现消息时，它会检查*correlation_id*属性。如果它匹配来自请求的值，则返回对应用程序的响应。

### 把它放在一起

*rpc_server.py*的代码：
```python
#!/usr/bin/env python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

channel = connection.channel()

channel.queue_declare(queue='rpc_queue')


def fib(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fib(n - 1) + fib(n - 2)


def on_request(ch, method, props, body):
    n = int(body)

    print(" [.] fib(%s)" % n)
    response = fib(n)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(
                         correlation_id=props.correlation_id),
                     body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_size=1)
channel.basic_consume(on_request, queue='rpc_queue')

print(" [x] Awaiting RPC requests")
channel.start_consuming()
```

服务器代码非常简单：

  - （4）像往常一样，我们首先建立连接并声明队列。
  - （11）我们声明我们的斐波那契函数。它只假定有效的正整数输入。（不要指望这个版本适用于大数字，它可能是最慢的递归实现）。
  - （20）我们声明了*basic_consume*的回调，它是RPC服务器的核心。它在收到请求时执行。它完成工作并将响应发回。
  - （34）我们可能想运行多个服务器进程。为了在多台服务器上平均分配负载，我们需要设置*prefetch_count*设置。

*rpc_client.py*的代码：

```python
#!/usr/bin/env python
import pika
import uuid


class FibonacciRpcClient:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(self.on_response, no_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.corrrelation_id:
            self.response = body

    def call(self, n):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(exchange='',
                                   routing_key='rpc_queue',
                                   properties=pika.BasicProperties(
                                       reply_to=self.callback_queue,
                                       correlation_id=self.corr_id),
                                   body=str(n))
        while self.response is None:
            self.connection.process_data_events()

        return int(self.response)


fibonacci_rpc = FibonacciRpcClient()

print(" [x] Requesting fib(30)")
response = fibonacci_rpc.call(30)
print(" [.] Got %r" % response)
```

客户端代码稍有涉及：

  - （8）我们建立连接，通道并为回复声明独占的“回调”队列。
  - （17）我们订阅'回调'队列，以便我们可以接收RPC响应。
  - （19）对每个响应执行的'*on_response*'回调函数做了一个非常简单的工作，对于每个响应消息它检查*correlation_id*是否是我们正在寻找的。如果是这样，它将保存*self.response*中的响应并打破消费循环。
  - （23）接下来，我们定义我们的主要调用方法 - 它执行实际的RPC请求。
  - （25）在这个方法中，首先我们生成一个唯一的*correlation_id*数并保存 - '*on_response*'回调函数将使用这个值来捕获适当的响应。
  - （29）接下来，我们发布具有两个属性的请求消息：*reply_to*和*correlation_id*。
  - （32）在这一点上，我们可以坐下来等待，直到适当的回应到达。
  - （41）最后，我们将回复返回给用户。
